"""Handler visitor for DSL code generation.

Generate Python code for event handlers.
"""

from streetrace.dsl.ast.nodes import (
    BlockAction,
    EventHandler,
    MaskAction,
    RetryAction,
    WarnAction,
)
from streetrace.dsl.codegen.emitter import CodeEmitter
from streetrace.dsl.codegen.visitors.expressions import ExpressionVisitor
from streetrace.log import get_logger

logger = get_logger(__name__)


class HandlerVisitor:
    """Generate Python code for DSL event handlers.

    Visit event handler nodes and emit async method definitions.
    """

    def __init__(self, emitter: CodeEmitter) -> None:
        """Initialize the handler visitor.

        Args:
            emitter: Code emitter for output generation.

        """
        self._emitter = emitter
        self._expr_visitor = ExpressionVisitor()

    def visit(self, node: EventHandler) -> None:
        """Visit an event handler and generate Python code.

        Args:
            node: Event handler AST node.

        """
        method_name = self._get_method_name(node)
        source_line = node.meta.line if node.meta else None

        # Emit method definition
        self._emitter.emit(
            f"async def {method_name}(self, ctx: WorkflowContext) -> None:",
            source_line=source_line,
        )
        self._emitter.indent()

        if not node.body:
            self._emitter.emit("pass")
        else:
            self._visit_handler_body(node.body)

        self._emitter.dedent()
        self._emitter.emit_blank()

    def _get_method_name(self, node: EventHandler) -> str:
        """Get the method name for an event handler.

        Args:
            node: Event handler node.

        Returns:
            Python method name for the handler.

        """
        event_type = node.event_type.replace("-", "_")
        return f"{node.timing}_{event_type}"

    def _visit_handler_body(self, body: list[object]) -> None:
        """Visit and emit handler body statements.

        Args:
            body: List of handler body statements.

        """
        # Import statement visitor for non-guardrail statements
        from streetrace.dsl.codegen.visitors.flows import FlowVisitor

        flow_visitor = FlowVisitor(self._emitter)

        for stmt in body:
            if isinstance(stmt, MaskAction):
                self._visit_mask_action(stmt)
            elif isinstance(stmt, BlockAction):
                self._visit_block_action(stmt)
            elif isinstance(stmt, WarnAction):
                self._visit_warn_action(stmt)
            elif isinstance(stmt, RetryAction):
                self._visit_retry_action(stmt)
            else:
                # Delegate to flow visitor for other statements
                flow_visitor.visit_statement(stmt)

    def _visit_mask_action(self, node: MaskAction) -> None:
        """Generate code for mask guardrail action.

        Args:
            node: Mask action node.

        """
        source_line = node.meta.line if node.meta else None
        guardrail = node.guardrail
        self._emitter.emit(
            f"ctx.message = await ctx.guardrails.mask('{guardrail}', ctx.message)",
            source_line=source_line,
        )

    def _visit_block_action(self, node: BlockAction) -> None:
        """Generate code for block guardrail action.

        Args:
            node: Block action node.

        """
        source_line = node.meta.line if node.meta else None
        condition = self._expr_visitor.visit(node.condition)

        # If condition is a simple name, treat it as a guardrail check
        if condition.startswith("ctx.vars['") and condition.endswith("']"):
            guardrail_name = condition[len("ctx.vars['") : -len("']")]
            self._emitter.emit(
                f"if await ctx.guardrails.check('{guardrail_name}', ctx.message):",
                source_line=source_line,
            )
        else:
            self._emitter.emit(f"if {condition}:", source_line=source_line)

        self._emitter.indent()
        self._emitter.emit(
            "raise BlockedInputError('Input blocked: guardrail triggered')",
        )
        self._emitter.dedent()

    def _visit_warn_action(self, node: WarnAction) -> None:
        """Generate code for warn guardrail action.

        Args:
            node: Warn action node.

        """
        source_line = node.meta.line if node.meta else None

        if node.condition:
            condition = self._expr_visitor.visit(node.condition)
            self._emitter.emit(f"if {condition}:", source_line=source_line)
            self._emitter.indent()
            message = node.message or "Warning condition triggered"
            self._emitter.emit(f"ctx.warn('{message}')")
            self._emitter.dedent()
        elif node.message:
            self._emitter.emit(f"ctx.warn('{node.message}')", source_line=source_line)

    def _visit_retry_action(self, node: RetryAction) -> None:
        """Generate code for retry guardrail action.

        Args:
            node: Retry action node.

        """
        source_line = node.meta.line if node.meta else None
        message = self._expr_visitor.visit(node.message)
        condition = self._expr_visitor.visit(node.condition)

        self._emitter.emit(f"if {condition}:", source_line=source_line)
        self._emitter.indent()
        self._emitter.emit(f"raise RetryInputError({message})")
        self._emitter.dedent()
