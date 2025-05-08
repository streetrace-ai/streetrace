"""StreetRace🚗💨 CLI entry point."""
import asyncio

from streetrace.app import run_app
from streetrace.args import Args, bind_and_run
from streetrace.log import get_logger, init_logging


def main(args: Args) -> None:
    """Configure and run the Application."""
    init_logging(args)
    logger = get_logger(__name__)
    try:
        asyncio.run(run_app(args))
    except Exception as app_err:
        msg = f"Critical error during application execution: {app_err}"
        logger.exception(msg)
        raise
    finally:
        logger.info("Application exiting.")


if __name__ == "__main__":
    bind_and_run(main)
