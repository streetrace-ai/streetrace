"""Base class for all subcommands."""

from abc import ABC, abstractmethod

import typed_argparse as tap


class BaseSubcommand(ABC):
    """Abstract base class for all subcommands.

    Each subcommand must define its name, description, argument parser,
    and execution logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The subcommand name (e.g., 'configure').

        This name will be used to invoke the subcommand from the command line.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of the subcommand.

        This description will be shown in help messages.
        """

    @abstractmethod
    def create_parser(self) -> type[tap.TypedArgs]:
        """Create the typed_argparse Args class for this subcommand.

        Returns:
            A TypedArgs class that defines the arguments for this subcommand.

        """

    @abstractmethod
    def execute(self, args: tap.TypedArgs) -> None:
        """Execute the subcommand with parsed arguments.

        Args:
            args: Parsed arguments from the subcommand's argument parser.

        """
