"""Code emitter for Streetrace DSL code generation.

Manage Python code generation with indentation and line tracking
for source map generation.
"""

from streetrace.dsl.sourcemap.registry import SourceMapping
from streetrace.log import get_logger

logger = get_logger(__name__)

DEFAULT_INDENT = "    "
"""Default indentation string (4 spaces)."""

MIN_INDENT_LEVEL = 0
"""Minimum indentation level."""


class CodeEmitter:
    """Manage Python code generation with indentation and line tracking.

    Handle proper indentation, line counting, and source mapping
    generation for DSL to Python code transformation.
    """

    def __init__(
        self,
        source_file: str,
        *,
        indent_str: str = DEFAULT_INDENT,
    ) -> None:
        """Initialize a code emitter for a source file.

        Args:
            source_file: Path to the original DSL source file.
            indent_str: String to use for indentation.

        """
        self._lines: list[str] = []
        self._indent_level = 0
        self._indent_str = indent_str
        self._source_file = source_file
        self._source_mappings: list[SourceMapping] = []
        logger.debug("Created CodeEmitter for %s", source_file)

    def emit(self, code: str, source_line: int | None = None) -> None:
        """Emit a line of code with optional source mapping.

        Args:
            code: The code to emit (single line, no trailing newline).
            source_line: Optional source line number for mapping.

        """
        if source_line is not None:
            # Emit source comment before the code
            self._emit_source_comment(source_line)

        # Build the indented line
        indent = self._indent_str * self._indent_level
        self._lines.append(f"{indent}{code}")

        # Record source mapping if provided
        if source_line is not None:
            generated_line = len(self._lines)
            mapping = SourceMapping(
                generated_line=generated_line,
                generated_column=len(indent),
                source_file=self._source_file,
                source_line=source_line,
                source_column=0,
            )
            self._source_mappings.append(mapping)

    def _emit_source_comment(self, source_line: int) -> None:
        """Emit a source location comment.

        Args:
            source_line: The source line number.

        """
        indent = self._indent_str * self._indent_level
        self._lines.append(f"{indent}# {self._source_file}:{source_line}")

    def emit_comment(self, text: str) -> None:
        """Emit a comment line.

        Args:
            text: The comment text (without # prefix).

        """
        indent = self._indent_str * self._indent_level
        self._lines.append(f"{indent}# {text}")

    def emit_blank(self) -> None:
        """Emit a blank line."""
        self._lines.append("")

    def emit_raw(self, code: str) -> None:
        """Emit code without indentation.

        Args:
            code: The code to emit exactly as provided.

        """
        self._lines.append(code)

    def indent(self) -> None:
        """Increase indentation level."""
        self._indent_level += 1
        logger.debug("Indent level: %d", self._indent_level)

    def dedent(self) -> None:
        """Decrease indentation level."""
        if self._indent_level > MIN_INDENT_LEVEL:
            self._indent_level -= 1
        logger.debug("Indent level: %d", self._indent_level)

    def get_code(self) -> str:
        """Get the generated code as a string.

        Returns:
            The complete generated code with newlines.

        """
        if not self._lines:
            return ""
        return "\n".join(self._lines) + "\n"

    def get_source_mappings(self) -> list[SourceMapping]:
        """Get all source mappings.

        Returns:
            List of source mappings generated during emission.

        """
        return list(self._source_mappings)

    def get_line_count(self) -> int:
        """Get the current line count.

        Returns:
            Number of lines emitted so far.

        """
        return len(self._lines)

    def get_indent_level(self) -> int:
        """Get the current indentation level.

        Returns:
            Current indentation depth.

        """
        return self._indent_level
