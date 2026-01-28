"""Main code generator for Streetrace DSL.

Transform validated DSL AST into Python source code with source mappings.
"""

from streetrace.dsl.ast.nodes import DslFile, PromptDef
from streetrace.dsl.codegen.emitter import CodeEmitter
from streetrace.dsl.codegen.visitors.workflow import WorkflowVisitor
from streetrace.dsl.sourcemap.registry import SourceMapping
from streetrace.log import get_logger

logger = get_logger(__name__)


class CodeGenerator:
    """Generate Python code from DSL AST.

    Transform a validated DslFile AST into Python source code
    suitable for execution, along with source mappings for
    error translation.
    """

    def __init__(self) -> None:
        """Initialize the code generator."""
        logger.debug("Created CodeGenerator")

    def generate(
        self,
        ast: DslFile,
        source_file: str,
        *,
        merged_prompts: dict[str, PromptDef] | None = None,
    ) -> tuple[str, list[SourceMapping]]:
        """Generate Python code from a DSL AST.

        Args:
            ast: Validated DslFile AST node.
            source_file: Name of the original source file.
            merged_prompts: Optional dict of prompt name to merged PromptDef
                from semantic analysis. When provided, these are used instead
                of extracting prompts from AST statements.

        Returns:
            Tuple of (generated Python code, source mappings).

        """
        logger.debug("Generating Python code for %s", source_file)

        # Create emitter for this file
        emitter = CodeEmitter(source_file)

        # Visit the AST and emit code
        visitor = WorkflowVisitor(emitter)
        visitor.visit(ast, source_file, merged_prompts=merged_prompts)

        # Get the generated code and mappings
        code = emitter.get_code()
        mappings = emitter.get_source_mappings()

        logger.debug(
            "Generated %d lines of code with %d source mappings",
            emitter.get_line_count(),
            len(mappings),
        )

        return code, mappings
