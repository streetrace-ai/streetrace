"""Configure subcommand implementation."""

import sys
from typing import cast

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

    def execute(self, args: tap.TypedArgs) -> None:
        """Execute the configure subcommand.

        Args:
            args: Parsed configure-specific arguments.

        """
        # Type cast since we know this will be ConfigureArgs from create_parser
        configure_args = cast("ConfigureArgs", args)
        config_manager = ConfigManager(configure_args)

        # Validate argument combinations
        if configure_args.show and not (configure_args.global_ or configure_args.local):
            sys.stderr.write("Error: --show requires either --global or --local\n")
            show_usage()
            return

        if configure_args.reset and not (
            configure_args.global_ or configure_args.local
        ):
            sys.stderr.write("Error: --reset requires either --global or --local\n")
            show_usage()
            return

        if configure_args.global_ and configure_args.local:
            sys.stderr.write("Error: Cannot specify both --global and --local\n")
            show_usage()
            return

        if not (
            configure_args.show
            or configure_args.reset
            or configure_args.global_
            or configure_args.local
        ):
            show_usage()
            return

        # Execute based on arguments
        if configure_args.show:
            config_manager.show_config(is_global=configure_args.global_)
        elif configure_args.reset:
            config_manager.reset_config(is_global=configure_args.global_)
        elif configure_args.global_:
            config_manager.interactive_config(is_global=True)
        elif configure_args.local:
            config_manager.interactive_config(is_global=False)
