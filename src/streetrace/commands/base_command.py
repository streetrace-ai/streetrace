"""Define the base class for all application commands.

This module provides the abstract base class that all command implementations must
inherit from, ensuring a consistent interface for command execution and description.
"""

from abc import ABC, abstractmethod

from streetrace.log import get_logger

logger = get_logger(__name__)


class Command(ABC):
    """Abstract Base Class for all application commands.

    Each command must define its invocation names, description, and execution logic.
    """

    @property
    @abstractmethod
    def names(self) -> list[str]:
        """A list of names (without the leading '/') that can invoke this command.

        These names will be used case-insensitively.
        The first name in the list is considered the primary name.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """A short description of what the command does."""

    @abstractmethod
    async def execute_async(self, user_input: str) -> str | None:
        """Execute the command's action.

        Args:
            user_input: The raw input string from the user (e.g., "/exit").

        Returns:
            None or any output to send to the model.

        Raises:
            SystemExit: System exit requested by the command.

        """
