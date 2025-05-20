"""Implement the history command for displaying conversation history.

This module defines the HistoryCommand class which allows users to view
the current conversation history in the interactive mode.
"""

from collections.abc import Sequence
from typing import override

from google.adk.sessions import Session
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from streetrace.commands.base_command import Command
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.ui import ui_events
from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer
from streetrace.ui.ui_bus import UiBus
from streetrace.workflow.supervisor import SessionManager

logger = get_logger(__name__)


class _DisplayHistory(BaseModel):
    system_message: str | None
    context: Sequence[str] | None
    session: Session | None


_MAX_CONTEXT_PREVIEW_LENGTH = 200
"""Maximum length for context preview."""


@register_renderer
def render_history(obj: _DisplayHistory, console: Console) -> None:
    """Render a full history on the UI."""
    table = Table(title="Conversation history", show_lines=True)

    table.add_column(
        "Role",
        justify="right",
        style=Styles.RICH_HISTORY_ROLE,
        no_wrap=True,
    )
    table.add_column("Message", style=Styles.RICH_HISTORY_MESSAGE)

    if obj.system_message:
        table.add_row("System", obj.system_message)
    if obj.context:
        for context_item in obj.context:
            context_str = str(context_item)
            display_context = (
                context_str[:_MAX_CONTEXT_PREVIEW_LENGTH] + "..."
                if len(context_str) > _MAX_CONTEXT_PREVIEW_LENGTH
                else context_str
            )
            table.add_row("Context", display_context)

    session_message_count = 0
    if obj.session:
        for msg in obj.session.events:
            # render here
            pass

    if session_message_count == 0:
        table.add_row("", "No other messages yet...")
    console.print(table)


class HistoryCommand(Command):
    """Command to display the conversation history."""

    def __init__(
        self,
        ui_bus: UiBus,
        system_context: SystemContext,
        session_manager: SessionManager,
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
        """Execute the history display action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        """
        logger.info("Executing history command.")
        system = self.system_context.get_system_message()
        context = self.system_context.get_project_context()
        session = self.session_manager.get_current_session()
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
