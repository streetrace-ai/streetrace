"""Custom indenter for Streetrace DSL.

Generate _INDENT and _DEDENT tokens based on indentation level changes,
enabling Python-style indentation-based block structure.
"""

from typing import ClassVar

from lark.indenter import Indenter

from streetrace.log import get_logger

logger = get_logger(__name__)


class StreetraceIndenter(Indenter):
    """Custom indenter for Streetrace DSL.

    Generate _INDENT and _DEDENT tokens based on indentation level changes.
    This enables Python-style indentation for prompt bodies and colon blocks.
    """

    NL_type = "_NL"
    """Token type for newlines."""

    OPEN_PAREN_types: ClassVar[list[str]] = ["LPAR", "LSQB", "LBRACE"]
    """Token types for opening parentheses/brackets/braces."""

    CLOSE_PAREN_types: ClassVar[list[str]] = ["RPAR", "RSQB", "RBRACE"]
    """Token types for closing parentheses/brackets/braces."""

    INDENT_type = "_INDENT"
    """Token type for indent."""

    DEDENT_type = "_DEDENT"
    """Token type for dedent."""

    tab_len = 4
    """Number of spaces a tab represents."""
