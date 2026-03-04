"""Tests for EscalationEvent flow event.

Test the EscalationEvent dataclass and its integration with
run_agent_with_escalation() for signaling escalation to parent agents.
"""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest

from streetrace.dsl.runtime.context import WorkflowContext
from streetrace.dsl.runtime.events import EscalationEvent, FlowEvent


class TestEscalationEventCreation:
    """Test EscalationEvent dataclass creation."""

    def test_creates_escalation_event_with_required_fields(self) -> None:
        """Test creating an EscalationEvent with required fields."""
        event = EscalationEvent(
            agent_name="test_agent",
            result="DRIFTING",
            condition_op="~",
            condition_value="DRIFTING",
        )

        assert event.agent_name == "test_agent"
        assert event.result == "DRIFTING"
        assert event.condition_op == "~"
        assert event.condition_value == "DRIFTING"
        assert event.type == "escalation"

    def test_escalation_event_is_flow_event(self) -> None:
        """Test that EscalationEvent is a FlowEvent subclass."""
        event = EscalationEvent(
            agent_name="agent1",
            result="STOP",
            condition_op="==",
            condition_value="STOP",
        )

        assert isinstance(event, FlowEvent)

    def test_escalation_event_type_is_immutable(self) -> None:
        """Test that type field is set automatically and not changeable via init."""
        event = EscalationEvent(
            agent_name="agent1",
            result="result",
            condition_op="~",
            condition_value="value",
        )

        # Type should always be "escalation"
        assert event.type == "escalation"

    def test_escalation_event_all_operators(self) -> None:
        """Test creating EscalationEvent with all supported operators."""
        operators = ["~", "==", "!=", "contains"]

        for op in operators:
            event = EscalationEvent(
                agent_name="test",
                result="result",
                condition_op=op,
                condition_value="value",
            )
            assert event.condition_op == op


