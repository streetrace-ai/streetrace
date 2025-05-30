"""StreetRace🚗💨 CLI entry point."""

import asyncio

from streetrace.app import create_app
from streetrace.args import Args, bind_and_run
from streetrace.log import get_logger, init_logging


def main(args: Args) -> None:
    """Configure and run the Application."""
    init_logging(args)
    logger = get_logger(__name__)

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


def cli() -> None:
    """Entry point for the CLI."""
    bind_and_run(main)


if __name__ == "__main__":
    cli()
