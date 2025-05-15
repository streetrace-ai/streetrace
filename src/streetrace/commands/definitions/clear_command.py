"""Implement the clear command for resetting conversation history.

This module defines the ClearCommand class which allows users to clear
the current conversation history in the interactive mode.
"""

# Import Application for type hint only, avoid circular dependency if possible
from typing import override

from streetrace.commands.base_command import Command
from streetrace.history import HistoryManager
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class ClearCommand(Command):
    """Command to clear the conversation history, resetting it to the initial state."""

    def __init__(self, ui_bus: UiBus, history_manager: HistoryManager) -> None:
        """Initialize a new instance of ClearCommand."""
        self.ui_bus = ui_bus
        self.history_manager = history_manager

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["clear"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Clear conversation history and start over from the initial system message and context."

    @override
    async def execute_async(self) -> None:
        """Execute the history clearing action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        """
        logger.info("Attempting to clear conversation history.")
        try:
            # Re-initialize history as if starting an interactive session
            self.history_manager.initialize_history()
            logger.info("Conversation history cleared successfully.")
            self.ui_bus.dispatch(ui_events.Info("Conversation history has been cleared."))
        except Exception as e:
            logger.exception("Failed to rebuild context while clearing history")
            self.ui_bus.dispatch(ui_events.Warn(
                f"Could not clear history due to an error: {e}",
            ))
