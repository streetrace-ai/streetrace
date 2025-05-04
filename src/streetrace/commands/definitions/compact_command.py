"""Implement the compact command for summarizing conversation history.

This module defines the CompactCommand class which allows users to compact
the current conversation history to reduce token usage while maintaining context.
"""

import logging

# Import Application for type hint only
from typing import TYPE_CHECKING

from streetrace.commands.base_command import Command

if TYPE_CHECKING:
    from streetrace.application import Application

logger = logging.getLogger(__name__)


class CompactCommand(Command):
    """Command to compact/summarize the conversation history to reduce token usage."""

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["compact"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Summarize conversation history to reduce token count while maintaining context."

    def execute(self, app_instance: "Application") -> bool:
        """Execute the history compaction action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        Returns:
            Always True to signal the application should continue.
            The compaction action itself happens in the HistoryManager.

        """
        logger.info("Executing compact command.")
        # Access HistoryManager through the Application instance
        if not hasattr(app_instance, "history_manager"):
            logger.error("Application instance is missing the history_manager.")
            app_instance.ui.display_error("Internal error: History manager not found.")
            return True  # Still continue, but report error

        history_manager = app_instance.history_manager

        # Ensure the method exists on the history manager
        if not (
            hasattr(history_manager, "compact_history")
            and callable(history_manager.compact_history)
        ):
            logger.error(
                "HistoryManager instance is missing the compact_history method.",
            )
            app_instance.ui.display_error(
                "Internal error: History compact function not found.",
            )
            return True  # Still continue, but report error

        # Call the method on the history manager
        history_manager.compact_history()

        # Command itself doesn't dictate loop continuation, just performs action
        return True
