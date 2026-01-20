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
    FailureBlock,
    FlowDef,
    ForLoop,
    IfBlock,
    LogStmt,
    MatchBlock,
    NotifyStmt,
    ParallelBlock,
    PushStmt,
    RetryStepStmt,
    ReturnStmt,
    RunStmt,
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
        }

    def visit(self, node: FlowDef) -> None:
        """Visit a flow definition and generate Python code.

        Args:
            node: Flow definition AST node.

        """
        source_line = node.meta.line if node.meta else None

        # Emit method definition
        self._emitter.emit(
            f"async def flow_{node.name}(self, ctx: WorkflowContext) -> Any:",
            source_line=source_line,
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

        Args:
            body: List of flow body statements.

        """
        for stmt in body:
            self.visit_statement(stmt)

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

    def _visit_run_stmt(self, node: RunStmt) -> None:
        """Generate code for run agent statement.

        Args:
            node: Run statement node.

        """
        source_line = node.meta.line if node.meta else None
        args_str = ", ".join(self._expr_visitor.visit(arg) for arg in node.args)

        if args_str:
            call = f"await ctx.run_agent('{node.agent}', {args_str})"
        else:
            call = f"await ctx.run_agent('{node.agent}')"

        if node.target:
            target_name = node.target.lstrip("$")
            self._emitter.emit(
                f"ctx.vars['{target_name}'] = {call}",
                source_line=source_line,
            )
        else:
            self._emitter.emit(call, source_line=source_line)

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
                    f"await ctx.call_llm('{node.prompt}', {args_str}, "
                    f"model='{node.model}')"
                )
            else:
                call = f"await ctx.call_llm('{node.prompt}', model='{node.model}')"
        elif args_str:
            call = f"await ctx.call_llm('{node.prompt}', {args_str})"
        else:
            call = f"await ctx.call_llm('{node.prompt}')"

        if node.target:
            target_name = node.target.lstrip("$")
            self._emitter.emit(
                f"ctx.vars['{target_name}'] = {call}",
                source_line=source_line,
            )
        else:
            self._emitter.emit(call, source_line=source_line)

    def _visit_return_stmt(self, node: ReturnStmt) -> None:
        """Generate code for return statement.

        Args:
            node: Return statement node.

        """
        source_line = node.meta.line if node.meta else None
        value = self._expr_visitor.visit(node.value)
        self._emitter.emit(f"return {value}", source_line=source_line)

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

        Args:
            node: Parallel block node.

        """
        source_line = node.meta.line if node.meta else None

        # Collect all run statements using list comprehension
        run_stmts = [stmt for stmt in node.body if isinstance(stmt, RunStmt)]

        if not run_stmts:
            # No run statements, just execute sequentially
            for stmt in node.body:
                self.visit_statement(stmt)
            return

        # Generate parallel execution
        calls = []
        targets = []
        for stmt in run_stmts:
            args_str = ", ".join(self._expr_visitor.visit(arg) for arg in stmt.args)
            if args_str:
                call = f"ctx.run_agent('{stmt.agent}', {args_str})"
            else:
                call = f"ctx.run_agent('{stmt.agent}')"
            calls.append(call)
            targets.append(stmt.target.lstrip("$") if stmt.target else None)

        # Emit asyncio.gather
        self._emitter.emit("_parallel_results = await asyncio.gather(", source_line)
        self._emitter.indent()
        for call in calls:
            self._emitter.emit(f"{call},")
        self._emitter.dedent()
        self._emitter.emit(")")

        # Assign results to targets
        for i, target in enumerate(targets):
            if target:
                self._emitter.emit(f"ctx.vars['{target}'] = _parallel_results[{i}]")

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

    def _visit_failure_block(self, node: FailureBlock) -> None:
        """Generate code for failure block.

        Args:
            node: Failure block node.

        """
        source_line = node.meta.line if node.meta else None

        # Wrap previous code in try block and add except handler
        self._emitter.emit("try:", source_line=source_line)
        self._emitter.indent()
        self._emitter.emit("pass  # Placeholder: move preceding code here")
        self._emitter.dedent()
        self._emitter.emit("except Exception as _e:")
        self._emitter.indent()

        if not node.body:
            self._emitter.emit("pass")
        else:
            for stmt in node.body:
                self.visit_statement(stmt)

        self._emitter.dedent()

    def _visit_log_stmt(self, node: LogStmt) -> None:
        """Generate code for log statement.

        Args:
            node: Log statement node.

        """
        source_line = node.meta.line if node.meta else None
        self._emitter.emit(f"ctx.log('{node.message}')", source_line=source_line)

    def _visit_notify_stmt(self, node: NotifyStmt) -> None:
        """Generate code for notify statement.

        Args:
            node: Notify statement node.

        """
        source_line = node.meta.line if node.meta else None
        self._emitter.emit(f"ctx.notify('{node.message}')", source_line=source_line)

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
