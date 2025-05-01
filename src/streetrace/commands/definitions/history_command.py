"""Implement the history command for displaying conversation history.

This module defines the HistoryCommand class which allows users to view
the current conversation history in the interactive mode.
"""

import logging

from streetrace.application import Application
from streetrace.commands.base_command import Command

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

    def execute(self, app_instance: Application) -> bool:
        """Execute the history display action on the application instance.

        Args:
            app_instance: The main Application instance.

        Returns:
            True to signal the application should continue.
            Logs an error if the app_instance doesn't have the required method.

        """
        logger.info("Executing history command.")
        app_instance.display_history()
        return True
