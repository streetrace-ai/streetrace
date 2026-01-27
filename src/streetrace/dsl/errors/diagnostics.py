"""Diagnostic message building for Streetrace DSL compiler.

Provide diagnostic dataclasses for representing compiler errors, warnings,
and notes with source location information.
"""

from dataclasses import dataclass, field
from enum import Enum

from streetrace.dsl.errors.codes import ErrorCode
from streetrace.log import get_logger

logger = get_logger(__name__)


class Severity(str, Enum):
    """Diagnostic severity levels."""

    ERROR = "error"
    """A compilation error that prevents code generation."""

    WARNING = "warning"
    """A potential issue that does not prevent compilation."""

    NOTE = "note"
    """Additional contextual information for another diagnostic."""


@dataclass
class Diagnostic:
    """A diagnostic message with source location.

    Represent a compiler diagnostic (error, warning, or note) with
    detailed source location information for rustc-style formatting.
    """

    severity: Severity
    """The severity level of this diagnostic."""

    message: str
    """The primary diagnostic message (no leading capital, no trailing period)."""

    file: str
    """Path to the source file."""

    line: int
    """Line number where the diagnostic occurs (1-indexed)."""

    column: int
    """Column number where the diagnostic starts (0-indexed)."""

    code: ErrorCode | None = None
    """Optional error code for categorization."""

    end_line: int | None = None
    """End line for multi-line spans (optional)."""

    end_column: int | None = None
    """End column for the span (optional)."""

    help_text: str | None = None
    """Optional help text with suggestions for fixing the issue."""

    related: list["Diagnostic"] = field(default_factory=list)
    """Related diagnostics (notes, suggestions) attached to this one."""

    @classmethod
    def error(  # noqa: PLR0913
        cls,
        message: str,
        file: str,
        line: int,
        column: int,
        *,
        code: ErrorCode | None = None,
        end_line: int | None = None,
        end_column: int | None = None,
        help_text: str | None = None,
    ) -> "Diagnostic":
        """Create an error diagnostic.

        Factory method with many optional parameters for full diagnostic control.

        Args:
            message: The error message.
            file: Source file path.
            line: Line number (1-indexed).
            column: Column number (0-indexed).
            code: Optional error code.
            end_line: Optional end line.
            end_column: Optional end column.
            help_text: Optional help text.

        Returns:
            A new Diagnostic with ERROR severity.

        """
        return cls(
            severity=Severity.ERROR,
            message=message,
            file=file,
            line=line,
            column=column,
            code=code,
            end_line=end_line,
            end_column=end_column,
            help_text=help_text,
        )

    @classmethod
    def warning(  # noqa: PLR0913
        cls,
        message: str,
        file: str,
        line: int,
        column: int,
        *,
        code: ErrorCode | None = None,
        help_text: str | None = None,
    ) -> "Diagnostic":
        """Create a warning diagnostic.

        Factory method with location and optional parameters for full control.

        Args:
            message: The warning message.
            file: Source file path.
            line: Line number (1-indexed).
            column: Column number (0-indexed).
            code: Optional error code.
            help_text: Optional help text.

        Returns:
            A new Diagnostic with WARNING severity.

        """
        return cls(
            severity=Severity.WARNING,
            message=message,
            file=file,
            line=line,
            column=column,
            code=code,
            help_text=help_text,
        )

    @classmethod
    def note(
        cls,
        message: str,
        file: str,
        line: int,
        column: int,
    ) -> "Diagnostic":
        """Create a note diagnostic.

        Args:
            message: The note message.
            file: Source file path.
            line: Line number (1-indexed).
            column: Column number (0-indexed).

        Returns:
            A new Diagnostic with NOTE severity.

        """
        return cls(
            severity=Severity.NOTE,
            message=message,
            file=file,
            line=line,
            column=column,
        )

    def with_help(self, help_text: str) -> "Diagnostic":
        """Add help text to this diagnostic.

        Args:
            help_text: The help text to add.

        Returns:
            Self for chaining.

        """
        self.help_text = help_text
        return self

    def with_note(
        self,
        message: str,
        file: str,
        line: int,
        column: int,
    ) -> "Diagnostic":
        """Add a related note to this diagnostic.

        Args:
            message: The note message.
            file: Source file path.
            line: Line number (1-indexed).
            column: Column number (0-indexed).

        Returns:
            Self for chaining.

        """
        self.related.append(
            Diagnostic.note(
                message=message,
                file=file,
                line=line,
                column=column,
            ),
        )
        return self

    @property
    def span_length(self) -> int:
        """Calculate the length of the diagnostic span.

        Returns:
            Length of the span in characters, or 1 if not determinable.

        """
        if self.end_column is not None and self.end_line == self.line:
            return max(1, self.end_column - self.column)
        return 1

    def to_dict(self) -> dict[str, object]:
        """Convert this diagnostic to a dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON output.

        """
        location: dict[str, str | int] = {
            "file": self.file,
            "line": self.line,
            "column": self.column,
        }

        if self.end_line is not None:
            location["end_line"] = self.end_line

        if self.end_column is not None:
            location["end_column"] = self.end_column

        result: dict[str, object] = {
            "severity": self.severity.value,
            "message": self.message,
            "location": location,
        }

        if self.code is not None:
            result["code"] = self.code.value

        if self.help_text is not None:
            result["help"] = self.help_text

        if self.related:
            result["related"] = [d.to_dict() for d in self.related]

        return result
