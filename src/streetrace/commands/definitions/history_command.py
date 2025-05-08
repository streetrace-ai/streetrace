"""Implement the history command for displaying conversation history.

This module defines the HistoryCommand class which allows users to view
the current conversation history in the interactive mode.
"""

import logging

# Import Application for type hint only
from typing import TYPE_CHECKING, override

from streetrace.commands.base_command import Command

if TYPE_CHECKING:
    from streetrace.app import Application

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

    @override
    def execute(self, app_instance: "Application") -> None:
        """Execute the history display action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        """
        logger.info("Executing history command.")
        app_instance.history_manager.display_history()
