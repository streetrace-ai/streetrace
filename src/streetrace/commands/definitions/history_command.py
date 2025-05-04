"""Implement the history command for displaying conversation history.

This module defines the HistoryCommand class which allows users to view
the current conversation history in the interactive mode.
"""

import logging

# Import Application for type hint only
from typing import TYPE_CHECKING

from streetrace.commands.base_command import Command

if TYPE_CHECKING:
    from streetrace.application import Application

logger = logging.getLogger(__name__)


class HistoryCommand(Command):
    """Command to display the conversation history."""

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["history"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Display the conversation history."

    def execute(self, app_instance: "Application") -> bool:
        """Execute the history display action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        Returns:
            Always True to signal the application should continue.

        """
        logger.info("Executing history command.")
        # Access HistoryManager through the Application instance
        if not hasattr(app_instance, "history_manager"):
            logger.error("Application instance is missing the history_manager.")
            app_instance.ui.display_error("Internal error: History manager not found.")
            return True  # Still continue, but report error

        history_manager = app_instance.history_manager

        # Ensure the method exists on the history manager
        if not (
            hasattr(history_manager, "display_history")
            and callable(history_manager.display_history)
        ):
            logger.error(
                "HistoryManager instance is missing the display_history method.",
            )
            app_instance.ui.display_error(
                "Internal error: History display function not found.",
            )
            return True  # Still continue, but report error

        # Call the method on the history manager
        history_manager.display_history()

        # Command itself doesn't dictate loop continuation, just performs action
        return True
