"""Tests for workflow context escalation support.

Test coverage for run_agent_with_escalation(), _check_escalation(),
and get_last_result_with_escalation() methods in WorkflowContext.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.dsl.runtime.context import WorkflowContext


@pytest.fixture
def mock_workflow() -> MagicMock:
    """Create a mock workflow for testing."""
    workflow = MagicMock()
    workflow.run_agent = AsyncMock()
    return workflow


@pytest.fixture
def context(mock_workflow: MagicMock) -> WorkflowContext:
    """Create a workflow context with mock workflow."""
    return WorkflowContext(workflow=mock_workflow)


class TestCheckEscalation:
    """Test _check_escalation helper method."""

    def test_check_escalation_with_normalized_operator_match(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test escalation check with ~ operator matching."""
        # Import the spec classes that will be created
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        # Set up agents with prompt that has escalation condition
        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        context.set_prompts({
            "test_prompt": PromptSpec(
                body=lambda _: "Test prompt",
                escalation=EscalationSpec(op="~", value="DRIFTING"),
            ),
        })

        # Check with matching value (should normalize)
        result = context._check_escalation("test_agent", "**DRIFTING**")  # noqa: SLF001
        assert result is True

    def test_check_escalation_with_normalized_operator_no_match(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test escalation check with ~ operator not matching."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        context.set_prompts({
            "test_prompt": PromptSpec(
                body=lambda _: "Test prompt",
                escalation=EscalationSpec(op="~", value="DRIFTING"),
            ),
        })

        # Check with non-matching value
        result = context._check_escalation("test_agent", "Everything is fine")  # noqa: SLF001
        assert result is False

    def test_check_escalation_with_exact_match_operator(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test escalation check with == operator."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        context.set_prompts({
            "test_prompt": PromptSpec(
                body=lambda _: "Test prompt",
                escalation=EscalationSpec(op="==", value="NEEDS_HUMAN"),
            ),
        })

        # Check with exact match
        result = context._check_escalation("test_agent", "NEEDS_HUMAN")  # noqa: SLF001
        assert result is True

        # Check without exact match (different case)
        result = context._check_escalation("test_agent", "needs_human")  # noqa: SLF001
        assert result is False

    def test_check_escalation_with_not_equal_operator(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test escalation check with != operator."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        context.set_prompts({
            "test_prompt": PromptSpec(
                body=lambda _: "Test prompt",
                escalation=EscalationSpec(op="!=", value="SUCCESS"),
            ),
        })

        # Check with different value - should escalate
        result = context._check_escalation("test_agent", "FAILURE")  # noqa: SLF001
        assert result is True

        # Check with same value - should not escalate
        result = context._check_escalation("test_agent", "SUCCESS")  # noqa: SLF001
        assert result is False

    def test_check_escalation_with_contains_operator(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test escalation check with contains operator."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        context.set_prompts({
            "test_prompt": PromptSpec(
                body=lambda _: "Test prompt",
                escalation=EscalationSpec(op="contains", value="ERROR"),
            ),
        })

        # Check with containing value
        result = context._check_escalation(  # noqa: SLF001
            "test_agent",
            "There was an ERROR in processing",
        )
        assert result is True

        # Check without containing value
        result = context._check_escalation("test_agent", "All good")  # noqa: SLF001
        assert result is False

    def test_check_escalation_with_unknown_agent(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test escalation check returns False for unknown agent."""
        context.set_agents({})
        context.set_prompts({})

        result = context._check_escalation("unknown_agent", "any result")  # noqa: SLF001
        assert result is False

    def test_check_escalation_with_no_escalation_condition(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test escalation check returns False when prompt has no escalation."""
        from streetrace.dsl.runtime.workflow import PromptSpec

        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        context.set_prompts({
            "test_prompt": PromptSpec(
                body=lambda _: "Test prompt",
                escalation=None,
            ),
        })

        result = context._check_escalation("test_agent", "DRIFTING")  # noqa: SLF001
        assert result is False

    def test_check_escalation_with_no_prompt_for_agent(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test escalation check returns False when agent has no prompt."""
        context.set_agents({
            "test_agent": {"instruction": "nonexistent_prompt", "tools": []},
        })
        context.set_prompts({})

        result = context._check_escalation("test_agent", "DRIFTING")  # noqa: SLF001
        assert result is False

    def test_check_escalation_with_backward_compat_lambda_prompt(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test escalation check with old-style lambda prompt (no PromptSpec)."""
        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        # Old-style prompt without PromptSpec wrapper
        context.set_prompts({
            "test_prompt": lambda _: "Test prompt",
        })

        # Should return False without error (backward compat)
        result = context._check_escalation("test_agent", "DRIFTING")  # noqa: SLF001
        assert result is False


class TestRunAgentWithEscalation:
    """Test run_agent_with_escalation method."""

    @pytest.mark.asyncio
    async def test_run_agent_with_escalation_returns_generator(
        self,
        context: WorkflowContext,
        mock_workflow: MagicMock,
    ) -> None:
        """Test that run_agent_with_escalation returns an async generator."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        # Set up mock workflow to return an async generator
        async def mock_run_agent(
            _agent_name: str,
            *_args: object,
        ) -> AsyncGenerator[object, None]:
            yield MagicMock()  # Yield a mock event

        mock_workflow.run_agent = mock_run_agent

        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        context.set_prompts({
            "test_prompt": PromptSpec(
                body=lambda _: "Test prompt",
                escalation=EscalationSpec(op="~", value="DRIFTING"),
            ),
        })

        # Call run_agent_with_escalation
        result_gen = context.run_agent_with_escalation("test_agent", "input")

        # Should be an async generator
        assert hasattr(result_gen, "__anext__")

        # Consume the generator
        events = [event async for event in result_gen]

        # Should have yielded events
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_run_agent_with_escalation_sets_escalation_flag(
        self,
        context: WorkflowContext,
        mock_workflow: MagicMock,
    ) -> None:
        """Test that escalation flag is set correctly after agent run."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        # Set up mock workflow to return an async generator
        # The workflow.run_agent sets _last_call_result on the context
        async def mock_run_agent(
            _agent_name: str,
            *_args: object,
        ) -> AsyncGenerator[object, None]:
            # Simulate final response event
            event = MagicMock()
            event.is_final_response.return_value = True
            event.content.parts = [MagicMock(text="DRIFTING")]
            yield event
            # Simulate what the real workflow does - set result on context
            context._last_call_result = "DRIFTING"  # noqa: SLF001

        mock_workflow.run_agent = mock_run_agent
        mock_workflow._context = context  # noqa: SLF001

        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        context.set_prompts({
            "test_prompt": PromptSpec(
                body=lambda _: "Test prompt",
                escalation=EscalationSpec(op="~", value="DRIFTING"),
            ),
        })

        # Consume the generator
        async for _ in context.run_agent_with_escalation("test_agent", "input"):
            pass

        # Check escalation flag
        _result, escalated = context.get_last_result_with_escalation()
        assert escalated is True


class TestGetLastResultWithEscalation:
    """Test get_last_result_with_escalation method."""

    def test_get_last_result_with_escalation_returns_tuple(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test that get_last_result_with_escalation returns (result, escalated)."""
        # Set internal state
        context._last_call_result = "test result"  # noqa: SLF001
        context._last_escalated = True  # noqa: SLF001

        result, escalated = context.get_last_result_with_escalation()

        assert result == "test result"
        assert escalated is True

    def test_get_last_result_with_escalation_default_values(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test default values for result and escalation flag."""
        result, escalated = context.get_last_result_with_escalation()

        assert result is None
        assert escalated is False


class TestEscalationSpecDataclass:
    """Test EscalationSpec dataclass."""

    def test_creates_escalation_spec(self) -> None:
        """Test creating an EscalationSpec."""
        from streetrace.dsl.runtime.workflow import EscalationSpec

        spec = EscalationSpec(op="~", value="DRIFTING")
        assert spec.op == "~"
        assert spec.value == "DRIFTING"

    def test_creates_escalation_spec_all_operators(self) -> None:
        """Test creating EscalationSpec with all operators."""
        from streetrace.dsl.runtime.workflow import EscalationSpec

        operators = ["~", "==", "!=", "contains"]
        for op in operators:
            spec = EscalationSpec(op=op, value="TEST")
            assert spec.op == op


class TestPromptSpecDataclass:
    """Test PromptSpec dataclass."""

    def test_creates_prompt_spec_minimal(self) -> None:
        """Test creating a PromptSpec with only body."""
        from streetrace.dsl.runtime.workflow import PromptSpec

        spec = PromptSpec(body=lambda _: "Test prompt")
        assert callable(spec.body)
        assert spec.model is None
        assert spec.escalation is None

    def test_creates_prompt_spec_with_escalation(self) -> None:
        """Test creating a PromptSpec with escalation."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        escalation = EscalationSpec(op="~", value="DRIFTING")
        spec = PromptSpec(
            body=lambda _: "Test prompt",
            escalation=escalation,
        )
        assert spec.escalation is not None
        assert spec.escalation.op == "~"
        assert spec.escalation.value == "DRIFTING"

    def test_creates_prompt_spec_with_model(self) -> None:
        """Test creating a PromptSpec with model."""
        from streetrace.dsl.runtime.workflow import PromptSpec

        spec = PromptSpec(
            body=lambda _: "Test prompt",
            model="main",
        )
        assert spec.model == "main"
