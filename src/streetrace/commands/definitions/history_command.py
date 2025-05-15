"""Implement the history command for displaying conversation history.

This module defines the HistoryCommand class which allows users to view
the current conversation history in the interactive mode.
"""

from typing import override

from streetrace.commands.base_command import Command
from streetrace.history import HistoryManager
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class HistoryCommand(Command):
    """Command to display the conversation history."""

    def __init__(self, ui_bus: UiBus, history_manager: HistoryManager) -> None:
        """Initialize a new instance of HistoryCommand."""
        self.ui_bus = ui_bus
        self.history_manager = history_manager

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
        history = self.history_manager.get_history()
        if history:
            self.ui_bus.dispatch_ui_update(history)
        else:
            self.ui_bus.dispatch_ui_update(ui_events.Info("No history available yet."))
