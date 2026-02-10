"""Tests for prompt composition via $prompt_name in templates.

Validate that $prompt_name in a prompt body resolves to that prompt's body text,
with flow variables taking precedence over prompt names. Tests cover the
resolve() method on WorkflowContext and codegen changes.
"""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from streetrace.dsl.runtime.workflow import PromptSpec

if TYPE_CHECKING:
    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.workflow import DslAgentWorkflow


@pytest.fixture
def mock_workflow() -> "DslAgentWorkflow":
    """Create a mock DslAgentWorkflow for testing."""
    return MagicMock()


# =============================================================================
# WorkflowContext.resolve() — unit tests
# =============================================================================


class TestResolveFromPrompts:
    """Resolve prompt names to prompt body text."""

    @pytest.fixture
    def ctx(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext with prompts for composition testing."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        ctx.set_prompts({
            "no_inference": PromptSpec(
                body=lambda _ctx: "Do not infer or assume.",
            ),
            "reviewer": PromptSpec(
                body=lambda ctx: (
                    f"You are a reviewer.\n{ctx.resolve('no_inference')}"
                ),
            ),
        })
        return ctx

    def test_resolve_prompt_name_returns_body(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """Resolve a prompt name to its evaluated body text."""
        result = ctx.resolve("no_inference")
        assert result == "Do not infer or assume."

    def test_resolve_prompt_composition_in_another_prompt(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """A prompt that references another prompt via resolve gets composed."""
        result = ctx.resolve("reviewer")
        assert "You are a reviewer." in result
        assert "Do not infer or assume." in result

    def test_resolve_recursive_composition(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """Prompt A references prompt B which references prompt C."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        ctx.set_prompts({
            "base_rule": PromptSpec(
                body=lambda _ctx: "Be precise.",
            ),
            "style_rule": PromptSpec(
                body=lambda ctx: (
                    f"Write clearly. {ctx.resolve('base_rule')}"
                ),
            ),
            "full_prompt": PromptSpec(
                body=lambda ctx: (
                    f"Review this code. {ctx.resolve('style_rule')}"
                ),
            ),
        })

        result = ctx.resolve("full_prompt")
        assert "Review this code." in result
        assert "Write clearly." in result
        assert "Be precise." in result


class TestResolveVariablePrecedence:
    """Flow variables take precedence over prompt names."""

    @pytest.fixture
    def ctx(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a context with both a variable and a prompt named 'data'."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        ctx.set_prompts({
            "data": PromptSpec(
                body=lambda _ctx: "prompt body for data",
            ),
        })
        return ctx

    def test_variable_overrides_prompt_name(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """When a flow variable and a prompt share a name, variable wins."""
        ctx.vars["data"] = "variable value"
        result = ctx.resolve("data")
        assert result == "variable value"

    def test_prompt_used_when_no_variable(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """When no variable exists, prompt body is used."""
        result = ctx.resolve("data")
        assert result == "prompt body for data"


class TestResolveUnknownName:
    """Unknown names return empty string (tolerant behavior)."""

    def test_unknown_name_returns_empty_string(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """Resolving an unknown name returns empty string."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        result = ctx.resolve("nonexistent")
        assert result == ""


class TestResolveWithDictVariable:
    """Resolve stringifies dict variables as JSON."""

    def test_resolve_dict_variable_returns_json(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """Dict values are JSON-serialized through resolve."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        ctx.vars["findings"] = {"severity": "high", "count": 3}

        result = ctx.resolve("findings")
        assert '"severity"' in result
        assert '"high"' in result


# =============================================================================
# Code generator — _process_prompt_body uses ctx.resolve()
# =============================================================================


class TestCodegenPromptBody:
    """Code generator emits ctx.resolve() calls for $var in prompt bodies."""

    def test_process_prompt_body_generates_resolve(self) -> None:
        """_process_prompt_body generates ctx.resolve('name') calls."""
        from streetrace.dsl.codegen.emitter import CodeEmitter
        from streetrace.dsl.codegen.visitors.workflow import WorkflowVisitor

        emitter = CodeEmitter("test.sr")
        visitor = WorkflowVisitor(emitter)

        result = visitor._process_prompt_body(  # noqa: SLF001
            "Hello $user_name",
        )

        assert "ctx.resolve('user_name')" in result

    def test_process_prompt_body_does_not_use_ctx_vars(self) -> None:
        """_process_prompt_body no longer generates ctx.vars['name']."""
        from streetrace.dsl.codegen.emitter import CodeEmitter
        from streetrace.dsl.codegen.visitors.workflow import WorkflowVisitor

        emitter = CodeEmitter("test.sr")
        visitor = WorkflowVisitor(emitter)

        result = visitor._process_prompt_body(  # noqa: SLF001
            "Analyze $input_prompt",
        )

        assert "ctx.vars[" not in result
        assert "ctx.resolve('input_prompt')" in result

    def test_process_prompt_body_multiple_vars(self) -> None:
        """Multiple $vars in body all generate ctx.resolve() calls."""
        from streetrace.dsl.codegen.emitter import CodeEmitter
        from streetrace.dsl.codegen.visitors.workflow import WorkflowVisitor

        emitter = CodeEmitter("test.sr")
        visitor = WorkflowVisitor(emitter)

        result = visitor._process_prompt_body(  # noqa: SLF001
            "Review $pr_desc for $changes",
        )

        assert "ctx.resolve('pr_desc')" in result
        assert "ctx.resolve('changes')" in result


# =============================================================================
# End-to-end — compile DSL with prompt composition
# =============================================================================


class TestEndToEndPromptComposition:
    """Compile a DSL with prompt composition and verify generated code."""

    def test_generated_code_compiles_with_resolve(self) -> None:
        """Generated code with ctx.resolve() is valid Python syntax."""
        from streetrace.dsl.ast import (
            DslFile,
            FlowDef,
            ModelDef,
            PromptDef,
            ReturnStmt,
            VarRef,
            VersionDecl,
        )
        from streetrace.dsl.codegen.generator import CodeGenerator

        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                PromptDef(
                    name="no_inference",
                    body="Do not infer.",
                ),
                PromptDef(
                    name="reviewer",
                    body="You are a reviewer.\n$no_inference",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(value=VarRef(name="input_prompt")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Code must be valid Python
        compile(code, "<generated>", "exec")

        # Verify ctx.resolve is used (not ctx.vars for prompt interpolation)
        assert "ctx.resolve('no_inference')" in code

    def test_prompt_composition_runtime_evaluation(self) -> None:
        """Composed prompts evaluate correctly at runtime."""
        from streetrace.dsl.runtime.context import WorkflowContext

        workflow = MagicMock()
        ctx = WorkflowContext(workflow=workflow)

        # Set up prompts as the codegen would produce them
        ctx.set_prompts({
            "no_inference": PromptSpec(
                body=lambda _ctx: "ONLY get factual info.",
            ),
            "reviewer": PromptSpec(
                body=lambda ctx: (
                    f"You are a reviewer.\n{ctx.resolve('no_inference')}"
                ),
            ),
        })

        # Evaluate the composed prompt
        reviewer_prompt = ctx._prompts["reviewer"]  # noqa: SLF001
        assert isinstance(reviewer_prompt, PromptSpec)
        result = reviewer_prompt.body(ctx)

        assert "You are a reviewer." in result
        assert "ONLY get factual info." in result
