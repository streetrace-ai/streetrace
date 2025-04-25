# src/streetrace/commands/definitions/history_command.py
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
        """Executes the history display action on the application instance.

        Args:
            app_instance: The main Application instance.

        Returns:
            True to signal the application should continue.
            Logs an error if the app_instance doesn't have the required method.

        """
        logger.info("Executing history command.")
        assert hasattr(app_instance, "_display_history")
        assert callable(
            app_instance._display_history,
        )
        app_instance._display_history()
        return True  # Signal continue after displaying history
