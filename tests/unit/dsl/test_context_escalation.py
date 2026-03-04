"""Tests for workflow context escalation support.

Test coverage for run_agent_with_escalation(),
EscalationHandler.check(), and get_last_result_with_escalation()
methods in WorkflowContext.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.dsl.runtime.context import WorkflowContext
from streetrace.dsl.runtime.escalation_handler import EscalationHandler


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


def _make_handler(
    agents: dict[str, dict[str, object]],
    prompts: dict[str, object],
) -> EscalationHandler:
    """Create an EscalationHandler with given definitions."""
    return EscalationHandler(agents=agents, prompts=prompts)


class TestCheckEscalation:
    """Test EscalationHandler.check method."""

    def test_check_escalation_with_normalized_operator_match(self) -> None:
        """Test escalation check with ~ operator matching."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        handler = _make_handler(
            agents={"test_agent": {"instruction": "test_prompt", "tools": []}},
            prompts={
                "test_prompt": PromptSpec(
                    body=lambda _: "Test prompt",
                    escalation=EscalationSpec(op="~", value="DRIFTING"),
                ),
            },
        )

        result = handler.check("test_agent", "**DRIFTING**")
        assert result is True

    def test_check_escalation_with_normalized_operator_no_match(self) -> None:
        """Test escalation check with ~ operator not matching."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        handler = _make_handler(
            agents={"test_agent": {"instruction": "test_prompt", "tools": []}},
            prompts={
                "test_prompt": PromptSpec(
                    body=lambda _: "Test prompt",
                    escalation=EscalationSpec(op="~", value="DRIFTING"),
                ),
            },
        )

        result = handler.check("test_agent", "Everything is fine")
        assert result is False

    def test_check_escalation_with_exact_match_operator(self) -> None:
        """Test escalation check with == operator."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        handler = _make_handler(
            agents={"test_agent": {"instruction": "test_prompt", "tools": []}},
            prompts={
                "test_prompt": PromptSpec(
                    body=lambda _: "Test prompt",
                    escalation=EscalationSpec(op="==", value="NEEDS_HUMAN"),
                ),
            },
        )

        assert handler.check("test_agent", "NEEDS_HUMAN") is True
        assert handler.check("test_agent", "needs_human") is False

    def test_check_escalation_with_not_equal_operator(self) -> None:
        """Test escalation check with != operator."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        handler = _make_handler(
            agents={"test_agent": {"instruction": "test_prompt", "tools": []}},
            prompts={
                "test_prompt": PromptSpec(
                    body=lambda _: "Test prompt",
                    escalation=EscalationSpec(op="!=", value="SUCCESS"),
                ),
            },
        )

        assert handler.check("test_agent", "FAILURE") is True
        assert handler.check("test_agent", "SUCCESS") is False

    def test_check_escalation_with_contains_operator(self) -> None:
        """Test escalation check with contains operator."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        handler = _make_handler(
            agents={"test_agent": {"instruction": "test_prompt", "tools": []}},
            prompts={
                "test_prompt": PromptSpec(
                    body=lambda _: "Test prompt",
                    escalation=EscalationSpec(op="contains", value="ERROR"),
                ),
            },
        )

        assert handler.check(
            "test_agent", "There was an ERROR in processing",
        ) is True
        assert handler.check("test_agent", "All good") is False

    def test_check_escalation_with_unknown_agent(self) -> None:
        """Test escalation check returns False for unknown agent."""
        handler = _make_handler(agents={}, prompts={})
        assert handler.check("unknown_agent", "any result") is False

    def test_check_escalation_with_no_escalation_condition(self) -> None:
        """Test escalation check returns False when prompt has no escalation."""
        from streetrace.dsl.runtime.workflow import PromptSpec

        handler = _make_handler(
            agents={"test_agent": {"instruction": "test_prompt", "tools": []}},
            prompts={
                "test_prompt": PromptSpec(
                    body=lambda _: "Test prompt",
                    escalation=None,
                ),
            },
        )

        assert handler.check("test_agent", "DRIFTING") is False

    def test_check_escalation_with_no_prompt_for_agent(self) -> None:
        """Test escalation check returns False when agent has no prompt."""
        handler = _make_handler(
            agents={
                "test_agent": {"instruction": "nonexistent_prompt", "tools": []},
            },
            prompts={},
        )

        assert handler.check("test_agent", "DRIFTING") is False

    def test_check_escalation_with_backward_compat_lambda_prompt(self) -> None:
        """Test escalation check with old-style lambda prompt (no PromptSpec)."""
        handler = _make_handler(
            agents={"test_agent": {"instruction": "test_prompt", "tools": []}},
            prompts={"test_prompt": lambda _: "Test prompt"},
        )

        assert handler.check("test_agent", "DRIFTING") is False


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

        async def mock_run_agent(
            _agent_name: str,
            *_args: object,
        ) -> AsyncGenerator[object, None]:
            yield MagicMock()

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

        result_gen = context.run_agent_with_escalation("test_agent", "input")
        assert hasattr(result_gen, "__anext__")

        events = [event async for event in result_gen]
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_run_agent_with_escalation_sets_escalation_flag(
        self,
        context: WorkflowContext,
        mock_workflow: MagicMock,
    ) -> None:
        """Test that escalation flag is set correctly after agent run."""
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        async def mock_run_agent(
            _agent_name: str,
            *_args: object,
        ) -> AsyncGenerator[object, None]:
            event = MagicMock()
            event.is_final_response.return_value = True
            event.content.parts = [MagicMock(text="DRIFTING")]
            yield event
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

        async for _ in context.run_agent_with_escalation("test_agent", "input"):
            pass

        _result, escalated = context.get_last_result_with_escalation()
        assert escalated is True


class TestGetLastResultWithEscalation:
    """Test get_last_result_with_escalation method."""

    def test_get_last_result_with_escalation_returns_tuple(
        self,
        context: WorkflowContext,
    ) -> None:
        """Test that get_last_result_with_escalation returns (result, escalated)."""
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
