"""Logging helper module."""

from logging import (
    DEBUG,
    INFO,
    Formatter,
    Logger,
    StreamHandler,
    basicConfig,
    getLogger,
)

import litellm

from streetrace.args import Args


def init_logging(args: Args) -> None:
    """Initialize logging for the application.

    Should be called once when the application starts.
    """
    # --- Logging Configuration ---
    # Basic config for file logging
    basicConfig(
        level=INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="streetrace.log",
        filemode="w",
    )

    # Console handler for user-facing logs
    console_handler = StreamHandler()
    console_handler.setLevel(INFO)
    console_formatter = Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)

    root_logger = getLogger()
    configure_3p_loggers(root_logger)

    # Configure Logging Level based on args
    if args.verbose:
        # https://docs.litellm.ai/docs/debugging/local_debugging
        litellm._turn_on_debug()  # type: ignore[attr-defined,no-untyped-call] # noqa: SLF001
        # Add console handler only if debug is enabled
        # Root logger setup
        # Set root logger level to DEBUG initially to capture everything
        root_logger.setLevel(DEBUG)
        root_logger.info("Debug logging enabled.")
    else:
        litellm.suppress_debug_info = True
    # --- End Logging Configuration ---


def get_logger(name: str) -> Logger:
    """Proxy for logging.getLogger."""
    return getLogger(name)


def configure_3p_loggers(root_logger: Logger) -> None:
    """Configure the litellm logger to use the same handlers as the root logger."""
    for name in root_logger.manager.loggerDict:
        if name.startswith("streetrace"):
            continue  # Skip our own loggers
        # Disable console output for a specific third-party logger
        third_party_logger = getLogger(
            name,
        )  # Replace with the actual logger name
        third_party_logger.handlers.clear()  # Remove any existing handlers
