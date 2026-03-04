"""Custom exception hook for DSL stack trace translation.

Provide a custom exception hook that translates Python stack traces
to reference the original DSL source files using source maps.
"""

import sys
import traceback
from io import StringIO
from types import TracebackType

from streetrace.dsl.sourcemap.registry import SourceMapRegistry
from streetrace.log import get_logger

logger = get_logger(__name__)

# Store the original excepthook
_original_excepthook = sys.excepthook
_installed = False


def install_excepthook(registry: SourceMapRegistry) -> None:
    """Install custom exception hook for stack trace translation.

    Replace sys.excepthook with a custom handler that translates
    stack frames from generated Python code to original DSL files.

    Args:
        registry: Source map registry for frame translation.

    """
    global _installed  # noqa: PLW0603

    if _installed:
        logger.debug("Exception hook already installed")
        return

    def streetrace_excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        """Translate and display traceback with source map.

        Args:
            exc_type: Exception type.
            exc_value: Exception instance.
            exc_tb: Traceback object.

        """
        # Translate the traceback
        translated = translate_traceback(exc_tb, registry)

        # Print the translated traceback
        print_translated_traceback(translated, exc_type, exc_value)

    sys.excepthook = streetrace_excepthook
    _installed = True
    logger.debug("Installed DSL exception hook")


def uninstall_excepthook() -> None:
    """Restore the original exception hook."""
    global _installed  # noqa: PLW0603

    if _installed:
        sys.excepthook = _original_excepthook
        _installed = False
        logger.debug("Uninstalled DSL exception hook")


class TranslatedFrame:
    """A translated stack frame with DSL source information."""

    def __init__(  # noqa: PLR0913
        self,
        filename: str,
        lineno: int,
        name: str,
        line: str | None = None,
        *,
        is_dsl_frame: bool = False,
        original_filename: str | None = None,
        original_lineno: int | None = None,
    ) -> None:
        """Initialize translated frame.

        Args:
            filename: Display filename (DSL or Python).
            lineno: Line number.
            name: Function/context name.
            line: Source line content (optional).
            is_dsl_frame: True if this frame was translated from DSL.
            original_filename: Original generated Python filename.
            original_lineno: Original generated line number.

        """
        self.filename = filename
        self.lineno = lineno
        self.name = name
        self.line = line
        self.is_dsl_frame = is_dsl_frame
        self.original_filename = original_filename
        self.original_lineno = original_lineno


def translate_traceback(
    tb: TracebackType | None,
    registry: SourceMapRegistry,
) -> list[TranslatedFrame]:
    """Translate a Python traceback using source maps.

    Args:
        tb: Python traceback object.
        registry: Source map registry for lookups.

    Returns:
        List of translated frames.

    """
    frames: list[TranslatedFrame] = []

    while tb is not None:
        frame = tb.tb_frame
        code = frame.f_code
        lineno = tb.tb_lineno

        # Check if this is a generated DSL file
        if code.co_filename.startswith("<dsl:"):
            # Try to translate using source map
            mapping = registry.lookup(code.co_filename, lineno)
            if mapping is not None:
                frames.append(
                    TranslatedFrame(
                        filename=mapping.source_file,
                        lineno=mapping.source_line,
                        name=code.co_name,
                        is_dsl_frame=True,
                        original_filename=code.co_filename,
                        original_lineno=lineno,
                    ),
                )
            else:
                # No mapping found, show as-is but mark as DSL
                frames.append(
                    TranslatedFrame(
                        filename=code.co_filename,
                        lineno=lineno,
                        name=code.co_name,
                        is_dsl_frame=True,
                    ),
                )
        else:
            # Regular Python frame
            frames.append(
                TranslatedFrame(
                    filename=code.co_filename,
                    lineno=lineno,
                    name=code.co_name,
                    is_dsl_frame=False,
                ),
            )

        tb = tb.tb_next

    return frames


def print_translated_traceback(
    frames: list[TranslatedFrame],
    exc_type: type[BaseException],
    exc_value: BaseException,
) -> None:
    """Print a formatted translated traceback.

    Args:
        frames: List of translated frames.
        exc_type: Exception type.
        exc_value: Exception instance.

    """
    output = StringIO()

    output.write("Traceback (most recent call last):\n")

    for frame in frames:
        frame_line = (
            f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}\n'
        )
        output.write(frame_line)

        if frame.is_dsl_frame:
            if frame.line:
                output.write(f"    {frame.line}\n")
        else:
            # Try to get the actual source line
            try:
                import linecache
                source_line = linecache.getline(frame.filename, frame.lineno).strip()
                if source_line:
                    output.write(f"    {source_line}\n")
            except OSError:
                # File may not exist or be readable - skip source line
                logger.debug("Could not read source line from %s", frame.filename)

    # Format the exception
    exc_lines = traceback.format_exception_only(exc_type, exc_value)
    for line in exc_lines:
        output.write(line)

    # Print to stderr
    print(output.getvalue(), file=sys.stderr, end="")  # noqa: T201


def format_exception_with_source_map(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: TracebackType | None,
    registry: SourceMapRegistry,
) -> str:
    """Format an exception with source map translation.

    Args:
        exc_type: Exception type.
        exc_value: Exception instance.
        exc_tb: Traceback object.
        registry: Source map registry.

    Returns:
        Formatted traceback string.

    """
    frames = translate_traceback(exc_tb, registry)

    output = StringIO()
    output.write("Traceback (most recent call last):\n")

    for frame in frames:
        frame_line = (
            f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}\n'
        )
        output.write(frame_line)
        if frame.line:
            output.write(f"    {frame.line}\n")

    exc_lines = traceback.format_exception_only(exc_type, exc_value)
    for line in exc_lines:
        output.write(line)

    return output.getvalue()
