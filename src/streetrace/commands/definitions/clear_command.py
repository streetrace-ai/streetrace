"""Implement the clear command for resetting conversation history.

This module defines the ClearCommand class which allows users to clear
the current conversation history in the interactive mode.
"""

import logging

# Import Application for type hint only, avoid circular dependency if possible
from typing import TYPE_CHECKING, override

from streetrace.commands.base_command import Command

if TYPE_CHECKING:
    from streetrace.app import Application  # Use for type hinting

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

    @override
    def execute(self, app_instance: "Application") -> None:
        """Execute the history clearing action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        """
        logger.info("Executing clear command.")
        app_instance.history_manager.clear_history()
