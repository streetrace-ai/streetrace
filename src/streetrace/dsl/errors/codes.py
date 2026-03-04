"""Error code definitions for Streetrace DSL compiler.

Provide standardized error codes following compiler conventions for
categorizing and identifying specific error conditions.
"""

from enum import Enum

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

    E0012 = "E0012"
    """Escalate continue used outside loop context."""

    E0013 = "E0013"
    """Prompt has no body after merging all definitions."""

    E0014 = "E0014"
    """Conflicting prompt modifier values."""

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


