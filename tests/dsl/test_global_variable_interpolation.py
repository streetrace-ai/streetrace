"""Tests for global variable interpolation in prompt lambdas.

Confirm that variables assigned with $ in flows are global and discoverable
from prompt lambdas. Validate behavior for basic types and objects.
"""

import json
from datetime import UTC
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from streetrace.dsl.runtime.workflow import PromptSpec

if TYPE_CHECKING:
    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.workflow import DslAgentWorkflow


async def consume_generator(generator: object) -> list[object]:
    """Consume an async generator and return all events."""
    return [event async for event in generator]  # type: ignore[union-attr]


@pytest.fixture
def mock_workflow() -> "DslAgentWorkflow":
    """Create a mock DslAgentWorkflow for testing."""
    return MagicMock()


class TestGlobalVariableScope:
    """Variables assigned in ctx.vars are global and persist across flows."""

    @pytest.fixture
    def ctx(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext for testing."""
        from streetrace.dsl.runtime.context import WorkflowContext

        return WorkflowContext(workflow=mock_workflow)

    def test_variable_set_in_one_place_visible_everywhere(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """A variable assigned in ctx.vars is immediately readable."""
        ctx.vars["x"] = "123"
        assert ctx.vars["x"] == "123"

    def test_variables_persist_across_simulated_flow_steps(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """Variables set by one flow step are available to subsequent steps."""
        # Simulate flow step 1: assignment
        ctx.vars["pr_description"] = "Add login feature"

        # Simulate flow step 2: a different operation reads the variable
        assert ctx.vars["pr_description"] == "Add login feature"

    def test_builtin_input_prompt_variable(
        self,
    ) -> None:
        """The create_context method sets the input_prompt built-in variable."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow.__new__(DslAgentWorkflow)
        workflow._models = {}  # noqa: SLF001
        workflow._prompts = {}  # noqa: SLF001
        workflow._agents = {}  # noqa: SLF001
        workflow._schemas = {}  # noqa: SLF001
        workflow._context = None  # noqa: SLF001

        ctx = workflow.create_context(input_prompt="hello world")
        assert ctx.vars["input_prompt"] == "hello world"


class TestPromptLambdaInterpolation:
    """Prompt lambdas can access global variables from ctx.vars."""

    @pytest.fixture
    def ctx(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext with prompts that reference variables.

        The lambdas mirror what the codegen now produces:
            prompt reviewer: \"\"\"Review $pr_description for $changes\"\"\"
        compiles to:
            lambda ctx: f\"\"\"Review {ctx.stringify(ctx.vars['pr_description'])}
                         for {ctx.stringify(ctx.vars['changes'])}\"\"\"
        """
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        ctx.set_models({"main": "anthropic/claude-sonnet"})

        ctx.set_prompts({
            "reviewer": PromptSpec(
                body=lambda ctx: (
                    f"Review {ctx.stringify(ctx.vars['pr_description'])} "
                    f"for {ctx.stringify(ctx.vars['changes'])}"
                ),
            ),
            "simple": PromptSpec(
                body=lambda ctx: f"Value is {ctx.stringify(ctx.vars['x'])}",
            ),
        })
        ctx._prompt_models = {"reviewer": "main", "simple": "main"}  # noqa: SLF001

        return ctx

    def test_string_variable_interpolation(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """String variables are interpolated directly into prompt text."""
        ctx.vars["x"] = "hello"

        prompt = ctx._prompts["simple"]  # noqa: SLF001
        assert isinstance(prompt, PromptSpec)
        result = prompt.body(ctx)
        assert result == "Value is hello"

    def test_integer_variable_interpolation(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """Integer variables are converted to string via str()."""
        ctx.vars["x"] = 42

        prompt = ctx._prompts["simple"]  # noqa: SLF001
        assert isinstance(prompt, PromptSpec)
        result = prompt.body(ctx)
        assert result == "Value is 42"

    def test_multiple_variables_interpolation(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """Multiple variables from ctx.vars are interpolated into one prompt."""
        ctx.vars["pr_description"] = "Add authentication"
        ctx.vars["changes"] = "login.py, auth.py"

        prompt = ctx._prompts["reviewer"]  # noqa: SLF001
        assert isinstance(prompt, PromptSpec)
        result = prompt.body(ctx)
        assert result == "Review Add authentication for login.py, auth.py"

    def test_missing_variable_raises_key_error(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """Accessing an undefined variable from a prompt raises KeyError."""
        prompt = ctx._prompts["simple"]  # noqa: SLF001
        assert isinstance(prompt, PromptSpec)
        with pytest.raises(KeyError, match="x"):
            prompt.body(ctx)

    @pytest.mark.asyncio
    async def test_call_llm_interpolates_global_vars(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """call_llm evaluates prompts with global variable values."""
        ctx.vars["x"] = "world"

        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="response")),
            ]
            mock_acompletion.return_value = mock_response

            await consume_generator(ctx.call_llm("simple"))

            mock_acompletion.assert_called_once()
            messages = mock_acompletion.call_args.kwargs.get("messages", [])
            assert messages[0]["content"] == "Value is world"


class TestObjectStringification:
    """Objects (dicts, lists) are serialized as JSON when interpolated."""

    @pytest.fixture
    def ctx(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext with a prompt that interpolates $data."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        ctx.set_models({"main": "anthropic/claude-sonnet"})
        ctx.set_prompts({
            "inspect": PromptSpec(
                body=lambda ctx: f"Data: {ctx.stringify(ctx.vars['data'])}",
            ),
        })
        ctx._prompt_models = {"inspect": "main"}  # noqa: SLF001
        return ctx

    def test_dict_serializes_as_json(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """Dicts are serialized as JSON with double-quoted keys."""
        ctx.vars["data"] = {"severity": "high", "count": 3}

        prompt = ctx._prompts["inspect"]  # noqa: SLF001
        assert isinstance(prompt, PromptSpec)
        result = prompt.body(ctx)

        expected_json = json.dumps({"severity": "high", "count": 3})
        assert f"Data: {expected_json}" == result

    def test_list_serializes_as_json(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """Lists are serialized as JSON arrays."""
        ctx.vars["data"] = ["error1", "error2"]

        prompt = ctx._prompts["inspect"]  # noqa: SLF001
        assert isinstance(prompt, PromptSpec)
        result = prompt.body(ctx)

        assert result == 'Data: ["error1", "error2"]'

    def test_nested_object_serializes_as_json(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """Nested dicts/lists produce valid JSON."""
        ctx.vars["data"] = {
            "finding": {"file": "main.py", "line": 42},
            "tags": ["bug", "security"],
        }

        prompt = ctx._prompts["inspect"]  # noqa: SLF001
        assert isinstance(prompt, PromptSpec)
        result = prompt.body(ctx)

        # The result after "Data: " must be valid JSON
        json_part = result.removeprefix("Data: ")
        parsed = json.loads(json_part)
        assert parsed["finding"]["file"] == "main.py"
        assert parsed["finding"]["line"] == 42
        assert parsed["tags"] == ["bug", "security"]

    def test_boolean_and_null_use_json_conventions(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """JSON booleans (true/false) and null are used instead of Python repr."""
        ctx.vars["data"] = {"active": True, "deleted": False, "note": None}

        prompt = ctx._prompts["inspect"]  # noqa: SLF001
        assert isinstance(prompt, PromptSpec)
        result = prompt.body(ctx)

        assert "true" in result
        assert "false" in result
        assert "null" in result
        # Python repr would produce these — they should NOT appear
        assert "True" not in result
        assert "False" not in result
        assert "None" not in result


class TestStringifyMethod:
    """Direct unit tests for WorkflowContext.stringify()."""

    @pytest.fixture
    def ctx(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext for testing."""
        from streetrace.dsl.runtime.context import WorkflowContext

        return WorkflowContext(workflow=mock_workflow)

    def test_str_passthrough(self, ctx: "WorkflowContext") -> None:
        """Strings pass through unchanged."""
        assert ctx.stringify("hello") == "hello"

    def test_int_uses_str(self, ctx: "WorkflowContext") -> None:
        """Integers use str()."""
        assert ctx.stringify(42) == "42"

    def test_float_uses_str(self, ctx: "WorkflowContext") -> None:
        """Floats use str()."""
        assert ctx.stringify(3.14) == "3.14"

    def test_bool_uses_str(self, ctx: "WorkflowContext") -> None:
        """Booleans use str() when not inside a container."""
        value = True
        assert ctx.stringify(value) == "True"

    def test_dict_uses_json(self, ctx: "WorkflowContext") -> None:
        """Dicts are serialized as JSON."""
        result = ctx.stringify({"key": "value"})
        assert result == '{"key": "value"}'

    def test_list_uses_json(self, ctx: "WorkflowContext") -> None:
        """Lists are serialized as JSON."""
        result = ctx.stringify([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_dict_with_non_serializable_uses_default_str(
        self,
        ctx: "WorkflowContext",
    ) -> None:
        """Non-JSON-serializable values inside dicts fall back to str()."""
        from datetime import datetime

        dt = datetime(2025, 1, 15, 10, 30, tzinfo=UTC)
        result = ctx.stringify({"timestamp": dt})
        parsed = json.loads(result)
        assert parsed["timestamp"] == str(dt)
