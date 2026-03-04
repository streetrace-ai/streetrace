"""Semantic analysis module for Streetrace DSL.

Provide semantic analysis capabilities including reference validation,
variable scoping, type checking, and error reporting.
"""

from streetrace.dsl.semantic.analyzer import SemanticAnalyzer
from streetrace.dsl.semantic.errors import SemanticError
from streetrace.dsl.semantic.scope import Scope, ScopeType, Symbol, SymbolKind

__all__ = [
    "Scope",
    "ScopeType",
    "SemanticAnalyzer",
    "SemanticError",
    "Symbol",
    "SymbolKind",
]
