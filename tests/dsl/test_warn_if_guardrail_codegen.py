"""Tests for warn-if guardrail codegen bug (RFC-020 debug).

Reproduce the issue where ``warn if <guardrail>`` generates a variable
lookup (``ctx.vars['cognitive_drift']``) instead of a guardrail check
(``await ctx.guardrails.check('cognitive_drift', ctx.message)``).

This causes a KeyError at runtime because 'cognitive_drift' is not
a context variable — it is a guardrail name.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.compiler import compile_dsl, normalize_source
from streetrace.dsl.grammar.parser import ParserFactory
from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.dsl.semantic.analyzer import SemanticAnalyzer

WARN_IF_GUARDRAIL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

after output do
    warn if cognitive_drift
end
"""

BLOCK_IF_GUARDRAIL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

on input do
    block if jailbreak
end
"""

FULL_GUARDRAILS_DSL = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

on input do
    mask pii
    block if jailbreak
end

on output do
    mask pii
end

on tool-call do
    block if mcp_guard
end

on tool-result do
    mask pii
    block if jailbreak
end

after output do
    warn if cognitive_drift
end
"""


def _generate_python(source: str) -> str:
    """Generate Python source from DSL source.

    Args:
        source: DSL source code.

    Returns:
        Generated Python source code string.

    """
    source = normalize_source(source)
    parser = ParserFactory.create()
    tree = parser.parse(source)
    ast = transform(tree)
    analyzer = SemanticAnalyzer()
    result = analyzer.analyze(ast)
    gen = CodeGenerator()
    python_source, _ = gen.generate(
        ast, "test.sr", merged_prompts=result.symbols.prompts,
    )
    return python_source


def _get_workflow_class(bytecode: object) -> type[DslAgentWorkflow]:
    """Run bytecode and extract workflow class."""
    namespace: dict[str, object] = {}
    # SECURITY: Test code running validated DSL bytecode
    exec(bytecode, namespace)  # noqa: S102  # nosec B102

    for obj in namespace.values():
        is_workflow = (
            isinstance(obj, type)
            and issubclass(obj, DslAgentWorkflow)
            and obj is not DslAgentWorkflow
        )
        if is_workflow:
            return obj

    msg = "No workflow class found"
    raise ValueError(msg)


class TestWarnIfGuardrailCodegen:
    """Test that warn-if generates guardrail checks, not variable lookups."""

    def test_warn_if_generates_guardrail_check_not_var_lookup(self) -> None:
        """Warn if cognitive_drift should call ctx.guardrails.check.

        BUG: Currently generates ``ctx.vars['cognitive_drift']`` which
        raises KeyError at runtime. Should generate:
        ``await ctx.guardrails.check('cognitive_drift', ctx.message)``
        """
        python_source = _generate_python(WARN_IF_GUARDRAIL_SOURCE)

        # The generated code SHOULD contain a guardrails.check call
        assert "ctx.guardrails.check" in python_source, (
            "warn if should generate guardrails.check call, "
            f"got:\n{python_source}"
        )
        # The generated code should NOT contain a bare variable lookup
        assert "ctx.vars['cognitive_drift']" not in python_source, (
            "warn if should NOT generate variable lookup, "
            f"got:\n{python_source}"
        )

    def test_block_if_generates_guardrail_check(self) -> None:
        """Block if jailbreak correctly generates ctx.guardrails.check.

        This test documents the WORKING behavior for comparison.
        """
        python_source = _generate_python(BLOCK_IF_GUARDRAIL_SOURCE)

        assert "ctx.guardrails.check" in python_source
        assert "ctx.vars['jailbreak']" not in python_source

    def test_warn_if_parity_with_block_if(self) -> None:
        """Warn if and block if should both invoke guardrail checks.

        BUG: block if correctly detects guardrail names and generates
        ctx.guardrails.check(), but warn if does not have this logic.
        """
        warn_source = _generate_python(WARN_IF_GUARDRAIL_SOURCE)
        block_source = _generate_python(BLOCK_IF_GUARDRAIL_SOURCE)

        block_has_check = "guardrails.check" in block_source
        warn_has_check = "guardrails.check" in warn_source

        assert block_has_check, "block if should use guardrails.check"
        assert warn_has_check, (
            "warn if should use guardrails.check like block if does. "
            f"warn if generated:\n{warn_source}"
        )

    def test_full_dsl_compiles_all_handlers(self) -> None:
        """Full DSL with all guardrail handlers should compile."""
        bytecode, _ = compile_dsl(FULL_GUARDRAILS_DSL, "test.sr")
        workflow_class = _get_workflow_class(bytecode)

        assert hasattr(workflow_class, "on_input")
        assert hasattr(workflow_class, "on_output")
        assert hasattr(workflow_class, "on_tool_call")
        assert hasattr(workflow_class, "on_tool_result")
        assert hasattr(workflow_class, "after_output")

    @pytest.mark.asyncio
    async def test_warn_if_calls_guardrail_check_at_runtime(self) -> None:
        """Calling after_output should invoke guardrails.check, not raise KeyError."""
        bytecode, _ = compile_dsl(WARN_IF_GUARDRAIL_SOURCE, "test.sr")
        workflow_class = _get_workflow_class(bytecode)

        ctx = MagicMock()
        ctx.vars = {}
        ctx.message = "test message"
        ctx.guardrails = MagicMock()
        ctx.guardrails.check = AsyncMock(return_value=False)
        ctx.warn = MagicMock()

        workflow = workflow_class.__new__(workflow_class)

        await workflow.after_output(ctx)

        ctx.guardrails.check.assert_awaited_once_with(
            "cognitive_drift", "test message",
        )
        ctx.warn.assert_not_called()

    @pytest.mark.asyncio
    async def test_warn_if_triggers_ctx_warn_when_guardrail_fires(self) -> None:
        """When guardrail check returns True, ctx.warn should be called."""
        bytecode, _ = compile_dsl(WARN_IF_GUARDRAIL_SOURCE, "test.sr")
        workflow_class = _get_workflow_class(bytecode)

        ctx = MagicMock()
        ctx.vars = {}
        ctx.message = "suspicious message"
        ctx.guardrails = MagicMock()
        ctx.guardrails.check = AsyncMock(return_value=True)
        ctx.warn = MagicMock()

        workflow = workflow_class.__new__(workflow_class)

        await workflow.after_output(ctx)

        ctx.guardrails.check.assert_awaited_once_with(
            "cognitive_drift", "suspicious message",
        )
        ctx.warn.assert_called_once()
