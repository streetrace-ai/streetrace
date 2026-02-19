"""Error code definitions for Streetrace DSL compiler.

Provide standardized error codes following compiler conventions for
categorizing and identifying specific error conditions.
"""

from enum import Enum

from streetrace.log import get_logger

logger = get_logger(__name__)

# Error code category boundaries
_REFERENCE_MAX = 3
"""Maximum error code number for reference errors."""

_TYPE_CODE = 4
"""Error code number for type errors."""

_IMPORT_MAX = 6
"""Maximum error code number for import errors."""

_SYNTAX_MAX = 8
"""Maximum error code number for syntax errors."""


class ErrorCode(str, Enum):
    """DSL compiler error codes.

    Error codes follow the convention E0001-E9999 where the prefix
    indicates the error category:
    - E00xx: Reference errors (undefined symbols)
    - E01xx: Scope errors (variable visibility)
    - E02xx: Type errors
    - E03xx: Import errors
    - E04xx: Syntax errors
    - E05xx: Semantic errors
    """

    # Reference errors (E00xx)
    E0001 = "E0001"
    """Undefined reference to model, tool, agent, or prompt."""

    E0002 = "E0002"
    """Variable used before definition."""

    E0003 = "E0003"
    """Duplicate definition (variable redefinition in same scope)."""

    # Type errors (E02xx)
    E0004 = "E0004"
    """Type mismatch in expression."""

    # Import errors (E03xx)
    E0005 = "E0005"
    """Import file not found."""

    E0006 = "E0006"
    """Circular import detected."""

    # Syntax errors (E04xx)
    E0007 = "E0007"
    """Invalid token or unexpected end of input."""

    E0008 = "E0008"
    """Mismatched indentation."""

    # Semantic errors (E05xx)
    E0009 = "E0009"
    """Invalid guardrail action for context."""

    E0010 = "E0010"
    """Missing required property."""

    E0011 = "E0011"
    """Circular agent reference detected."""

    E0015 = "E0015"
    """Prompt references undefined variable."""

    E0016 = "E0016"
    """Instruction prompt references runtime variable."""

    # Warning codes (W0xxx)
    W0002 = "W0002"
    """Agent has both delegate and use properties (unusual pattern)."""

    @property
    def category(self) -> str:
        """Get the error category for this code.

        Returns:
            Human-readable category name.

        """
        code_num = int(self.value[1:])
        if code_num <= _REFERENCE_MAX:
            return "reference"
        if code_num == _TYPE_CODE:
            return "type"
        if code_num <= _IMPORT_MAX:
            return "import"
        if code_num <= _SYNTAX_MAX:
            return "syntax"
        return "semantic"


# Error message templates for each code
ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.E0001: "undefined reference to {kind} '{name}'",
    ErrorCode.E0002: "variable '${name}' used before definition",
    ErrorCode.E0003: "duplicate definition of {kind} '{name}'",
    ErrorCode.E0004: "type mismatch: expected {expected}, got {actual}",
    ErrorCode.E0005: "import file not found: {path}",
    ErrorCode.E0006: "circular import detected: {cycle}",
    ErrorCode.E0007: "invalid token or unexpected end of input",
    ErrorCode.E0008: "mismatched indentation",
    ErrorCode.E0009: "invalid guardrail action '{action}' in {context} context",
    ErrorCode.E0010: "missing required property '{field}' in {kind}",
    ErrorCode.E0011: "circular agent reference detected: {cycle}",
    ErrorCode.E0015: "prompt '{prompt}' references undefined variable '${name}'",
    ErrorCode.E0016: "instruction '{prompt}' references runtime variable '${name}'",
    ErrorCode.W0002: "agent '{name}' has both delegate and use (unusual pattern)",
}


def format_error_message(code: ErrorCode, **kwargs: str) -> str:
    """Format an error message with the given parameters.

    Args:
        code: The error code.
        **kwargs: Parameters to substitute in the message template.

    Returns:
        Formatted error message string.

    """
    template = ERROR_MESSAGES.get(code, "unknown error")
    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.warning("Missing parameter for error message: %s", e)
        return template
