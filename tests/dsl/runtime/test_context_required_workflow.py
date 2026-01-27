"""Tests for WorkflowContext requiring workflow parameter.

Test that WorkflowContext requires a workflow reference and
has no fallback code paths.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from google.adk.events import Event

    from streetrace.dsl.runtime.workflow import DslAgentWorkflow


async def async_gen_flow_result() -> AsyncGenerator[str, None]:
    """Create async generator that yields flow_result."""
    yield "flow_result"


@pytest.fixture
def mock_workflow() -> "DslAgentWorkflow":
    """Create a mock DslAgentWorkflow."""
    workflow = MagicMock()
    # run_flow is now an async generator
    workflow.run_flow = MagicMock(return_value=async_gen_flow_result())
    return workflow


class TestWorkflowContextRequiredWorkflow:
    """Test that WorkflowContext requires a workflow parameter."""

    def test_workflow_context_requires_workflow_parameter(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """WorkflowContext requires workflow parameter."""
        from streetrace.dsl.runtime.context import WorkflowContext

        # Should work with workflow provided
        ctx = WorkflowContext(workflow=mock_workflow)
        assert ctx._workflow is mock_workflow  # noqa: SLF001

    def test_workflow_context_stores_workflow_reference(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """WorkflowContext stores the workflow reference internally."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)

        assert ctx._workflow is mock_workflow  # noqa: SLF001

    def test_workflow_context_initializes_vars_dict(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """WorkflowContext initializes vars as empty dict."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)

        assert ctx.vars == {}

    def test_workflow_context_initializes_message_string(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """WorkflowContext initializes message as empty string."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)

        assert ctx.message == ""

    def test_workflow_context_initializes_guardrails(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """WorkflowContext initializes guardrails provider."""
        from streetrace.dsl.runtime.context import GuardrailProvider, WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)

        assert isinstance(ctx.guardrails, GuardrailProvider)


class TestRunAgentDelegation:
    """Test that run_agent always delegates to workflow."""

    @pytest.mark.asyncio
    async def test_run_agent_delegates_to_workflow(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent() delegates to workflow.run_agent()."""
        from streetrace.dsl.runtime.context import WorkflowContext

        # Create mock event
        mock_event = MagicMock()

        # Mock run_agent as async generator
        async def mock_run_agent_gen(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            yield mock_event

        mock_workflow.run_agent = mock_run_agent_gen

        ctx = WorkflowContext(workflow=mock_workflow)

        # run_agent is now an async generator - collect events
        events = [event async for event in ctx.run_agent("test_agent", "arg1", "arg2")]

        assert len(events) == 1
        assert events[0] is mock_event

    @pytest.mark.asyncio
    async def test_run_agent_passes_all_args(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent() passes all arguments to workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        captured_args: list[tuple[str, tuple[object, ...]]] = []

        # Mock run_agent as async generator that captures args
        async def mock_run_agent_gen(
            agent_name: str,
            *args: object,
        ) -> AsyncGenerator["Event", None]:
            captured_args.append((agent_name, args))
            yield MagicMock()

        mock_workflow.run_agent = mock_run_agent_gen

        ctx = WorkflowContext(workflow=mock_workflow)

        # Consume the generator to trigger execution
        _ = [event async for event in ctx.run_agent("agent", "a", "b", "c")]

        assert len(captured_args) == 1
        assert captured_args[0] == ("agent", ("a", "b", "c"))

    @pytest.mark.asyncio
    async def test_run_agent_returns_workflow_result(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent() yields events from workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        mock_event1 = MagicMock()
        mock_event2 = MagicMock()

        # Mock run_agent as async generator that yields multiple events
        async def mock_run_agent_gen(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            yield mock_event1
            yield mock_event2

        mock_workflow.run_agent = mock_run_agent_gen

        ctx = WorkflowContext(workflow=mock_workflow)

        events = [event async for event in ctx.run_agent("agent")]

        assert len(events) == 2
        assert events[0] is mock_event1
        assert events[1] is mock_event2


class TestRunFlowDelegation:
    """Test that run_flow always delegates to workflow."""

    @pytest.mark.asyncio
    async def test_run_flow_delegates_to_workflow(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_flow() delegates to workflow.run_flow()."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)

        # run_flow is now an async generator - collect events
        events = [event async for event in ctx.run_flow("test_flow", "arg1")]

        mock_workflow.run_flow.assert_called_once_with("test_flow", "arg1")
        assert events == ["flow_result"]

    @pytest.mark.asyncio
    async def test_run_flow_passes_all_args(
        self,
    ) -> None:
        """run_flow() passes all arguments to workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        # Create fresh mock for this test
        workflow = MagicMock()
        workflow.run_flow = MagicMock(return_value=async_gen_flow_result())

        ctx = WorkflowContext(workflow=workflow)

        # run_flow is now an async generator - consume it
        _ = [event async for event in ctx.run_flow("flow", "x", "y", "z")]

        workflow.run_flow.assert_called_once_with("flow", "x", "y", "z")

    @pytest.mark.asyncio
    async def test_run_flow_yields_events_from_workflow(
        self,
    ) -> None:
        """run_flow() yields events from workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        async def custom_flow_gen() -> AsyncGenerator[str, None]:
            yield "event1"
            yield "event2"

        workflow = MagicMock()
        workflow.run_flow = MagicMock(return_value=custom_flow_gen())

        ctx = WorkflowContext(workflow=workflow)

        events = [event async for event in ctx.run_flow("flow")]

        assert events == ["event1", "event2"]


class TestNoFallbackMethods:
    """Test that fallback methods have been removed."""

    def test_no_run_agent_fallback_method(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """WorkflowContext should not have _run_agent_fallback method."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)

        assert not hasattr(ctx, "_run_agent_fallback")

    def test_no_run_flow_fallback_method(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """WorkflowContext should not have _run_flow_fallback method."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)

        assert not hasattr(ctx, "_run_flow_fallback")
