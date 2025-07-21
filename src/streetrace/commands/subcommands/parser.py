"""Parser that handles subcommand routing."""

import sys
from collections.abc import Callable
from typing import Any

import typed_argparse as tap

from streetrace.args import Args
from streetrace.log import get_logger

from .registry import SubcommandRegistry

logger = get_logger(__name__)

MIN_SUBCOMMAND_LENGTH = 3


class SubcommandParser:
    """Parser that handles subcommand routing.

    This class integrates with typed_argparse to detect subcommand invocations
    and route them to the appropriate subcommand handlers, while falling back
    to the main application for non-subcommand invocations.
    """

    def __init__(self, registry: SubcommandRegistry | None = None) -> None:
        """Initialize the subcommand parser.

        Args:
            registry: The subcommand registry to use. If None, uses the singleton
                instance.

        """
        self.registry = registry or SubcommandRegistry.instance()

    def is_subcommand(self, command: str) -> bool:
        """Check if a command is a registered subcommand.

        Args:
            command: The command name to check.

        Returns:
            True if the command is a registered subcommand, False otherwise.

        """
        return command in self.registry.list_subcommands()

    def _looks_like_subcommand(self, command: str) -> bool:
        """Check if a command looks like it might be intended as a subcommand.

        This helps distinguish between invalid subcommands and natural language prompts.

        Args:
            command: The command to check.

        Returns:
            True if the command looks like it might be intended as a subcommand.

        """
        # Don't treat flags (starting with - or --) as subcommands
        if command.startswith("-"):
            return False

        # Single words with no spaces that are lowercase and contain hyphens or
        # underscores are likely intended as subcommands
        if " " in command:
            return False

        # Commands that look like typical CLI subcommands
        if "-" in command or "_" in command:
            return True

        # Single lowercase words that don't look like natural language
        return bool(command.islower() and len(command) > MIN_SUBCOMMAND_LENGTH)

    def parse_and_execute(
        self,
        argv: list[str] | None = None,
        main_app_handler: Callable[[Any], None] | None = None,
    ) -> None:
        """Parse arguments and execute appropriate subcommand or main app.

        This method examines the command line arguments to determine if a subcommand
        is being invoked. If so, it parses the subcommand-specific arguments and
        executes the subcommand. Otherwise, it falls back to the main application.

        Args:
            argv: Command line arguments. If None, uses sys.argv.
            main_app_handler: Function to call for non-subcommand invocations.

        """
        if argv is None:
            argv = sys.argv[1:]  # Skip the script name

        # If no arguments, fall back to main app
        if not argv:
            if main_app_handler:
                # We need to create empty args for the main app
                empty_args = Args(
                    model=None,
                    command=None,
                    arbitrary_prompt=[],
                )
                main_app_handler(empty_args)
            return

        # Check if the first argument is a subcommand before parsing
        potential_subcommand = argv[0]

        if self.is_subcommand(potential_subcommand):
            # It's a subcommand, execute it directly
            self._execute_subcommand(potential_subcommand, argv[1:])
        elif self._looks_like_subcommand(potential_subcommand) and len(argv) == 1:
            # Looks like an invalid subcommand (single word with no additional args)
            available = ", ".join(self.registry.list_subcommands())
            sys.stderr.write(f"Error: Unknown subcommand '{potential_subcommand}'\n")
            sys.stderr.write(f"Available subcommands: {available}\n")
            sys.exit(1)
        else:
            # Not a subcommand, parse with main Args class and run main app
            try:
                parser = tap.Parser(Args)
                args = parser.parse_args(argv)

                if main_app_handler:
                    main_app_handler(args)
                else:
                    logger.warning(
                        "No main app handler provided for non-subcommand invocation",
                    )
            except SystemExit as e:
                # typed_argparse calls sys.exit on parse errors or --help
                # We need to let it propagate to maintain expected CLI behavior
                sys.exit(e.code)

    def _execute_subcommand(
        self, subcommand_name: str, subcommand_argv: list[str],
    ) -> None:
        """Execute a specific subcommand with its arguments.

        Args:
            subcommand_name: The name of the subcommand to execute.
            subcommand_argv: Arguments specific to the subcommand.

        """
        subcommand = self.registry.get_subcommand(subcommand_name)
        if subcommand is None:
            available = ", ".join(self.registry.list_subcommands())
            sys.stderr.write(f"Error: Unknown subcommand '{subcommand_name}'\n")
            sys.stderr.write(f"Available subcommands: {available}\n")
            sys.exit(1)

        try:
            # Get the argument parser class for this subcommand
            args_class = subcommand.create_parser()

            # Parse the subcommand-specific arguments
            parser = tap.Parser(args_class)
            parsed_args = parser.parse_args(subcommand_argv)

            # Execute the subcommand
            self.registry.execute_subcommand(subcommand_name, parsed_args)

        except SystemExit as e:
            # typed_argparse calls sys.exit on parse errors or --help
            # Let it propagate with the same exit code
            sys.exit(e.code)
        except Exception as e:
            logger.exception("Error executing subcommand '%s'", subcommand_name)
            sys.stderr.write(f"Error executing subcommand '{subcommand_name}': {e}\n")
            sys.exit(1)
