"""Handler for writing final response to output file."""

from pathlib import Path
from typing import override

from streetrace.input_handler import (
    HANDLED_CONT,
    SKIP,
    HandlerResult,
    InputContext,
    InputHandler,
)
from streetrace.log import get_logger

logger = get_logger(__name__)


class OutputFileHandler(InputHandler):
    """Handler that writes final response to output file."""

    def __init__(self, output_file: Path | None) -> None:
        """Initialize the output file handler.

        Args:
            output_file: Path to the output file, or None if not configured

        """
        self.output_file = output_file

    @override
    async def handle(self, ctx: InputContext) -> HandlerResult:
        """Write final response to output file if configured.

        Args:
            ctx: Input context containing the final response

        Returns:
            HandlerResult indicating handling result

        """
        # Skip if no output file configured
        if not self.output_file:
            return SKIP

        # Skip if no final response to write
        if not ctx.final_response:
            return SKIP

        try:
            # Write the final response to the output file (overwrite if exists)
            self.output_file.write_text(ctx.final_response, encoding="utf-8")
            logger.debug("Wrote final response to %s", self.output_file)
        except OSError as e:
            logger.exception("Failed to write output file %s", self.output_file)
            msg = f"Failed to write output file: {e}"
            raise OSError(msg) from e

        return HANDLED_CONT

