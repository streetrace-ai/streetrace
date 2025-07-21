"""StreetRace🚗💨 CLI entry point."""

import asyncio
import sys
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

from streetrace.app import create_app
from streetrace.args import Args
from streetrace.commands.subcommands import (
    ConfigureSubcommand,
    SubcommandParser,
    SubcommandRegistry,
)
from streetrace.config_loader import load_model_from_config
from streetrace.log import get_logger, init_logging


def show_version() -> None:
    """Display the application version and exit."""
    try:
        app_version = version("streetrace")
        print(f"StreetRace🚗💨 {app_version}")  # noqa: T201
    except Exception:  # noqa: BLE001
        # Broad exception handling is acceptable here as we want to gracefully
        # handle any version lookup failures (missing package, corrupted metadata, etc.)
        print("StreetRace🚗💨 (version unknown)")  # noqa: T201
    sys.exit(0)


def run_main_app(args: Args) -> None:
    """Run the main application (non-subcommand mode)."""
    if args.version:
        show_version()

    cwd = Path.cwd()
    if not cwd.is_dir():
        msg = f"Current working directory is not a directory: {cwd}"
        raise NotADirectoryError(msg)
    load_dotenv(
        dotenv_path=cwd / ".env",
        override=True,
    )  # Load environment variables from .env file in the current directory
    init_logging(args)
    logger = get_logger(__name__)

    # Load model from configuration for the main app
    effective_model = load_model_from_config(args)
    if not effective_model:
        error_msg = (
            "Error: No model specified. Use --model argument or configure a model "
            "with 'streetrace configure --global' or 'streetrace configure --local'"
        )
        sys.stderr.write(f"{error_msg}\n")
        sys.exit(1)

    # Update args with effective model for the app
    args.model = effective_model
    app = create_app(args)
    while True:
        try:
            asyncio.run(app.run())
        except KeyboardInterrupt:
            # we treat keyboard interrupt as an interrupt to the current operation,
            # so we keep the app running.
            # if the current prompt is empty, then Ctrl+C will cause
            # SystemExit from KeyboardInterrupt
            continue
        except SystemExit:
            break
        except Exception as app_err:
            msg = f"Critical error during application execution: {app_err}"
            logger.exception(msg)
            raise


def setup_subcommands() -> None:
    """Register all available subcommands."""
    registry = SubcommandRegistry.instance()

    # Register the configure subcommand
    configure_subcommand = ConfigureSubcommand()
    registry.register(configure_subcommand)


def main() -> None:
    """Entry point for the CLI."""
    # Set up subcommands
    setup_subcommands()

    # Use SubcommandParser to handle routing
    parser = SubcommandParser()
    parser.parse_and_execute(main_app_handler=run_main_app)


if __name__ == "__main__":
    main()
