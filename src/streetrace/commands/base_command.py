"""Define the base class for all application commands.

This module provides the abstract base class that all command implementations must inherit from,
ensuring a consistent interface for command execution and description.
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from streetrace.application import Application

logger = logging.getLogger(__name__)


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
    def execute(self, app_instance: "Application") -> bool:
        """Execute the command's action.

        Args:
            app_instance: The main Application instance.
                          Commands can use this to access application state or methods.

        Returns:
            bool: False if the application should exit after execution,
                  True if the application should continue.

        """
