"""Implement the exit command for terminating the application.

This module defines the ExitCommand class which allows users to exit
the application in interactive mode.
"""

import logging

from streetrace.application import Application
from streetrace.commands.base_command import Command

logger = logging.getLogger(__name__)


class ExitCommand(Command):
    """Command to signal the application to exit the interactive session.

    Handles both /exit and /quit.
    """

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["exit", "quit"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Exit the interactive session."

    def execute(self, _: Application) -> bool:
        """Signal the application to stop.

        Args:
            _: The application instance (required by the interface but unused).

        Returns:
            False to signal exit.

        """
        logger.info("Leaving...")
        return False
