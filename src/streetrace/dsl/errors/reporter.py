"""Error reporter for Streetrace DSL compiler.

Provide rustc-style error formatting with source context, carets,
and helpful suggestions.
"""

import json
from collections.abc import Mapping
from io import StringIO

from streetrace.dsl.errors.diagnostics import Diagnostic, Severity
from streetrace.log import get_logger

logger = get_logger(__name__)

GUTTER_WIDTH = 5
"""Width of the line number gutter."""

CONTEXT_LINES = 1
"""Number of context lines to show before/after error."""


class DiagnosticReporter:
    """Format and report diagnostic messages.

    Format diagnostics in rustc-style with source context, carets
    pointing to the error location, and helpful suggestions.
    """

    def __init__(self, source_cache: dict[str, str] | None = None) -> None:
        """Initialize the diagnostic reporter.

        Args:
            source_cache: Optional cache of file path to source content.

        """
        self._source_cache: dict[str, str] = source_cache or {}

    def add_source(self, file_path: str, source: str) -> None:
        """Add source content for a file.

        Args:
            file_path: Path to the source file.
            source: Content of the source file.

        """
        self._source_cache[file_path] = source

    def format_diagnostic(self, diagnostic: Diagnostic) -> str:
        """Format a single diagnostic in rustc-style.

        Args:
            diagnostic: The diagnostic to format.

        Returns:
            Formatted diagnostic string.

        Example output:
            error[E0001]: undefined reference to model 'fast'
              --> my_agent.sr:15:18
               |
            15 |     using model "fast"
               |                  ^^^^
               |
               = help: defined models are: main, compact

        """
        output = StringIO()

        # Header line: severity[code]: message
        self._write_header(output, diagnostic)

        # Location line: --> file:line:column
        self._write_location(output, diagnostic)

        # Source context with carets
        self._write_source_context(output, diagnostic)

        # Help text if present
        if diagnostic.help_text:
            self._write_help(output, diagnostic.help_text)

        # Related diagnostics (notes)
        for related in diagnostic.related:
            output.write("\n")
            self._write_note(output, related)

        return output.getvalue()

    def format_diagnostics(
        self,
        diagnostics: list[Diagnostic],
        *,
        include_summary: bool = True,
    ) -> str:
        """Format multiple diagnostics.

        Args:
            diagnostics: List of diagnostics to format.
            include_summary: Whether to include a summary line at the end.

        Returns:
            Formatted string with all diagnostics.

        """
        if not diagnostics:
            return ""

        output = StringIO()
        for i, diagnostic in enumerate(diagnostics):
            if i > 0:
                output.write("\n")
            output.write(self.format_diagnostic(diagnostic))

        if include_summary:
            output.write("\n")
            self._write_summary(output, diagnostics)

        return output.getvalue()

    def format_json(
        self,
        diagnostics: list[Diagnostic],
        file: str,
        *,
        stats: Mapping[str, int | str] | None = None,
    ) -> str:
        """Format diagnostics as JSON.

        Args:
            diagnostics: List of diagnostics.
            file: Primary file being checked.
            stats: Optional statistics about the file (int values for counts,
                   str values for error messages).

        Returns:
            JSON string representation.

        """
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        warnings = [d for d in diagnostics if d.severity == Severity.WARNING]

        result = {
            "version": "1.0",
            "file": file,
            "valid": len(errors) == 0,
            "errors": [d.to_dict() for d in errors],
            "warnings": [d.to_dict() for d in warnings],
        }

        if stats:
            result["stats"] = stats

        return json.dumps(result, indent=2)

    def _write_header(self, output: StringIO, diagnostic: Diagnostic) -> None:
        """Write the diagnostic header line.

        Args:
            output: Output buffer.
            diagnostic: The diagnostic.

        """
        severity = diagnostic.severity.value
        if diagnostic.code:
            output.write(f"{severity}[{diagnostic.code.value}]: {diagnostic.message}\n")
        else:
            output.write(f"{severity}: {diagnostic.message}\n")

    def _write_location(self, output: StringIO, diagnostic: Diagnostic) -> None:
        """Write the source location line.

        Args:
            output: Output buffer.
            diagnostic: The diagnostic.

        """
        # Columns are displayed 1-indexed for users
        col_display = diagnostic.column + 1
        output.write(f"  --> {diagnostic.file}:{diagnostic.line}:{col_display}\n")

    def _write_source_context(
        self,
        output: StringIO,
        diagnostic: Diagnostic,
    ) -> None:
        """Write source context with carets.

        Args:
            output: Output buffer.
            diagnostic: The diagnostic.

        """
        source = self._source_cache.get(diagnostic.file)
        if source is None:
            # No source available, just write empty gutter
            output.write(f"{' ' * GUTTER_WIDTH}|\n")
            return

        lines = source.split("\n")
        line_idx = diagnostic.line - 1  # Convert to 0-indexed

        if line_idx < 0 or line_idx >= len(lines):
            output.write(f"{' ' * GUTTER_WIDTH}|\n")
            return

        # Calculate display range
        start_idx = max(0, line_idx - CONTEXT_LINES)
        end_idx = min(len(lines), line_idx + CONTEXT_LINES + 1)

        # Empty gutter line before
        output.write(f"{' ' * GUTTER_WIDTH}|\n")

        # Write source lines
        for idx in range(start_idx, end_idx):
            line_num = idx + 1
            line_content = lines[idx]
            gutter = f"{line_num:>{GUTTER_WIDTH - 1}} "
            output.write(f"{gutter}| {line_content}\n")

            # Write caret line for the error line
            if idx == line_idx:
                self._write_caret_line(output, diagnostic, line_content)

        # Empty gutter line after
        output.write(f"{' ' * GUTTER_WIDTH}|\n")

    def _write_caret_line(
        self,
        output: StringIO,
        diagnostic: Diagnostic,
        source_line: str,
    ) -> None:
        """Write the caret line pointing to the error.

        Args:
            output: Output buffer.
            diagnostic: The diagnostic.
            source_line: The source line content.

        """
        # Calculate span length
        span_length = diagnostic.span_length
        if diagnostic.end_column is not None and diagnostic.end_line == diagnostic.line:
            span_length = max(1, diagnostic.end_column - diagnostic.column)
        else:
            # Try to guess span from source (find word boundary)
            span_length = self._guess_span_length(source_line, diagnostic.column)

        # Build caret line with proper spacing
        # Account for tabs in the source line
        col = diagnostic.column
        prefix = source_line[:col] if col < len(source_line) else ""
        # Replace non-tab characters with spaces, keep tabs
        spacing = "".join("\t" if c == "\t" else " " for c in prefix)

        carets = "^" * span_length
        gutter = " " * GUTTER_WIDTH
        output.write(f"{gutter}| {spacing}{carets}\n")

    def _guess_span_length(self, line: str, column: int) -> int:
        """Guess the span length for highlighting.

        Args:
            line: The source line.
            column: Start column.

        Returns:
            Guessed span length.

        """
        if column >= len(line):
            return 1

        # Find end of current word/token
        end = column
        while end < len(line) and not line[end].isspace():
            end += 1

        return max(1, end - column)

    def _write_help(self, output: StringIO, help_text: str) -> None:
        """Write help text.

        Args:
            output: Output buffer.
            help_text: The help text.

        """
        gutter = " " * GUTTER_WIDTH
        output.write(f"{gutter}= help: {help_text}\n")

    def _write_note(self, output: StringIO, diagnostic: Diagnostic) -> None:
        """Write a note diagnostic.

        Args:
            output: Output buffer.
            diagnostic: The note diagnostic.

        """
        # Notes are displayed inline with location
        col_display = diagnostic.column + 1
        output.write(
            f"note: {diagnostic.message}\n"
            f"  --> {diagnostic.file}:{diagnostic.line}:{col_display}\n",
        )

    def _write_summary(
        self,
        output: StringIO,
        diagnostics: list[Diagnostic],
    ) -> None:
        """Write a summary line.

        Args:
            output: Output buffer.
            diagnostics: List of all diagnostics.

        """
        errors = sum(1 for d in diagnostics if d.severity == Severity.ERROR)
        warnings = sum(1 for d in diagnostics if d.severity == Severity.WARNING)

        # Get unique files
        files = {d.file for d in diagnostics}
        file_count = len(files)

        if errors == 0 and warnings == 0:
            return

        parts = []
        if errors > 0:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings > 0:
            parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")

        summary = " and ".join(parts)

        if file_count == 1:
            file_name = next(iter(files))
            output.write(f"Found {summary} in {file_name}\n")
        else:
            output.write(f"Found {summary} in {file_count} files\n")


def format_success_message(
    file: str,  # noqa: ARG001
    *,
    models: int = 0,
    agents: int = 0,
    flows: int = 0,
    handlers: int = 0,
) -> str:
    """Format a success message for valid DSL file.

    Args:
        file: The file path (reserved for future use in message formatting).
        models: Number of model definitions.
        agents: Number of agent definitions.
        flows: Number of flow definitions.
        handlers: Number of event handlers.

    Returns:
        Formatted success message.

    """
    parts = []
    if models > 0:
        parts.append(f"{models} model{'s' if models != 1 else ''}")
    if agents > 0:
        parts.append(f"{agents} agent{'s' if agents != 1 else ''}")
    if flows > 0:
        parts.append(f"{flows} flow{'s' if flows != 1 else ''}")
    if handlers > 0:
        parts.append(f"{handlers} handler{'s' if handlers != 1 else ''}")

    if parts:
        stats = ", ".join(parts)
        return f"valid ({stats})"

    return "valid"
