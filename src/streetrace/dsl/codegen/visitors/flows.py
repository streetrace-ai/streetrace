"""Flow visitor for DSL code generation.

Generate Python code for flow definitions and control flow statements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from streetrace.dsl.ast.nodes import (
    AbortStmt,
    Assignment,
    CallStmt,
    ContinueStmt,
    EscalateStmt,
    EscalationHandler,
    FailureBlock,
    FlowDef,
    ForLoop,
    IfBlock,
    LogStmt,
    LoopBlock,
    MatchBlock,
    NotifyStmt,
    ParallelBlock,
    PropertyAssignment,
    PushStmt,
    RetryStepStmt,
    ReturnStmt,
    RunStmt,
    VarRef,
)
from streetrace.dsl.codegen.visitors.expressions import ExpressionVisitor
from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from streetrace.dsl.codegen.emitter import CodeEmitter

logger = get_logger(__name__)


class FlowVisitor:
    """Generate Python code for DSL flow definitions.

    Visit flow definition nodes and emit async method definitions
    with proper control flow translation.
    """

    def __init__(self, emitter: CodeEmitter) -> None:
        """Initialize the flow visitor.

        Args:
            emitter: Code emitter for output generation.

        """
        self._emitter = emitter
        self._expr_visitor = ExpressionVisitor()
        self._stmt_dispatch: dict[type, Callable[[object], None]] = {
            Assignment: self._visit_assignment,  # type: ignore[dict-item]
            PropertyAssignment: self._visit_property_assignment,  # type: ignore[dict-item]
            RunStmt: self._visit_run_stmt,  # type: ignore[dict-item]
            CallStmt: self._visit_call_stmt,  # type: ignore[dict-item]
            ReturnStmt: self._visit_return_stmt,  # type: ignore[dict-item]
            PushStmt: self._visit_push_stmt,  # type: ignore[dict-item]
            ForLoop: self._visit_for_loop,  # type: ignore[dict-item]
            ParallelBlock: self._visit_parallel_block,  # type: ignore[dict-item]
            MatchBlock: self._visit_match_block,  # type: ignore[dict-item]
            IfBlock: self._visit_if_block,  # type: ignore[dict-item]
            FailureBlock: self._visit_failure_block,  # type: ignore[dict-item]
            LogStmt: self._visit_log_stmt,  # type: ignore[dict-item]
            NotifyStmt: self._visit_notify_stmt,  # type: ignore[dict-item]
            EscalateStmt: self._visit_escalate_stmt,  # type: ignore[dict-item]
            ContinueStmt: self._visit_continue_stmt,  # type: ignore[dict-item]
            AbortStmt: self._visit_abort_stmt,  # type: ignore[dict-item]
            RetryStepStmt: self._visit_retry_step_stmt,  # type: ignore[dict-item]
            LoopBlock: self._visit_loop_block,  # type: ignore[dict-item]
        }

    def visit(self, node: FlowDef) -> None:
        """Visit a flow definition and generate Python code.

        Args:
            node: Flow definition AST node.

        """
        source_line = node.meta.line if node.meta else None

        # Emit method definition with async generator signature
        self._emitter.emit(
            f"async def flow_{node.name}(",
            source_line=source_line,
        )
        self._emitter.emit(
            "    self, ctx: WorkflowContext",
        )
        self._emitter.emit(
            ") -> AsyncGenerator[Event | FlowEvent, None]:",
        )
        self._emitter.indent()

        # Parameters are passed through ctx.vars by the caller
        # No explicit initialization needed here

        if not node.body:
            self._emitter.emit("pass")
        else:
            self._visit_flow_body(node.body)

        self._emitter.dedent()
        self._emitter.emit_blank()

    def _visit_flow_body(self, body: list[object]) -> None:
        """Visit and emit flow body statements.

        Handle failure blocks by wrapping preceding statements in try/except.
        If a FailureBlock is present, all statements before it are wrapped
        in a try block, and the failure block becomes the except handler.

        Args:
            body: List of flow body statements.

        """
        # Find if there's a failure block in the body
        failure_idx = self._find_failure_block_index(body)

        if failure_idx is not None:
            self._emit_with_failure_handler(body, failure_idx)
        else:
            # No failure block - emit statements normally
            for stmt in body:
                self.visit_statement(stmt)

    def _find_failure_block_index(self, body: list[object]) -> int | None:
        """Find the index of a FailureBlock in the body, if any.

        Args:
            body: List of flow body statements.

        Returns:
            Index of the FailureBlock or None if not found.

        """
        for i, stmt in enumerate(body):
            if isinstance(stmt, FailureBlock):
                return i
        return None

    def _emit_with_failure_handler(
        self,
        body: list[object],
        failure_idx: int,
    ) -> None:
        """Emit flow body with failure block as try/except.

        Args:
            body: List of flow body statements.
            failure_idx: Index of the FailureBlock in the body.

        """
        failure_block_item = body[failure_idx]
        # Type guard - we know it's FailureBlock from the index finding logic
        if not isinstance(failure_block_item, FailureBlock):
            self._emitter.emit("pass")
            return

        failure_block = failure_block_item
        source_line = failure_block.meta.line if failure_block.meta else None

        # Emit try block with preceding statements
        self._emitter.emit("try:", source_line=source_line)
        self._emitter.indent()
        self._emit_statements_or_pass(body[:failure_idx])
        self._emitter.dedent()

        # Emit except block with failure block body
        self._emitter.emit("except Exception as _e:")
        self._emitter.indent()
        self._emit_statements_or_pass(failure_block.body)
        self._emitter.dedent()

        # Emit statements after the failure block (if any)
        for stmt in body[failure_idx + 1:]:
            self.visit_statement(stmt)

    def _emit_statements_or_pass(self, statements: list[object]) -> None:
        """Emit statements or pass if the list is empty.

        Args:
            statements: List of statements to emit.

        """
        if statements:
            for stmt in statements:
                self.visit_statement(stmt)
        else:
            self._emitter.emit("pass")

    def visit_statement(self, stmt: object) -> None:
        """Visit a single statement and generate code.

        Args:
            stmt: Statement AST node.

        """
        stmt_type = type(stmt)
        visitor = self._stmt_dispatch.get(stmt_type)
        if visitor:
            visitor(stmt)
        else:
            logger.warning("Unknown statement type: %s", stmt_type.__name__)

    def _visit_assignment(self, node: Assignment) -> None:
        """Generate code for variable assignment.

        Args:
            node: Assignment node.

        """
        source_line = node.meta.line if node.meta else None
        target_name = node.target.lstrip("$")
        value = self._expr_visitor.visit(node.value)
        self._emitter.emit(
            f"ctx.vars['{target_name}'] = {value}",
            source_line=source_line,
        )

    def _visit_property_assignment(self, node: PropertyAssignment) -> None:
        """Generate code for property assignment.

        Transform $obj.prop = value to ctx.vars['obj']['prop'] = value.
        Supports nested properties like $obj.a.b = value.

        Args:
            node: PropertyAssignment node.

        """
        source_line = node.meta.line if node.meta else None

        # Get base variable name from PropertyAccess
        base = node.target.base
        base_name = base.name if isinstance(base, VarRef) else str(base)

        # Build nested dict access: ctx.vars['obj']['prop1']['prop2']...
        target = f"ctx.vars['{base_name}']"
        for prop in node.target.properties:
            target = f"{target}['{prop}']"

        # Generate value expression
        value = self._expr_visitor.visit(node.value)

        self._emitter.emit(f"{target} = {value}", source_line=source_line)

    def _visit_run_stmt(self, node: RunStmt) -> None:
        """Generate code for run agent statement.

        Args:
            node: Run statement node.

        """
        source_line = node.meta.line if node.meta else None
        args_str = ", ".join(self._expr_visitor.visit(arg) for arg in node.args)

        if node.escalation_handler:
            # Use run_agent_with_escalation which tracks escalation state
            if args_str:
                call = f"ctx.run_agent_with_escalation('{node.agent}', {args_str})"
            else:
                call = f"ctx.run_agent_with_escalation('{node.agent}')"

            # Generate async for loop to yield events and capture result
            self._emitter.emit(
                f"async for _event in {call}:",
                source_line=source_line,
            )
            self._emitter.indent()
            self._emitter.emit("yield _event")
            self._emitter.dedent()

            # Get result and escalation flag
            self._emitter.emit(
                "_result, _escalated = ctx.get_last_result_with_escalation()",
            )

            # Assign result to target if specified
            if node.target:
                target_name = node.target.lstrip("$")
                self._emitter.emit(f"ctx.vars['{target_name}'] = _result")

            # Handle escalation
            self._emitter.emit("if _escalated:")
            self._emitter.indent()
            self._emit_escalation_action(node.escalation_handler)
            self._emitter.dedent()
        else:
            # Original logic for non-escalation runs
            if args_str:
                call = f"ctx.run_agent('{node.agent}', {args_str})"
            else:
                call = f"ctx.run_agent('{node.agent}')"

            # Generate async for loop to yield events
            self._emitter.emit(
                f"async for _event in {call}:",
                source_line=source_line,
            )
            self._emitter.indent()
            self._emitter.emit("yield _event")
            self._emitter.dedent()

            # Assign result from context if target specified
            if node.target:
                target_name = node.target.lstrip("$")
                self._emitter.emit(f"ctx.vars['{target_name}'] = ctx.get_last_result()")

    def _emit_escalation_action(self, handler: EscalationHandler) -> None:
        """Emit code for escalation action.

        Args:
            handler: Escalation handler node.

        """
        if handler.action == "return":
            value = self._expr_visitor.visit(handler.value)
            self._emitter.emit(f"ctx.vars['_return_value'] = {value}")
            self._emitter.emit("return")
        elif handler.action == "continue":
            self._emitter.emit("continue")
        elif handler.action == "abort":
            self._emitter.emit("raise AbortError('Escalation triggered abort')")

    def _visit_call_stmt(self, node: CallStmt) -> None:
        """Generate code for call LLM statement.

        Args:
            node: Call statement node.

        """
        source_line = node.meta.line if node.meta else None
        args_str = ", ".join(self._expr_visitor.visit(arg) for arg in node.args)

        if node.model:
            if args_str:
                call = (
                    f"ctx.call_llm('{node.prompt}', {args_str}, "
                    f"model='{node.model}')"
                )
            else:
                call = f"ctx.call_llm('{node.prompt}', model='{node.model}')"
        elif args_str:
            call = f"ctx.call_llm('{node.prompt}', {args_str})"
        else:
            call = f"ctx.call_llm('{node.prompt}')"

        # Generate async for loop to yield events
        self._emitter.emit(f"async for _event in {call}:", source_line=source_line)
        self._emitter.indent()
        self._emitter.emit("yield _event")
        self._emitter.dedent()

        # Assign result from context if target specified
        if node.target:
            target_name = node.target.lstrip("$")
            self._emitter.emit(f"ctx.vars['{target_name}'] = ctx.get_last_result()")

    def _visit_return_stmt(self, node: ReturnStmt) -> None:
        """Generate code for return statement.

        In async generators, 'return value' is not allowed. Instead, store
        the return value in context and use a bare return.

        Args:
            node: Return statement node.

        """
        source_line = node.meta.line if node.meta else None
        value = self._expr_visitor.visit(node.value)
        # Store return value in context for retrieval after generator completes
        self._emitter.emit(
            f"ctx.vars['_return_value'] = {value}",
            source_line=source_line,
        )
        self._emitter.emit("return")

    def _visit_push_stmt(self, node: PushStmt) -> None:
        """Generate code for push statement.

        Args:
            node: Push statement node.

        """
        source_line = node.meta.line if node.meta else None
        value = self._expr_visitor.visit(node.value)
        target_name = node.target.lstrip("$")
        self._emitter.emit(
            f"ctx.vars['{target_name}'].append({value})",
            source_line=source_line,
        )

    def _visit_for_loop(self, node: ForLoop) -> None:
        """Generate code for for loop.

        Args:
            node: For loop node.

        """
        source_line = node.meta.line if node.meta else None
        var_name = node.variable.lstrip("$")
        iterable = self._expr_visitor.visit(node.iterable)

        self._emitter.emit(
            f"for _item_{var_name} in {iterable}:",
            source_line=source_line,
        )
        self._emitter.indent()

        # Assign loop variable to ctx.vars
        self._emitter.emit(f"ctx.vars['{var_name}'] = _item_{var_name}")

        # Visit loop body
        for stmt in node.body:
            self.visit_statement(stmt)

        self._emitter.dedent()

    def _visit_parallel_block(self, node: ParallelBlock) -> None:
        """Generate code for parallel block.

        Validate that only RunStmt nodes are present, then generate code
        for true parallel execution using asyncio.gather.

        Args:
            node: Parallel block node.

        Raises:
            ValueError: If parallel block contains non-RunStmt statements.

        """
        source_line = node.meta.line if node.meta else None

        # Empty parallel block - just pass
        if not node.body:
            self._emitter.emit("pass", source_line=source_line)
            return

        # Validate: parallel do only supports run agent statements
        for stmt in node.body:
            if not isinstance(stmt, RunStmt):
                stmt_type = type(stmt).__name__
                msg = (
                    f"parallel do only supports 'run agent' statements. "
                    f"Found: {stmt_type}"
                )
                raise TypeError(msg)

        # Collect run statements (already validated to be RunStmt)
        run_stmts: list[RunStmt] = node.body

        # Generate parallel execution code
        self._emitter.emit(
            "# Parallel block - execute agents concurrently",
            source_line=source_line,
        )
        self._emitter.emit("_parallel_specs = [")
        self._emitter.indent()

        for stmt in run_stmts:
            # Generate args list
            args_parts = [self._expr_visitor.visit(arg) for arg in stmt.args]
            args_str = f"[{', '.join(args_parts)}]" if args_parts else "[]"

            # Generate target variable name (or None if no target)
            target_name = f"'{stmt.target.lstrip('$')}'" if stmt.target else "None"

            self._emitter.emit(f"('{stmt.agent}', {args_str}, {target_name}),")

        self._emitter.dedent()
        self._emitter.emit("]")

        # Call the parallel execution helper
        self._emitter.emit(
            "_parallel_results = await self._execute_parallel_agents(",
        )
        self._emitter.emit(
            "    ctx, _parallel_specs)",
        )

        # Assign results to target variables
        for stmt in run_stmts:
            if stmt.target:
                target_name = stmt.target.lstrip("$")
                self._emitter.emit(
                    f"ctx.vars['{target_name}'] = _parallel_results['{target_name}']",
                )

    def _visit_match_block(self, node: MatchBlock) -> None:
        """Generate code for match block.

        Args:
            node: Match block node.

        """
        source_line = node.meta.line if node.meta else None
        expr = self._expr_visitor.visit(node.expression)

        self._emitter.emit(f"match {expr}:", source_line=source_line)
        self._emitter.indent()

        for case in node.cases:
            self._emitter.emit(f"case '{case.pattern}':")
            self._emitter.indent()
            if isinstance(case.body, list):
                for stmt in case.body:
                    self.visit_statement(stmt)
            else:
                self.visit_statement(case.body)
            self._emitter.dedent()

        # Handle else case
        if node.else_body:
            self._emitter.emit("case _:")
            self._emitter.indent()
            if isinstance(node.else_body, list):
                for stmt in node.else_body:
                    self.visit_statement(stmt)
            else:
                self.visit_statement(node.else_body)
            self._emitter.dedent()

        self._emitter.dedent()

    def _visit_if_block(self, node: IfBlock) -> None:
        """Generate code for if block.

        Args:
            node: If block node.

        """
        source_line = node.meta.line if node.meta else None
        condition = self._expr_visitor.visit(node.condition)

        self._emitter.emit(f"if {condition}:", source_line=source_line)
        self._emitter.indent()

        if not node.body:
            self._emitter.emit("pass")
        else:
            for stmt in node.body:
                self.visit_statement(stmt)

        self._emitter.dedent()

    def _visit_failure_block(self, node: FailureBlock) -> None:  # noqa: ARG002
        """Generate code for failure block.

        FailureBlock is handled specially in _visit_flow_body, which wraps
        preceding statements in a try block. This method should not be called
        directly from statement dispatch, but is kept for completeness.

        Args:
            node: Failure block node (not used, see _visit_flow_body).

        """
        # FailureBlock is processed in _visit_flow_body by wrapping
        # preceding statements in try/except. If we get here directly,
        # something unexpected happened.
        logger.warning(
            "FailureBlock visited directly - should be handled in _visit_flow_body",
        )

    def _visit_log_stmt(self, node: LogStmt) -> None:
        """Generate code for log statement.

        Args:
            node: Log statement node.

        """
        source_line = node.meta.line if node.meta else None
        message_code = self._expr_visitor.visit(node.message)
        self._emitter.emit(f"ctx.log({message_code})", source_line=source_line)

    def _visit_notify_stmt(self, node: NotifyStmt) -> None:
        """Generate code for notify statement.

        Args:
            node: Notify statement node.

        """
        source_line = node.meta.line if node.meta else None
        message_code = self._expr_visitor.visit(node.message)
        self._emitter.emit(f"ctx.notify({message_code})", source_line=source_line)

    def _visit_escalate_stmt(self, node: EscalateStmt) -> None:
        """Generate code for escalate statement.

        Args:
            node: Escalate statement node.

        """
        source_line = node.meta.line if node.meta else None
        if node.message:
            self._emitter.emit(
                f"await ctx.escalate_to_human('{node.message}')",
                source_line=source_line,
            )
        else:
            self._emitter.emit(
                "await ctx.escalate_to_human()",
                source_line=source_line,
            )

    def _visit_continue_stmt(self, node: ContinueStmt) -> None:
        """Generate code for continue statement.

        Args:
            node: Continue statement node.

        """
        source_line = node.meta.line if node.meta else None
        self._emitter.emit("continue", source_line=source_line)

    def _visit_abort_stmt(self, node: AbortStmt) -> None:
        """Generate code for abort statement.

        Args:
            node: Abort statement node.

        """
        source_line = node.meta.line if node.meta else None
        self._emitter.emit("raise AbortError('Flow aborted')", source_line=source_line)

    def _visit_retry_step_stmt(self, node: RetryStepStmt) -> None:
        """Generate code for retry step statement.

        Args:
            node: Retry step statement node.

        """
        source_line = node.meta.line if node.meta else None
        message = self._expr_visitor.visit(node.message)
        self._emitter.emit(
            f"raise RetryStepError({message})",
            source_line=source_line,
        )

    def _visit_loop_block(self, node: LoopBlock) -> None:
        """Generate code for loop block.

        Generate a while loop with optional iteration counter for the
        iterative refinement pattern.

        Args:
            node: Loop block AST node.

        """
        source_line = node.meta.line if node.meta else None

        if node.max_iterations is not None:
            # Bounded loop with iteration counter
            self._emitter.emit("_loop_count = 0", source_line=source_line)
            self._emitter.emit(f"_max_iterations = {node.max_iterations}")
            self._emitter.emit("while _loop_count < _max_iterations:")
            self._emitter.indent()
            self._emitter.emit("_loop_count += 1")
        else:
            # Unbounded loop (while True)
            self._emitter.emit("while True:", source_line=source_line)
            self._emitter.indent()

        # Emit loop body
        if node.body:
            for stmt in node.body:
                self.visit_statement(stmt)
        else:
            self._emitter.emit("pass")

        self._emitter.dedent()
