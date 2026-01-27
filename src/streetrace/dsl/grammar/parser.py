"""Parser factory for Streetrace DSL.

Create configured Lark parser instances supporting LALR (production)
and Earley (debug) parsing modes.
"""

from pathlib import Path
from typing import Literal

from lark import Lark

from streetrace.dsl.grammar.indenter import StreetraceIndenter
from streetrace.log import get_logger

logger = get_logger(__name__)

GRAMMAR_PATH = Path(__file__).parent / "streetrace.lark"
"""Path to the Streetrace DSL grammar file."""

ParserMode = Literal["lalr", "earley"]
"""Supported parser modes."""


class ParserFactory:
    """Factory for creating Streetrace DSL parser instances.

    Create configured Lark parser instances with the Streetrace grammar
    and custom indenter for handling Python-style indentation.

    Parser instances are cached because Earley parser construction is
    expensive (grammar analysis, FIRST/FOLLOW set computation).
    """

    _grammar_cache: str | None = None
    """Cached grammar content to avoid repeated file reads."""

    _parser_cache: Lark | None = None
    """Cached production parser instance (non-debug mode)."""

    @classmethod
    def _load_grammar(cls) -> str:
        """Load the grammar file contents.

        Returns:
            The grammar string.

        """
        if cls._grammar_cache is None:
            logger.debug("Loading grammar from %s", GRAMMAR_PATH)
            cls._grammar_cache = GRAMMAR_PATH.read_text()
        return cls._grammar_cache

    @classmethod
    def create(cls, *, debug: bool = False) -> Lark:
        """Create a Streetrace DSL parser.

        Args:
            debug: If True, enables additional debugging output and
                   returns a fresh parser instance (not cached).

        Returns:
            Configured Lark parser instance.

        Note:
            Currently uses Earley parser for all cases due to grammar
            complexity. Future optimization may enable LALR for production.

        """
        # Return cached parser for production (non-debug) mode
        # Debug mode always creates a fresh parser for explicit ambiguity
        if not debug and cls._parser_cache is not None:
            return cls._parser_cache

        # Use Earley parser for now - the grammar has some constructs
        # that cause LALR reduce/reduce conflicts. These will be resolved
        # in a future grammar refactoring phase.
        parser_type: ParserMode = "earley"
        logger.debug("Creating %s parser (debug=%s)", parser_type, debug)

        grammar = cls._load_grammar()

        parser = Lark(
            grammar,
            parser=parser_type,
            postlex=StreetraceIndenter(),
            propagate_positions=True,
            maybe_placeholders=False,
            ambiguity="resolve" if not debug else "explicit",
            keep_all_tokens=True,
        )

        # Cache the production parser for reuse
        if not debug:
            cls._parser_cache = parser

        return parser

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached parser state.

        Use for testing or when grammar may have changed.
        """
        cls._grammar_cache = None
        cls._parser_cache = None
