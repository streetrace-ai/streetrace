"""Conversation history management."""

from dataclasses import field
from enum import Enum
from typing import TYPE_CHECKING

import litellm
from pydantic import BaseModel

from streetrace.args import Args
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.tool_call_result import ToolCallResult

if TYPE_CHECKING:
    # Avoid circular imports for type hinting
    from streetrace.ui.console_ui import ConsoleUI


logger = get_logger(__name__)

_MAX_MENTION_CONTENT_LENGTH = 20000
"""Maximum length for file content to prevent excessive tokens."""


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

    def add_assistant_message(self, message: litellm.Message | str) -> None:
        """Add an assistant message to the conversation history.

        Args:
            message: The content of the assistant message

        """
        if isinstance(message, litellm.Message):
            self.messages.append(message)
        elif isinstance(message, str):
            self.messages.append(
                litellm.Message(
                    role="assistant",
                    content=message,
                ),
            )
        else:
            msg = f"Unexpected message type: {type(message).__name__}"
            raise TypeError(msg)

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
    ) -> None:
        """Initialize the HistoryManager.

        Args:
            app_args: Application args.
            ui: ConsoleUI instance for displaying messages.
            system_context: System and project context data access.

        """
        self.app_args = app_args
        self.ui = ui
        self.system_context = system_context
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
