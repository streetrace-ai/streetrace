"""Conversation history management."""

import logging
from dataclasses import field
from enum import Enum
from typing import TYPE_CHECKING

import litellm
from pydantic import BaseModel

from streetrace.args import Args
from streetrace.llm_interface import LlmInterface
from streetrace.system_context import SystemContext
from streetrace.tools.tool_call_result import ToolCallResult

if TYPE_CHECKING:
    # Avoid circular imports for type hinting
    from streetrace.ui.console_ui import ConsoleUI


logger = logging.getLogger(__name__)

_MAX_MENTION_CONTENT_LENGTH = 20000
"""Maximum length for file content to prevent excessive tokens."""
_MAX_CONTEXT_PREVIEW_LENGTH = 200
"""Maximum length for context preview."""


class Role(str, Enum):
    """Roles in a conversation between user, model and tools."""

    @staticmethod
    def _generate_next_value_(
        name: str,
        _start: int,
        _count: int,
        _last_values: list[str],
    ) -> str:
        return name

    SYSTEM = "system"
    USER = "user"
    CONTEXT = "user"  # noqa: PIE796
    MODEL = "assistant"
    TOOL = "tool"


class History(BaseModel):
    """Model for the conversation history."""

    system_message: str | None = None
    context: str | None = None
    messages: list[litellm.Message] = field(default_factory=list)

    def get_all_messages(self) -> list[litellm.Message]:
        """Create messages for the conversation history.

        Returns:
            List of litellm.Message objects

        """
        messages = []
        if self.system_message:
            messages.append(
                litellm.Message(role=Role.SYSTEM, content=self.system_message),
            )
        if self.context:
            messages.append(
                litellm.Message(role=Role.CONTEXT, content=self.context),
            )
        return messages + self.messages

    def add_assistant_message(self, message: litellm.Message) -> None:
        """Add an assistant message to the conversation history.

        Args:
            message: The content of the assistant message

        """
        self.messages.append(message)

    def add_assistant_message_test(
        self,
        content: str,
        tool_call: dict[str, any] | None = None,
    ) -> None:
        """Add an assistant message to the conversation history.

        Args:
            content: The content of the assistant message
            tool_call: Optional tool call to add to the assistant message

        """
        tool_calls_part = []
        if tool_call:
            tool_calls_part = [
                litellm.ChatCompletionMessageToolCall(
                    id=tool_call["tool_call_id"],
                    type="function",
                    function={
                        "name": tool_call["tool_name"],
                        "arguments": tool_call["arguments"],
                    },
                ),
            ]
        self.messages.append(
            litellm.Message(
                role="assistant",
                content=content,
                tool_calls=tool_calls_part,
            ),
        )

    def add_user_message(self, content: str) -> None:
        """Add user message to the conversation history.

        Args:
            content: The content of the user message

        """
        self.messages.append(
            litellm.Message(role="user", content=content),
        )

    def add_context_message(self, title: str, content: str) -> None:
        """Add user message to the conversation history.

        Args:
            title: The title of the context item
            content: The content of the context item

        """
        self.messages.append(
            litellm.Message(role="user", content=f"---\n# {title}\n\n{content}\n\n---"),
        )

    def add_tool_message(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_result: ToolCallResult,
    ) -> None:
        """Add user message to the conversation history.

        Args:
            tool_call_id: The ID of the tool call
            tool_name: The name of the tool
            tool_result: The result of the tool call

        """
        self.messages.append(
            litellm.Message(
                role="tool",
                tool_call_id=tool_call_id,
                name=tool_name,
                content=tool_result.model_dump_json(exclude_none=True),
            ),
        )


