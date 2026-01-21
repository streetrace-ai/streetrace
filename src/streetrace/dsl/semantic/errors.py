"""Error definitions for Streetrace DSL semantic analysis.

Provide error classes and error codes for semantic analysis errors.
"""

from dataclasses import dataclass
from enum import Enum

from streetrace.dsl.ast.nodes import SourcePosition
from streetrace.log import get_logger

logger = get_logger(__name__)


class ErrorCode(Enum):
    """Semantic error codes following compiler conventions."""

    E0001 = "undefined reference to {kind} '{name}'"
    E0002 = "variable '{name}' used before definition"
    E0003 = "duplicate definition of {kind} '{name}'"
    E0004 = "type mismatch: expected {expected}, got {actual}"
    E0005 = "circular reference detected in {kind} '{name}'"
    E0006 = "invalid import: {message}"
    E0007 = "missing required field '{field}' in {kind}"
    E0008 = "mismatched indentation"
    E0009 = "scope error: {message}"
    E0010 = "missing required property '{property}' in {kind} '{name}'"


@dataclass
class SemanticError:
    """Semantic analysis error with location and context.

    Represents an error discovered during semantic analysis with
    detailed information for error reporting.
    """

    code: ErrorCode
    """Error code for categorization."""

    message: str
    """Human-readable error message."""

    position: SourcePosition | None = None
    """Source position where error occurred."""

    suggestion: str | None = None
    """Optional suggestion for fixing the error."""

    context_lines: list[str] | None = None
    """Optional source context lines for display."""

    @classmethod
    def undefined_reference(
        cls,
        kind: str,
        name: str,
        position: SourcePosition | None = None,
        *,
        suggestion: str | None = None,
    ) -> "SemanticError":
        """Create an undefined reference error.

        Args:
            kind: Kind of reference (model, tool, agent, etc.).
            name: Name that was not found.
            position: Source position of the error.
            suggestion: Optional suggestion for valid names.

        Returns:
            SemanticError instance.

        """
        msg = f"undefined reference to {kind} '{name}'"
        return cls(
            code=ErrorCode.E0001,
            message=msg,
            position=position,
            suggestion=suggestion,
        )

    @classmethod
    def undefined_variable(
        cls,
        name: str,
        position: SourcePosition | None = None,
    ) -> "SemanticError":
        """Create an undefined variable error.

        Args:
            name: Variable name that was not found.
            position: Source position of the error.

        Returns:
            SemanticError instance.

        """
        msg = f"variable '${name}' used before definition"
        return cls(
            code=ErrorCode.E0002,
            message=msg,
            position=position,
        )

    @classmethod
    def duplicate_definition(
        cls,
        kind: str,
        name: str,
        position: SourcePosition | None = None,
    ) -> "SemanticError":
        """Create a duplicate definition error.

        Args:
            kind: Kind of definition (model, tool, etc.).
            name: Name that was duplicated.
            position: Source position of the error.

        Returns:
            SemanticError instance.

        """
        msg = f"duplicate definition of {kind} '{name}'"
        return cls(
            code=ErrorCode.E0003,
            message=msg,
            position=position,
        )

    @classmethod
    def missing_required_property(
        cls,
        kind: str,
        name: str,
        prop: str,
        position: SourcePosition | None = None,
        *,
        suggestion: str | None = None,
    ) -> "SemanticError":
        """Create a missing required property error.

        Args:
            kind: Kind of definition (agent, prompt, etc.).
            name: Name of the definition missing the property.
            prop: Name of the missing required property.
            position: Source position of the error.
            suggestion: Optional suggestion for fixing.

        Returns:
            SemanticError instance.

        """
        msg = f"missing required property '{prop}' in {kind} '{name}'"
        return cls(
            code=ErrorCode.E0010,
            message=msg,
            position=position,
            suggestion=suggestion,
        )

    def format(self) -> str:
        """Format the error for display.

        Returns:
            Formatted error string.

        """
        parts = [f"error[{self.code.name}]: {self.message}"]

        if self.position is not None:
            parts.append(f"  --> line {self.position.line}:{self.position.column}")

        if self.suggestion is not None:
            parts.append(f"  = help: {self.suggestion}")

        return "\n".join(parts)
