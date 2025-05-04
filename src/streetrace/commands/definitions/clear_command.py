"""Implement the clear command for resetting conversation history.

This module defines the ClearCommand class which allows users to clear
the current conversation history in the interactive mode.
"""

import logging

# Import Application for type hint only, avoid circular dependency if possible
from typing import TYPE_CHECKING

from streetrace.commands.base_command import Command

if TYPE_CHECKING:
    from streetrace.application import Application  # Use for type hinting

logger = logging.getLogger(__name__)


class ClearCommand(Command):
    """Command to clear the conversation history, resetting it to the initial state."""

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["clear"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Clear conversation history and start over from the initial system message and context."

    def execute(self, app_instance: "Application") -> bool:
        """Execute the history clearing action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        Returns:
            Always True to signal the application should continue.
            The clearing action itself happens in the HistoryManager.

        """
        logger.info("Executing clear command.")
        # Access HistoryManager through the Application instance
        if not hasattr(app_instance, "history_manager"):
            logger.error("Application instance is missing the history_manager.")
            app_instance.ui.display_error("Internal error: History manager not found.")
            return True  # Still continue, but report error

        history_manager = app_instance.history_manager

        # Ensure the method exists on the history manager
        if not (
            hasattr(history_manager, "clear_history")
            and callable(history_manager.clear_history)
        ):
            logger.error(
                "HistoryManager instance is missing the clear_history method.",
            )
            app_instance.ui.display_error(
                "Internal error: History clear function not found.",
            )
            return True  # Still continue, but report error

        # Call the method on the history manager
        history_manager.clear_history()

        # Command itself doesn't dictate loop continuation, just performs action
        return True
