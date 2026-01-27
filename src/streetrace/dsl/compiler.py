"""Main compiler for Streetrace DSL.

Provide the primary compilation and validation functions for transforming
DSL source code into Python bytecode.
"""

from types import CodeType

from lark import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken
from lark.indenter import DedentError

from streetrace.dsl.ast.nodes import AgentDef, DslFile, EventHandler, FlowDef, ModelDef
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.cache import BytecodeCache
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.errors.codes import ErrorCode
from streetrace.dsl.errors.diagnostics import Diagnostic
from streetrace.dsl.grammar.parser import ParserFactory
from streetrace.dsl.semantic import errors as semantic_errors
from streetrace.dsl.semantic.analyzer import SemanticAnalyzer
from streetrace.dsl.semantic.errors import SemanticError
from streetrace.dsl.sourcemap.registry import SourceMapping, SourceMapRegistry
from streetrace.log import get_logger

logger = get_logger(__name__)


def normalize_source(source: str) -> str:
    """Normalize DSL source for parsing.

    Ensure source ends with a newline character. The grammar requires _NL
    tokens after statements, and files without trailing newlines cause
    unexpected EOF errors.

    Args:
        source: The DSL source code.

    Returns:
        Normalized source with trailing newline.

    """
    if source and not source.endswith("\n"):
        return source + "\n"
    return source


# Global cache and registry instances
_bytecode_cache: BytecodeCache | None = None
_source_map_registry: SourceMapRegistry | None = None


def get_bytecode_cache() -> BytecodeCache:
    """Get the global bytecode cache instance.

    Returns:
        The shared BytecodeCache instance.

    """
    global _bytecode_cache  # noqa: PLW0603
    if _bytecode_cache is None:
        _bytecode_cache = BytecodeCache()
    return _bytecode_cache


def get_source_map_registry() -> SourceMapRegistry:
    """Get the global source map registry instance.

    Returns:
        The shared SourceMapRegistry instance.

    """
    global _source_map_registry  # noqa: PLW0603
    if _source_map_registry is None:
        _source_map_registry = SourceMapRegistry()
    return _source_map_registry


def compile_dsl(
    source: str,
    filename: str,
    *,
    debug_parser: bool = False,
    use_cache: bool = True,
) -> tuple[CodeType, list[SourceMapping]]:
    """Compile DSL source to Python bytecode.

    Transform DSL source through the complete pipeline: parsing, AST
    transformation, semantic analysis, code generation, and compilation.

    Args:
        source: The DSL source code.
        filename: Name of the source file (for error messages and source maps).
        debug_parser: Enable parser debug mode for verbose output.
        use_cache: Use bytecode caching for repeated compilations.

    Returns:
        Tuple of (compiled bytecode, source mappings).

    Raises:
        DslSyntaxError: If parsing fails.
        DslSemanticError: If semantic analysis fails.
        SyntaxError: If generated Python code has syntax errors.

    """
    logger.debug("Compiling DSL file: %s", filename)

    # Normalize source (ensure trailing newline for grammar)
    source = normalize_source(source)

    # Check cache first
    if use_cache:
        cache = get_bytecode_cache()
        cached = cache.get(source)
        if cached is not None:
            logger.debug("Using cached bytecode for %s", filename)
            return cached

    # Parse the source
    try:
        parser = ParserFactory.create(debug=debug_parser)
        tree = parser.parse(source)
    except (UnexpectedCharacters, UnexpectedEOF, UnexpectedToken) as e:
        logger.debug("Parse error in %s: %s", filename, e)
        raise DslSyntaxError(str(e), filename=filename, parse_error=e) from e
    except DedentError as e:
        msg = f"mismatched indentation: {e}"
        logger.debug("Indentation error in %s: %s", filename, e)
        raise DslSyntaxError(msg, filename=filename, parse_error=e) from e

    # Transform to AST
    ast = transform(tree)

    # Semantic analysis
    analyzer = SemanticAnalyzer()
    result = analyzer.analyze(ast)

    if not result.is_valid:
        logger.debug("Semantic errors in %s: %d errors", filename, len(result.errors))
        msg = "semantic analysis failed"
        raise DslSemanticError(msg, filename=filename, errors=result.errors)

    # Code generation
    generator = CodeGenerator()
    python_source, source_mappings = generator.generate(ast, filename)

    # Compile to bytecode
    # SECURITY: This compile() usage is intentional and safe.
    # The source code is generated from a verified DSL file.
    generated_filename = f"<dsl:{filename}>"
    bytecode = compile(python_source, generated_filename, "exec")

    # Register source mappings
    registry = get_source_map_registry()
    for mapping in source_mappings:
        registry.add_mapping(generated_filename, mapping)

    # Cache the result
    if use_cache:
        cache = get_bytecode_cache()
        cache.put(source, bytecode, source_mappings)

    logger.debug(
        "Compiled %s: %d lines of Python, %d source mappings",
        filename,
        python_source.count("\n") + 1,
        len(source_mappings),
    )

    return bytecode, source_mappings


