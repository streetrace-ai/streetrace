"""Configure subcommand implementation."""

from pathlib import Path

import typed_argparse as tap

from streetrace.configure import ConfigManager, show_usage

from .base_subcommand import BaseSubcommand


class ConfigureArgs(tap.TypedArgs):
    """Arguments specific to the configure subcommand."""

    path: Path | None = tap.arg(help="Working directory", default=None)
    local: bool = tap.arg(help="Configure local settings", default=False)
    global_: bool = tap.arg(help="Configure global settings", default=False)
    show: bool = tap.arg(help="Show configuration settings", default=False)
    reset: bool = tap.arg(help="Reset configuration settings", default=False)

    @property
    def working_dir(self) -> Path:
        """Get working directory."""
        if self.path:
            work_dir = self.path
            if not work_dir.is_absolute():
                work_dir = Path.cwd().joinpath(work_dir).resolve()
        else:
            work_dir = Path.cwd().resolve()

        if not work_dir.is_dir():
            msg = (
                f"Specified path '{self.path}' resolved to '{work_dir}' which is "
                "not a valid directory."
            )
            raise ValueError(msg)

        return work_dir


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
            print("Error: --show requires either --global or --local")
            show_usage()
            return

        if args.reset and not (args.global_ or args.local):
            print("Error: --reset requires either --global or --local")
            show_usage()
            return

        if args.global_ and args.local:
            print("Error: Cannot specify both --global and --local")
            show_usage()
            return

        if not (args.show or args.reset or args.global_ or args.local):
            show_usage()
            return

        # Execute based on arguments
        if args.show:
            config_manager.show_config(args.global_)
        elif args.reset:
            config_manager.reset_config(args.global_)
        elif args.global_:
            config_manager.interactive_config(True)
        elif args.local:
            config_manager.interactive_config(False)
