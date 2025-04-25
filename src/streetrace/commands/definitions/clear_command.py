# src/streetrace/commands/definitions/clear_command.py
import logging

from streetrace.application import Application
from streetrace.commands.base_command import Command

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

    def execute(self, app_instance: Application) -> bool:
        """Executes the history clearing action on the application instance.

        Args:
            app_instance: The main Application instance.

        Returns:
            True to signal the application should continue, unless an
            unrecoverable error occurred within the clearing logic itself.
            Logs an error if the app_instance doesn't have the required method.

        """
        logger.info("Executing clear command.")
        # Ensure the method exists before calling
        if not (
            hasattr(app_instance, "_clear_history")
            and callable(app_instance._clear_history)
        ):
            logger.error("Application instance is missing the _clear_history method.")
            # Continue execution, but log the error.
            return False  # Or potentially False if this is critical

        # Call the method and return its result
        # Assuming _clear_history also returns a boolean indicating continuation.
        should_continue = app_instance._clear_history()
        logger.info("Conversation history cleared.")
        return should_continue