def validate_dsl(
    source: str,
    filename: str,
    *,
    debug_parser: bool = False,
) -> list[Diagnostic]:
    """Validate DSL source without compilation.

    Perform parsing and semantic analysis to produce diagnostics
    without generating or compiling code.

    Args:
        source: The DSL source code.
        filename: Name of the source file.
        debug_parser: Enable parser debug mode.

    Returns:
        List of diagnostics (errors and warnings).

    """
    logger.debug("Validating DSL file: %s", filename)
    diagnostics: list[Diagnostic] = []

    # Normalize source (ensure trailing newline for grammar)
    source = normalize_source(source)

    # Parse the source
    try:
        parser = ParserFactory.create(debug=debug_parser)
        tree = parser.parse(source)
    except UnexpectedCharacters as e:
        diagnostics.append(
            Diagnostic.error(
                message="invalid character",
                file=filename,
                line=e.line,
                column=e.column,
                code=ErrorCode.E0007,
                help_text=f"unexpected character '{e.char}'",
            ),
        )
        return diagnostics
    except UnexpectedEOF as e:
        diagnostics.append(
            Diagnostic.error(
                message="unexpected end of input",
                file=filename,
                line=e.line if hasattr(e, "line") else 1,
                column=e.column if hasattr(e, "column") else 0,
                code=ErrorCode.E0007,
            ),
        )
        return diagnostics
    except UnexpectedToken as e:
        diagnostics.append(
            Diagnostic.error(
                message=f"unexpected token '{e.token}'",
                file=filename,
                line=e.line,
                column=e.column,
                code=ErrorCode.E0007,
                help_text=f"expected one of: {', '.join(str(x) for x in e.expected)}",
            ),
        )
        return diagnostics
    except DedentError as e:
        # Extract line info from the error message if possible
        line = 1
        help_text = str(e)
        # Parse error message like "Unexpected dedent to column 2. Expected dedent to 0"
        if "column" in str(e).lower():
            help_text = (
                f"{e} - check that all lines in the block have consistent indentation"
            )
        diagnostics.append(
            Diagnostic.error(
                message="mismatched indentation",
                file=filename,
                line=line,
                column=0,
                code=ErrorCode.E0008,
                help_text=help_text,
            ),
        )
        return diagnostics

    # Transform to AST
    try:
        ast = transform(tree)
    except Exception as e:  # noqa: BLE001
        diagnostics.append(
            Diagnostic.error(
                message=f"AST transformation failed: {e}",
                file=filename,
                line=1,
                column=0,
            ),
        )
        return diagnostics

    # Semantic analysis
    analyzer = SemanticAnalyzer()
    result = analyzer.analyze(ast)

    # Convert semantic errors to diagnostics
    diagnostics.extend(
        _semantic_error_to_diagnostic(error, filename) for error in result.errors
    )

    return diagnostics


