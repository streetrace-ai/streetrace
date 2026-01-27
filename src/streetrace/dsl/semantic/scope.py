"""Scope tracking for Streetrace DSL semantic analysis.

Provide scope management for variable and symbol tracking during
semantic analysis. Supports hierarchical scopes with parent lookup.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.dsl.ast.nodes import AstNode

logger = get_logger(__name__)


class SymbolKind(Enum):
    """Kind of symbol in the symbol table."""

    MODEL = auto()
    SCHEMA = auto()
    TOOL = auto()
    PROMPT = auto()
    AGENT = auto()
    FLOW = auto()
    VARIABLE = auto()
    PARAMETER = auto()
    RETRY_POLICY = auto()
    TIMEOUT_POLICY = auto()


class ScopeType(Enum):
    """Type of scope for variable visibility rules."""

    GLOBAL = auto()
    FLOW = auto()
    HANDLER = auto()
    BLOCK = auto()


@dataclass
class Symbol:
    """Symbol entry in the symbol table.

    Represents a named entity that can be referenced in DSL code.
    """

    name: str
    """Name of the symbol."""

    kind: SymbolKind
    """Kind of symbol (model, tool, variable, etc.)."""

    defined_at: "AstNode | None" = None
    """AST node where this symbol was defined."""

    type_info: str | None = None
    """Optional type information for the symbol."""


@dataclass
class Scope:
    """Scope for tracking symbols and variables.

    Support hierarchical scopes with parent lookup for variable resolution.
    """

    scope_type: ScopeType
    """Type of this scope (global, flow, handler, block)."""

    parent: "Scope | None" = None
    """Parent scope for hierarchical lookup."""

    _symbols: dict[str, Symbol] = field(default_factory=dict)
    """Symbols defined in this scope."""

    def define(
        self,
        name: str,
        kind: SymbolKind,
        *,
        node: "AstNode | None" = None,
        type_info: str | None = None,
    ) -> Symbol:
        """Define a symbol in this scope.

        Args:
            name: Name of the symbol.
            kind: Kind of symbol.
            node: Optional AST node where symbol is defined.
            type_info: Optional type information.

        Returns:
            The created Symbol.

        """
        symbol = Symbol(
            name=name,
            kind=kind,
            defined_at=node,
            type_info=type_info,
        )
        self._symbols[name] = symbol
        logger.debug(
            "Defined symbol %s of kind %s in %s scope",
            name,
            kind.name,
            self.scope_type.name,
        )
        return symbol

    def lookup(self, name: str) -> Symbol | None:
        """Look up a symbol by name, searching parent scopes.

        Args:
            name: Name of the symbol to look up.

        Returns:
            The Symbol if found, None otherwise.

        """
        # Check current scope first
        if name in self._symbols:
            return self._symbols[name]
        # Check parent scope if available
        if self.parent is not None:
            return self.parent.lookup(name)
        return None

    def lookup_local(self, name: str) -> Symbol | None:
        """Look up a symbol only in the current scope.

        Args:
            name: Name of the symbol to look up.

        Returns:
            The Symbol if found in this scope, None otherwise.

        """
        return self._symbols.get(name)

    def is_defined_locally(self, name: str) -> bool:
        """Check if a symbol is defined in this scope only.

        Args:
            name: Name of the symbol to check.

        Returns:
            True if the symbol is defined locally, False otherwise.

        """
        return name in self._symbols

    def all_symbols(self) -> dict[str, Symbol]:
        """Return all symbols in this scope.

        Returns:
            Dictionary of symbol name to Symbol.

        """
        return dict(self._symbols)

    def symbols_of_kind(self, kind: SymbolKind) -> list[Symbol]:
        """Return all symbols of a specific kind.

        Args:
            kind: The kind of symbols to return.

        Returns:
            List of symbols matching the kind.

        """
        return [s for s in self._symbols.values() if s.kind == kind]
