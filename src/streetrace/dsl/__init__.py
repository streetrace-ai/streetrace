"""Streetrace DSL compiler package.

Provide parsing, AST transformation, semantic analysis, and code generation
for the Streetrace Agent Definition Language.
"""

from streetrace.dsl.cache import BytecodeCache
from streetrace.dsl.cli import run_check, run_dump_python
from streetrace.dsl.codegen import CodeEmitter, CodeGenerator
from streetrace.dsl.compiler import (
    DslError,
    DslSemanticError,
    DslSyntaxError,
    compile_dsl,
    get_bytecode_cache,
    get_file_stats,
    get_source_map_registry,
    validate_dsl,
)
from streetrace.dsl.errors import Diagnostic, DiagnosticReporter, ErrorCode, Severity
from streetrace.dsl.grammar import ParserFactory, StreetraceIndenter

# Note: DslAgentLoader has been removed. For DSL loading, use:
# streetrace.workloads.DslDefinitionLoader
from streetrace.dsl.runtime import DslAgentWorkflow, WorkflowContext
from streetrace.dsl.semantic import SemanticAnalyzer
from streetrace.dsl.semantic.analyzer import AnalysisResult
from streetrace.dsl.sourcemap import (
    SourceMapping,
    SourceMapRegistry,
    install_excepthook,
)

__all__ = [
    "AnalysisResult",
    "BytecodeCache",
    "CodeEmitter",
    "CodeGenerator",
    "Diagnostic",
    "DiagnosticReporter",
    # "DslAgentLoader" - REMOVED: Use DslDefinitionLoader from streetrace.workloads
    "DslAgentWorkflow",
    "DslError",
    "DslSemanticError",
    "DslSyntaxError",
    "ErrorCode",
    "ParserFactory",
    "SemanticAnalyzer",
    "Severity",
    "SourceMapRegistry",
    "SourceMapping",
    "StreetraceIndenter",
    "WorkflowContext",
    "compile_dsl",
    "get_bytecode_cache",
    "get_file_stats",
    "get_source_map_registry",
    "install_excepthook",
    "run_check",
    "run_dump_python",
    "validate_dsl",
]
