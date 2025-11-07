"""StreetRace🚗💨 CLI entry point."""

# Set protobuf implementation before any imports
import os

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import asyncio
from pathlib import Path

from dotenv import load_dotenv

from streetrace.app import create_app
from streetrace.args import Args, bind_and_run
from streetrace.log import get_logger, init_logging
from streetrace.telemetry import init_telemetry


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
from streetrace.version import show_version


def run(args: Args) -> None:
    """Configure and run the Application."""
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

    # Initialize telemetry after loading environment variables
    init_telemetry()

    init_logging(args)
    logger = get_logger(__name__)

    app = create_app(args)
    while True:
        try:
            asyncio.run(app.run())
        except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
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


def main() -> None:
    """Entry point for the CLI."""
    bind_and_run(run)


if __name__ == "__main__":
    main()