class HistoryManager:
    """Manages the state and operations related to conversation history."""

    def __init__(
        self,
        app_args: Args,
        ui: "ConsoleUI",
        system_context: SystemContext,
        llm_interface: LlmInterface,
    ) -> None:
        """Initialize the HistoryManager.

        Args:
            app_args: Application args.
            ui: ConsoleUI instance for displaying messages.
            system_context: System and project context data access.
            llm_interface: LLM interface (e.g., for compacting history.)

        """
        self.app_args = app_args
        self.ui = ui
        self.system_context = system_context
        self.llm_interface = llm_interface
        self._conversation_history: History | None = None
        logger.info("HistoryManager initialized.")

    def initialize_history(self) -> None:
        """Initialize the conversation history."""
        # Get system and project context from SystemContext
        system_message = self.system_context.get_system_message()
        project_context = self.system_context.get_project_context()

        self._conversation_history = History(
            system_message=system_message,
            context=project_context,
        )

    def get_history(self) -> History | None:
        """Return the current conversation history."""
        return self._conversation_history

    def set_history(self, history: History) -> None:
        """Set the conversation history (used during compaction)."""
        self._conversation_history = history

    def add_mentions_to_history(self, mentioned_files: list[tuple[str, str]]) -> None:
        """Add content from mentioned files to conversation history.

        Args:
            mentioned_files: List of tuples containing (filepath, content).

        """
        history = self.get_history()
        if not history:
            logger.error("Cannot add mentions, history is not initialized.")
            return

        if not mentioned_files:
            return

        for filepath, content in mentioned_files:
            context_title = filepath
            context_message = content
            if len(content) > _MAX_MENTION_CONTENT_LENGTH:
                context_title = f"{filepath} (truncated)"
                context_message = content[:_MAX_MENTION_CONTENT_LENGTH]
                logger.warning(
                    "Truncated content for mentioned file @%s due to size.",
                    filepath,
                )
            history.add_context_message(
                context_title,
                context_message,
            )
            logger.debug("Added context from @%s to history.", filepath)

    def add_user_message(self, message: str) -> None:
        """Add a user message to the history."""
        history = self.get_history()
        if history:
            history.add_user_message(message)
            logger.debug("User message added to history.")
        else:
            logger.error("Cannot add user message, history not initialized.")

    def _display_history_header(self, history: History) -> None:
        """Display the header part of the history (system message, context)."""
        self.ui.display_info("\n--- Conversation History ---")
        if history.system_message:
            self.ui.display_system_message(history.system_message)
        if history.context:
            context_str = str(history.context)
            display_context = (
                context_str[:_MAX_CONTEXT_PREVIEW_LENGTH] + "..."
                if len(context_str) > _MAX_CONTEXT_PREVIEW_LENGTH
                else context_str
            )
            self.ui.display_context_message(display_context)

    def _display_history_messages(self, history: History) -> None:
        """Display the messages part of the history."""
        if not history.messages:
            self.ui.display_info("No messages in history yet.")
        else:
            for msg in history.messages:
                if msg.role == Role.USER and msg.content:
                    self.ui.display_history_user_message(msg.content)
                elif msg.role == Role.MODEL:
                    if msg.content:
                        self.ui.display_history_assistant_message(msg.content)
                    if msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            self.ui.display_tool_call(tool_call)
                elif msg.role == Role.TOOL and msg.content:
                    tool_result = ToolCallResult.model_validate_json(msg.content)
                    self.ui.display_tool_result(msg.name, tool_result)

    def display_history(self) -> None:
        """Display the current conversation history using the UI."""
        history = self.get_history()
        if not history:
            self.ui.display_warning("No history available yet.")
            return

        self._display_history_header(history)
        self._display_history_messages(history)
        self.ui.display_info("--- End History ---")

    async def compact_history(self) -> None:
        """Compact the current conversation history by generating a summary."""
        current_history = self.get_history()
        if not current_history or not current_history.messages:
            self.ui.display_warning("No history available to compact.")
            return

        self.ui.display_info("Compacting conversation history...")

        system_message = current_history.system_message
        context = current_history.context

        # Create a temporary history for the summarization request
        # Convert existing messages to dicts to avoid Pydantic validation issues
        messages_as_dicts = [msg.model_dump() for msg in current_history.messages]
        summary_request_history = History(
            system_message=system_message,
            context=context,
            messages=messages_as_dicts,  # Pass dicts
        )

        summary_prompt = """Please summarize our conversation so far, describing the
goal of the conversation, detailed plan we developed, all the key points and decisions.
Mark which points of the plan are already completed and mention all relevant artifacts.

Your summary should:
1. Preserve all important information, file paths, and code changes
2. Include any important decisions or conclusions we've reached
3. Keep any critical context needed for continuing the conversation
4. Format the summary as a concise narrative

Return ONLY the summary without explaining what you're doing."""

        summary_request_history.add_user_message(summary_prompt)

        logger.info("Requesting conversation summary from LLM")

        messages = await self.llm_interface.generate_async(
            self.app_args.model,
            summary_request_history,
        )
        # Get the summary message from the response
        last_message = None
        if hasattr(messages, "choices") and messages.choices:
            last_message = messages.choices[0].message

        if last_message:
            # Create a new history with just the summary
            new_history = History(system_message=system_message, context=context)

            # Pass the whole Message object to add_assistant_message
            new_history.add_assistant_message(last_message)
            # Replace the current history
            self.set_history(new_history)
            self.ui.display_info("History compacted successfully.")
        else:
            self.ui.display_warning(
                "The last message in history is not model, skipping compact. Please report or fix in code if that's not right.",
            )
            logger.error("LLM response was not in the expected format for summary.")

    def clear_history(self) -> None:
        """Clear the current conversation history, resetting it to the initial state."""
        logger.info("Attempting to clear conversation history.")
        try:
            # Re-initialize history as if starting an interactive session
            self.initialize_history()
            logger.info("Conversation history cleared successfully.")
            self.ui.display_info("Conversation history has been cleared.")
        except Exception as e:
            logger.exception("Failed to rebuild context while clearing history")
            self.ui.display_error(
                f"Could not clear history due to an error: {e}",
            )
