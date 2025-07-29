"""Implement the clear command for resetting conversation history.

This module defines the ResetSessionCommand class which allows users to clear
the current conversation history in the interactive mode.
"""

# Import Application for type hint only, avoid circular dependency if possible
from typing import TYPE_CHECKING, override

from streetrace.commands.base_command import Command
from streetrace.log import get_logger
from streetrace.ui import ui_events

if TYPE_CHECKING:
    from streetrace.session.session_manager import SessionManager
    from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class ResetSessionCommand(Command):
    """Command to clear the conversation history, resetting it to the initial state."""

    def __init__(self, ui_bus: "UiBus", session_manager: "SessionManager") -> None:
        """Initialize a new instance of ResetSessionCommand."""
        self.ui_bus = ui_bus
        self.session_manager = session_manager

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["reset"]

    @property
    def description(self) -> str:
        """Command description."""
        return (
            "Start a new conversation session from the initial system instruction and "
            "context."
        )

    @override
    async def execute_async(self) -> None:
        """Execute the history clearing action using the HistoryManager."""
        # Re-initialize history as if starting an interactive session
        self.session_manager.reset_session()
        logger.info("Session was reset on user's command.")
        self.ui_bus.dispatch_ui_update(
            ui_events.Info(
                "Session was reset. Start conversation to create a new session.",
            ),
        )