def get_file_stats(source: str, filename: str) -> dict[str, int]:  # noqa: ARG001
    """Get statistics about a DSL file.

    Args:
        source: The DSL source code.
        filename: Name of the source file (used for future error context).

    Returns:
        Dictionary with counts of models, agents, flows, handlers.

    """
    # Normalize source (ensure trailing newline for grammar)
    source = normalize_source(source)

    try:
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)
    except Exception:  # noqa: BLE001
        return {"models": 0, "agents": 0, "flows": 0, "handlers": 0}

    return _count_definitions(ast)


def _count_definitions(ast: DslFile) -> dict[str, int]:
    """Count definition types in AST.

    Args:
        ast: The DslFile AST node.

    Returns:
        Dictionary with counts.

    """
    counts = {"models": 0, "agents": 0, "flows": 0, "handlers": 0}

    for stmt in ast.statements:
        if isinstance(stmt, ModelDef):
            counts["models"] += 1
        elif isinstance(stmt, AgentDef):
            counts["agents"] += 1
        elif isinstance(stmt, FlowDef):
            counts["flows"] += 1
        elif isinstance(stmt, EventHandler):
            counts["handlers"] += 1

    return counts


def _map_semantic_error_code(
    semantic_code: semantic_errors.ErrorCode,
) -> ErrorCode | None:
    """Map a semantic ErrorCode to the errors.codes ErrorCode.

    Args:
        semantic_code: The semantic error code.

    Returns:
        Corresponding ErrorCode or None if no mapping exists.

    """
    # Map by name since both enums use the same names (E0001, E0002, etc.)
    try:
        return ErrorCode(semantic_code.name)
    except ValueError:
        logger.warning("No mapping for semantic error code: %s", semantic_code.name)
        return None


def _semantic_error_to_diagnostic(
    error: SemanticError,
    filename: str,
) -> Diagnostic:
    """Convert a SemanticError to a Diagnostic.

    Args:
        error: The semantic error.
        filename: Source filename.

    Returns:
        Diagnostic instance.

    """
    line = 1
    column = 0
    end_line = None
    end_column = None

    if error.position is not None:
        line = error.position.line
        column = error.position.column
        end_line = error.position.end_line
        end_column = error.position.end_column

    # Map semantic error code to diagnostic error code
    diagnostic_code = _map_semantic_error_code(error.code)

    return Diagnostic.error(
        message=error.message,
        file=filename,
        line=line,
        column=column,
        code=diagnostic_code,
        end_line=end_line,
        end_column=end_column,
        help_text=error.suggestion,
    )


class DslError(Exception):
    """Base exception for DSL compiler errors."""

    def __init__(self, message: str, *, filename: str | None = None) -> None:
        """Initialize DSL error.

        Args:
            message: Error message.
            filename: Optional source filename.

        """
        super().__init__(message)
        self.filename = filename


class DslSyntaxError(DslError):
    """Exception for DSL parsing/syntax errors."""

    def __init__(
        self,
        message: str,
        *,
        filename: str | None = None,
        parse_error: Exception | None = None,
    ) -> None:
        """Initialize syntax error.

        Args:
            message: Error message.
            filename: Source filename.
            parse_error: Original Lark parse error.

        """
        super().__init__(message, filename=filename)
        self.parse_error = parse_error


class DslSemanticError(DslError):
    """Exception for DSL semantic analysis errors."""

    def __init__(
        self,
        message: str,
        *,
        filename: str | None = None,
        errors: list[SemanticError] | None = None,
    ) -> None:
        """Initialize semantic error.

        Args:
            message: Error message.
            filename: Source filename.
            errors: List of semantic errors.

        """
        super().__init__(message, filename=filename)
        self.errors = errors or []

    def __str__(self) -> str:
        """Format error with detailed semantic error information.

        Returns:
            User-friendly error message including all semantic errors.

        """
        if not self.errors:
            return super().__str__()

        # Format each semantic error
        error_lines = []
        for err in self.errors:
            location = ""
            if err.position:
                location = f" at line {err.position.line}"
            error_lines.append(f"  - {err.message}{location}")
            if err.suggestion:
                error_lines.append(f"    hint: {err.suggestion}")

        details = "\n".join(error_lines)
        return f"semantic analysis failed:\n{details}"
