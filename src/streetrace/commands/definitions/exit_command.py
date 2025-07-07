"""Implement the exit command for terminating the application.

This module defines the ExitCommand class which allows users to exit
the application in interactive mode.
"""

from typing import override

from streetrace.commands.base_command import Command
from streetrace.log import get_logger

logger = get_logger(__name__)


class ExitCommand(Command):
    """Command to signal the application to exit the interactive session.

    Handles both /exit and /quit.
    """

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["exit", "quit", "bye"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Exit the interactive session."

    @override
    async def execute_async(self) -> None:
        """Signal the application to stop.

        Raises:
            SystemExit to signal exit.

        """
        logger.info("Leaving...")
        raise SystemExit
