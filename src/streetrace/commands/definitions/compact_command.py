"""Implement the compact command for summarizing conversation history.

This module defines the CompactCommand class which allows users to compact
the current conversation history to reduce token usage while maintaining context.
"""

import logging

# Import Application for type hint only
from typing import TYPE_CHECKING, override

from streetrace.commands.base_command import Command

if TYPE_CHECKING:
    from streetrace.app import Application

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

    @override
    def execute(self, app_instance: "Application") -> None:
        """Execute the history compaction action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        """
        logger.info("Executing compact command.")
        app_instance.history_manager.compact_history()
