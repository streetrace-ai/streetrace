"""Configure subcommand implementation."""

import sys

import typed_argparse as tap

from streetrace.commands.subcommands.base_subcommand import BaseSubcommand

from .args import ConfigureArgs
from .manager import ConfigManager, show_usage


class ConfigureSubcommand(BaseSubcommand):
    """Configure subcommand implementation.

    This subcommand handles configuration management for streetrace,
    including local and global settings management.
    """

    @property
    def name(self) -> str:
        """The subcommand name."""
        return "configure"

    @property
    def description(self) -> str:
        """Brief description of the subcommand."""
        return "Configure streetrace settings"

    def create_parser(self) -> type[tap.TypedArgs]:
        """Create the typed_argparse Args class for this subcommand."""
        return ConfigureArgs

    def execute(self, args: ConfigureArgs) -> None:
        """Execute the configure subcommand.

        Args:
            args: Parsed configure-specific arguments.

        """
        config_manager = ConfigManager(args)

        # Validate argument combinations
        if args.show and not (args.global_ or args.local):
            sys.stderr.write("Error: --show requires either --global or --local\n")
            show_usage()
            return

        if args.reset and not (args.global_ or args.local):
            sys.stderr.write("Error: --reset requires either --global or --local\n")
            show_usage()
            return

        if args.global_ and args.local:
            sys.stderr.write("Error: Cannot specify both --global and --local\n")
            show_usage()
            return

        if not (args.show or args.reset or args.global_ or args.local):
            show_usage()
            return

        # Execute based on arguments
        if args.show:
            config_manager.show_config(is_global=args.global_)
        elif args.reset:
            config_manager.reset_config(is_global=args.global_)
        elif args.global_:
            config_manager.interactive_config(is_global=True)
        elif args.local:
            config_manager.interactive_config(is_global=False)
