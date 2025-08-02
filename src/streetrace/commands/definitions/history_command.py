"""Implement the history command for displaying conversation history.

This module defines the HistoryCommand class which allows users to view
the current conversation history in the interactive mode.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from rich.console import Console, Group

    from streetrace.session.session_manager import SessionManager
    from streetrace.system_context import SystemContext
    from streetrace.ui.ui_bus import UiBus

from pydantic import BaseModel

from streetrace.commands.base_command import Command
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer

logger = get_logger(__name__)


class _DisplayHistory(BaseModel):
    system_message: str | None
    context: Sequence[str] | None
    session: "Session | None"


_MAX_FUNCTION_ARG_LENGTH = 20
"""Maximum length for function arguments preview."""

_MAX_RESPONSE_VALUE_LENGTH = 20
"""Maximum length for function response values preview."""


def _truncate_value(value: object, max_length: int) -> str:
    """Truncate a value to a maximum length and add ellipsis if needed.

    Args:
        value: The value to truncate
        max_length: Maximum allowed length

    Returns:
        Truncated string with ellipsis if needed

    """
    string_value = str(value)
    if len(string_value) <= max_length:
        return string_value
    return f"{string_value[:max_length]}... [{len(string_value)} chars]"


def _render_message_content(msg: "Event") -> "Group":
    """Extract and format message content parts for rendering.

    Args:
        msg: The event to render content from.

    Returns:
        A list of rendered content parts.

    """
    from rich.console import Group

    group = Group()

    # Check for escalation messages
    if msg.is_final_response() and msg.actions and msg.actions.escalate:
        error_message = (
            f"Agent escalated: {msg.error_message or 'No specific message.'}"
        )
        group.renderables.append(
            f"[{Styles.RICH_ERROR}]{error_message}[/{Styles.RICH_ERROR}]",
        )

    if msg.content and msg.content.parts:
        from rich.markdown import Markdown
        from rich.syntax import Syntax

        for part in msg.content.parts:
            # Handle text content
            if part.text:
                style = Styles.RICH_INFO
                if msg.is_final_response():
                    style = Styles.RICH_MODEL

                markdown_text = Markdown(
                    part.text,
                    inline_code_theme=Styles.RICH_MD_CODE,
                    style=style,
                )
                group.renderables.append(markdown_text)

            # Handle function calls
            if part.function_call:
                call = part.function_call
                # Truncate function arguments to improve readability
                truncated_args = _truncate_value(call.args, _MAX_FUNCTION_ARG_LENGTH)
                group.renderables.append(
                    Syntax(
                        code=f"{call.name}({truncated_args})",
                        lexer="python",
                        theme=Styles.RICH_TOOL_CALL,
                        line_numbers=False,
                        background_color="default",
                    ),
                )

            # Handle function responses
            if part.function_response:
                resp = part.function_response
                if resp.response:
                    response_lines = []
                    for key in resp.response:
                        value = _truncate_value(
                            resp.response[key],
                            _MAX_RESPONSE_VALUE_LENGTH,
                        )
                        response_lines.append(f"  ↳ {key}: {value}")

                    response_text = "\n".join(response_lines)
                    group.renderables.append(
                        Syntax(
                            code=response_text,
                            lexer="python",
                            theme=Styles.RICH_TOOL_CALL,
                            line_numbers=False,
                            background_color="default",
                        ),
                    )

    return group


@register_renderer
def render_history(obj: _DisplayHistory, console: "Console") -> None:
    """Render a full history on the UI."""
    from rich.table import Table

    table = Table(
        title="Conversation history",
        show_lines=False,
        leading=1,
        box=None,
    )

    table.add_column(
        "Role",
        justify="right",
        style=Styles.RICH_HISTORY_ROLE,
        no_wrap=True,
    )
    table.add_column("Message", style=Styles.RICH_HISTORY_MESSAGE)

    if obj.system_message:
        table.add_row("System", obj.system_message)

    session_message_count = 0
    if obj.session:
        for msg in obj.session.events:
            session_message_count += 1
            message_parts = _render_message_content(msg)
            if (
                msg.content
                and msg.content.parts
                and msg.content.parts[0].function_response is None
            ):
                # add a blank line to separate between events unless it's a function
                # response
                # Add row to table with role and combined message parts
                table.add_row(msg.author, message_parts)
            else:
                # Add row to table with role and combined message parts
                table.add_row("", message_parts)

    if session_message_count == 0:
        table.add_row("", "No other messages yet...")

    console.print(table)


class HistoryCommand(Command):
    """Command to display the conversation history."""

    def __init__(
        self,
        ui_bus: "UiBus",
        system_context: "SystemContext",
        session_manager: "SessionManager",
    ) -> None:
        """Initialize a new instance of HistoryCommand."""
        self.ui_bus = ui_bus
        self.system_context = system_context
        self.session_manager = session_manager

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["history"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Display the conversation history."

    @override
    async def execute_async(self) -> None:
        """Execute the history display action using the HistoryManager."""
        logger.info("Executing history command.")
        system = self.system_context.get_system_message()
        context = self.system_context.get_project_context()
        session = await self.session_manager.get_current_session()
        if session:
            self.ui_bus.dispatch_ui_update(
                _DisplayHistory(
                    system_message=system,
                    context=context,
                    session=session,
                ),
            )
        else:
            self.ui_bus.dispatch_ui_update(ui_events.Info("No history available yet."))
