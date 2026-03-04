"""Source map registry for Streetrace DSL.

Provide bidirectional mappings between generated Python line numbers
and original DSL file positions for error translation.
"""

import bisect
from dataclasses import dataclass, field

from streetrace.log import get_logger

logger = get_logger(__name__)


@dataclass
class SourceMapping:
    """Single mapping entry from generated code to source.

    Map a line in generated Python code back to its original
    position in the DSL source file.
    """

    generated_line: int
    """Line number in generated Python code (1-indexed)."""

    generated_column: int
    """Column number in generated Python code (0-indexed)."""

    source_file: str
    """Path to the original DSL source file."""

    source_line: int
    """Line number in the source file (1-indexed)."""

    source_column: int
    """Column number in the source file (0-indexed)."""

    source_end_line: int | None = None
    """End line for multi-line spans (optional)."""

    source_end_column: int | None = None
    """End column for multi-line spans (optional)."""


@dataclass
class _FileMappings:
    """Internal structure for storing mappings for a single file.

    Keep mappings sorted by generated line for efficient lookup.
    """

    mappings: list[SourceMapping] = field(default_factory=list)
    _sorted_lines: list[int] = field(default_factory=list)

    def add(self, mapping: SourceMapping) -> None:
        """Add a mapping, maintaining sorted order.

        Args:
            mapping: The source mapping to add.

        """
        # Insert in sorted position by generated line
        idx = bisect.bisect_left(self._sorted_lines, mapping.generated_line)
        self._sorted_lines.insert(idx, mapping.generated_line)
        self.mappings.insert(idx, mapping)

    def lookup(self, generated_line: int) -> SourceMapping | None:
        """Find the mapping for a generated line.

        Args:
            generated_line: Line number in generated code.

        Returns:
            The mapping at or before the line, or None if no mapping exists.

        """
        if not self._sorted_lines:
            return None

        # Find the rightmost mapping with line <= generated_line
        idx = bisect.bisect_right(self._sorted_lines, generated_line)
        if idx == 0:
            # Line is before all mappings
            return None

        return self.mappings[idx - 1]


class SourceMapRegistry:
    """Registry of source mappings for all compiled files.

    Maintain bidirectional mappings between generated Python code
    and original DSL source files for error translation.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._file_mappings: dict[str, _FileMappings] = {}
        logger.debug("Created SourceMapRegistry")

    def add_mapping(self, generated_file: str, mapping: SourceMapping) -> None:
        """Record a mapping for a generated file.

        Args:
            generated_file: Name/path of the generated Python file.
            mapping: The source mapping to record.

        """
        if generated_file not in self._file_mappings:
            self._file_mappings[generated_file] = _FileMappings()

        self._file_mappings[generated_file].add(mapping)
        logger.debug(
            "Added mapping: %s:%d -> %s:%d",
            generated_file,
            mapping.generated_line,
            mapping.source_file,
            mapping.source_line,
        )

    def lookup(
        self,
        generated_file: str,
        generated_line: int,
    ) -> SourceMapping | None:
        """Find source location for a generated line.

        Args:
            generated_file: Name/path of the generated Python file.
            generated_line: Line number in the generated code.

        Returns:
            The source mapping if found, None otherwise.

        """
        file_mappings = self._file_mappings.get(generated_file)
        if file_mappings is None:
            return None

        return file_mappings.lookup(generated_line)

    def get_mappings(self, generated_file: str) -> list[SourceMapping]:
        """Get all mappings for a generated file.

        Args:
            generated_file: Name/path of the generated Python file.

        Returns:
            List of all mappings for the file, sorted by generated line.

        """
        file_mappings = self._file_mappings.get(generated_file)
        if file_mappings is None:
            return []

        return list(file_mappings.mappings)

    def clear(self) -> None:
        """Clear all mappings from the registry."""
        self._file_mappings.clear()
        logger.debug("Cleared SourceMapRegistry")