class TestEscalationEventYielding:
    """Test that run_agent_with_escalation yields EscalationEvent."""

    @pytest.fixture
    def mock_workflow(self) -> MagicMock:
        """Create a mock workflow for testing."""
        return MagicMock()

    @pytest.fixture
    def context(self, mock_workflow: MagicMock) -> WorkflowContext:
        """Create a workflow context with mock workflow."""
        return WorkflowContext(workflow=mock_workflow)

    @pytest.mark.asyncio
    async def test_yields_escalation_event_when_triggered(
        self,
        context: WorkflowContext,
        mock_workflow: MagicMock,
    ) -> None:
        """Test that EscalationEvent is yielded when escalation triggers."""
        from google.adk.events import Event

        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        # Create a mock ADK event with author attribute
        mock_adk_event = MagicMock(spec=Event)
        mock_adk_event.author = "test_agent"

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator[Event, None]:
            context._last_call_result = "**Drifting.**"  # noqa: SLF001
            yield mock_adk_event

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

        # Collect all yielded events
        events = [
            event
            async for event in context.run_agent_with_escalation("test_agent", "input")
        ]

        # Should yield: ADK event, EscalationEvent, ADK Event with escalate flag
        assert len(events) == 3
        assert events[0] is mock_adk_event
        assert isinstance(events[1], EscalationEvent)
        assert isinstance(events[2], Event)

        # Verify EscalationEvent content
        escalation_event = events[1]
        assert escalation_event.agent_name == "test_agent"
        assert escalation_event.result == "**Drifting.**"
        assert escalation_event.condition_op == "~"
        assert escalation_event.condition_value == "DRIFTING"

        # Verify ADK Event has escalate flag set
        adk_escalate_event = events[2]
        assert adk_escalate_event.actions.escalate is True

    @pytest.mark.asyncio
    async def test_no_escalation_event_when_not_triggered(
        self,
        context: WorkflowContext,
        mock_workflow: MagicMock,
    ) -> None:
        """Test that no EscalationEvent is yielded when escalation not triggered."""
        from google.adk.events import Event

        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        mock_adk_event = MagicMock(spec=Event)

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator[Event, None]:
            context._last_call_result = "SUCCESS"  # noqa: SLF001
            yield mock_adk_event

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

        events = [
            event
            async for event in context.run_agent_with_escalation("test_agent", "input")
        ]

        # Should only yield the ADK event, no EscalationEvent
        assert len(events) == 1
        assert events[0] is mock_adk_event

    @pytest.mark.asyncio
    async def test_no_escalation_event_when_no_condition(
        self,
        context: WorkflowContext,
        mock_workflow: MagicMock,
    ) -> None:
        """Test that no EscalationEvent is yielded when prompt has no escalation."""
        from google.adk.events import Event

        from streetrace.dsl.runtime.workflow import PromptSpec

        mock_adk_event = MagicMock(spec=Event)

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator[Event, None]:
            context._last_call_result = "DRIFTING"  # noqa: SLF001
            yield mock_adk_event

        mock_workflow.run_agent = mock_run_agent

        context.set_agents({
            "test_agent": {"instruction": "test_prompt", "tools": []},
        })
        context.set_prompts({
            "test_prompt": PromptSpec(
                body=lambda _: "Test prompt",
                escalation=None,
            ),
        })

        events = [
            event
            async for event in context.run_agent_with_escalation("test_agent", "input")
        ]

        # Should only yield the ADK event, no EscalationEvent
        assert len(events) == 1
        assert events[0] is mock_adk_event

    @pytest.mark.asyncio
    async def test_escalation_event_appears_after_agent_events(
        self,
        context: WorkflowContext,
        mock_workflow: MagicMock,
    ) -> None:
        """Test that EscalationEvent appears after all agent events."""
        from google.adk.events import Event

        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        mock_event1 = MagicMock(spec=Event)
        mock_event1.author = "test_agent"
        mock_event2 = MagicMock(spec=Event)
        mock_event2.author = "test_agent"
        mock_event3 = MagicMock(spec=Event)
        mock_event3.author = "test_agent"

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator[Event, None]:
            yield mock_event1
            yield mock_event2
            yield mock_event3
            context._last_call_result = "DRIFTING"  # noqa: SLF001

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

        events = [
            event
            async for event in context.run_agent_with_escalation("test_agent", "input")
        ]

        # Should yield agent events, EscalationEvent, and ADK escalate event
        assert len(events) == 5
        assert events[0] is mock_event1
        assert events[1] is mock_event2
        assert events[2] is mock_event3
        assert isinstance(events[3], EscalationEvent)
        assert isinstance(events[4], Event)
        assert events[4].actions.escalate is True

    @pytest.mark.asyncio
    async def test_escalation_event_with_all_operators(
        self,
        context: WorkflowContext,
        mock_workflow: MagicMock,
    ) -> None:
        """Test that EscalationEvent includes correct operator for all types."""
        from google.adk.events import Event

        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        test_cases = [
            ("~", "DRIFTING", "**Drifting.**"),
            ("==", "EXACT", "EXACT"),
            ("!=", "SUCCESS", "FAILURE"),
            ("contains", "ERROR", "Found ERROR in data"),
        ]

        for op, value, result in test_cases:
            mock_adk_event = MagicMock(spec=Event)
            mock_adk_event.author = "test_agent"

            async def mock_run_agent(
                agent_name: str,  # noqa: ARG001
                *args: object,  # noqa: ARG001
                result_value: str = result,
                event: MagicMock = mock_adk_event,
            ) -> AsyncGenerator[Event, None]:
                context._last_call_result = result_value  # noqa: SLF001
                yield event

            mock_workflow.run_agent = mock_run_agent

            context.set_agents({
                "test_agent": {"instruction": "test_prompt", "tools": []},
            })
            context.set_prompts({
                "test_prompt": PromptSpec(
                    body=lambda _: "Test prompt",
                    escalation=EscalationSpec(op=op, value=value),
                ),
            })

            events = [
                event
                async for event in context.run_agent_with_escalation(
                    "test_agent",
                    "input",
                )
            ]

            # Should include EscalationEvent with correct operator
            escalation_events = [
                e for e in events if isinstance(e, EscalationEvent)
            ]
            assert len(escalation_events) == 1, f"Expected escalation for op={op}"
            assert escalation_events[0].condition_op == op
            assert escalation_events[0].condition_value == value

            # Should also include ADK Event with escalate flag
            adk_escalate_events = [
                e for e in events
                if isinstance(e, Event) and hasattr(e, "actions")
                and getattr(e.actions, "escalate", None) is True
            ]
            assert len(adk_escalate_events) == 1, f"Expected ADK escalate for op={op}"
