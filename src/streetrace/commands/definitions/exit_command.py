# src/streetrace/commands/definitions/exit_command.py
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

    # The app_instance is required by the base class but not used here.
    def execute(self, app_instance: Application) -> bool:
        """Signals the application to stop.

        Args:
            app_instance: The application instance (required by the interface but unused).

        Returns:
            False to signal exit.

        """
        logger.info("Leaving...")
        # Mark app_instance as unused if your linter supports it (e.g.,
        # Or simply don't refer to it.
        return False
