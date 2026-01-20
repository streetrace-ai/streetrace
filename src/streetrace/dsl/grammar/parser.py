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
    """

    _grammar_cache: str | None = None
    """Cached grammar content to avoid repeated file reads."""

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
            debug: If True, enables additional debugging output.

        Returns:
            Configured Lark parser instance.

        Note:
            Currently uses Earley parser for all cases due to grammar
            complexity. Future optimization may enable LALR for production.

        """
        # Use Earley parser for now - the grammar has some constructs
        # that cause LALR reduce/reduce conflicts. These will be resolved
        # in a future grammar refactoring phase.
        parser_type: ParserMode = "earley"
        logger.debug("Creating %s parser (debug=%s)", parser_type, debug)

        grammar = cls._load_grammar()

        return Lark(
            grammar,
            parser=parser_type,
            postlex=StreetraceIndenter(),
            propagate_positions=True,
            maybe_placeholders=False,
            ambiguity="resolve" if not debug else "explicit",
            keep_all_tokens=True,
        )
