"""Central registry for managing subcommands."""

from typing import Optional

import typed_argparse as tap

from streetrace.log import get_logger

from .base_subcommand import BaseSubcommand

logger = get_logger(__name__)


class SubcommandRegistry:
    """Central registry for managing subcommands.

    This class implements a singleton pattern to provide global access
    to the subcommand registry throughout the application.
    """

    _instance: Optional["SubcommandRegistry"] = None
    _initialized: bool = False

    def __new__(cls) -> "SubcommandRegistry":
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the registry (only once)."""
        if not self._initialized:
            self._subcommands: dict[str, BaseSubcommand] = {}
            self._initialized = True
            logger.debug("SubcommandRegistry initialized")

    @classmethod
    def instance(cls) -> "SubcommandRegistry":
        """Get the singleton instance of the registry."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, subcommand: BaseSubcommand) -> None:
        """Register a subcommand.

        Args:
            subcommand: The subcommand instance to register.

        Raises:
            ValueError: If a subcommand with the same name is already registered.

        """
        name = subcommand.name

        if name in self._subcommands:
            existing_type = type(self._subcommands[name]).__name__
            new_type = type(subcommand).__name__
            msg = (
                f"Subcommand '{name}' is already registered by {existing_type}. "
                f"Cannot register {new_type}."
            )
            raise ValueError(msg)

        self._subcommands[name] = subcommand
        logger.debug("Registered subcommand '%s' (%s)", name, type(subcommand).__name__)

    def get_subcommand(self, name: str) -> BaseSubcommand | None:
        """Get a subcommand by name.

        Args:
            name: The name of the subcommand to retrieve.

        Returns:
            The subcommand instance if found, None otherwise.

        """
        return self._subcommands.get(name)

    def list_subcommands(self) -> list[str]:
        """List all registered subcommand names.

        Returns:
            A list of registered subcommand names.

        """
        return list(self._subcommands.keys())

    def execute_subcommand(self, name: str, args: tap.TypedArgs) -> None:
        """Execute a subcommand with parsed arguments.

        Args:
            name: The name of the subcommand to execute.
            args: Parsed arguments for the subcommand.

        Raises:
            ValueError: If the subcommand is not found.

        """
        subcommand = self.get_subcommand(name)
        if subcommand is None:
            available = ", ".join(self.list_subcommands())
            msg = f"Unknown subcommand '{name}'. Available subcommands: {available}"
            raise ValueError(msg)

        logger.info("Executing subcommand '%s'", name)
        subcommand.execute(args)
