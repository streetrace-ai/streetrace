"""Conversation history management."""

from collections.abc import Iterable
from dataclasses import field
from enum import Enum
from typing import TYPE_CHECKING, Any

import litellm
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from streetrace.args import Args
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer

if TYPE_CHECKING:
    # Avoid circular imports for type hinting
    from streetrace.ui.ui_bus import UiBus


logger = get_logger(__name__)

_MAX_MENTION_CONTENT_LENGTH = 20000
"""Maximum length for file content to prevent excessive tokens."""

_MAX_CONTEXT_PREVIEW_LENGTH = 200
"""Maximum length for context preview."""


class Role(str, Enum):
    """Roles in a conversation between user, model and tools."""

    @staticmethod
    def _generate_next_value_(
        name: str,
        start: int,  # noqa: ARG004
        count: int,  # noqa: ARG004
        last_values: list[str],  # noqa: ARG004
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
    context: Iterable[str] | None = None
    messages: list[litellm.Message] = field(default_factory=list)

    def get_all_messages(self) -> list[litellm.Message]:
        """Create messages for the conversation history.

        Returns:
            List of litellm.Message objects

        """
        messages = []
        if self.system_message:
            messages.append(
                litellm.Message(
                    role=Role.SYSTEM,  # type: ignore[not-assignable]: wrong declaraion in adk
                    content=self.system_message,
                ),
            )
        if self.context:
            messages.append(
                litellm.Message(
                    role=Role.CONTEXT,  # type: ignore[not-assignable]: wrong declaraion in adk
                    content="".join(self.context),
                ),
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
        tool_call: dict[str, Any] | None = None,
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
            litellm.Message(
                role="user",  # type: ignore[not-assignable]: wrong declaraion in adk
                content=content,
            ),
        )

    def add_context_message(self, title: str, content: str) -> None:
        """Add user message to the conversation history.

        Args:
            title: The title of the context item
            content: The content of the context item

        """
        self.messages.append(
            litellm.Message(
                role="user",  # type: ignore[not-assignable]: wrong declaraion in adk
                content=f"---\n# {title}\n\n{content}\n\n---",
            ),
        )


@register_renderer
def render_history(history: History, console: Console) -> None:
    """Render a full history on the UI."""
    table = Table(title="Conversation history")

    table.add_column(
        "Role",
        justify="right",
        style=Styles.RICH_HISTORY_ROLE,
        no_wrap=True,
    )
    table.add_column("Message", style=Styles.RICH_HISTORY_MESSAGE)

    if history.system_message:
        table.add_row("System", history.system_message)
    if history.context:
        context_str = str(history.context)
        display_context = (
            context_str[:_MAX_CONTEXT_PREVIEW_LENGTH] + "..."
            if len(context_str) > _MAX_CONTEXT_PREVIEW_LENGTH
            else context_str
        )
        table.add_row("Context", display_context)
    if not history.messages:
        table.add_row("", "No other messages yet...")
    else:
        for msg in history.messages:
            content = msg.content or ""
            if content and msg.tool_calls:
                content += "\n\n"
            if msg.tool_calls:
                content += " + tool calls"
            table.add_row(msg.role, content)

    console.print(table)


class HistoryManager:
    """Manages the state and operations related to conversation history."""

    def __init__(
        self,
        app_args: Args,
        ui_bus: "UiBus",
        system_context: SystemContext,
    ) -> None:
        """Initialize the HistoryManager.

        Args:
            app_args: Application args.
            ui_bus: UI event bus to exchange messages with the UI.
            system_context: System and project context data access.

        """
        self.app_args = app_args
        self.ui_bus = ui_bus
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
