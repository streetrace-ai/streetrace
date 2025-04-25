# src/streetrace/commands/definitions/compact_command.py
import logging

from streetrace.application import Application
from streetrace.commands.base_command import Command

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

    def execute(self, app_instance: Application) -> bool:
        """Executes the history compaction action on the application instance.

        Args:
            app_instance: The main Application instance.

        Returns:
            The boolean result from app_instance._compact_history(), typically True
            to signal the application should continue, unless an unrecoverable
            error occurred within the compaction logic itself (though currently
            it always returns True).
            Logs an error if the app_instance doesn't have the required method.

        """
        logger.info("Executing compact command.")
        # Ensure the method exists before calling
        if not (
            hasattr(app_instance, "_compact_history")
            and callable(app_instance._compact_history)
        ):
            logger.error("Application instance is missing the _compact_history method.")
            # Decide on behavior: maybe return False to signal an issue?
            # For now, let's stick to the previous behavior of continuing, but log error.
            # If we expected execute() to potentially stop the app, we might return False here.
            return True  # Or potentially False if this is critical

        # Call the method and return its result
        return app_instance._compact_history()
