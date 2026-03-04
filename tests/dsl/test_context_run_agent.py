"""Tests for WorkflowContext.run_agent() delegation to workflow.

Test that run_agent properly delegates to the parent workflow.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from google.adk.events import Event

    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.workflow import DslAgentWorkflow


@pytest.fixture
def mock_workflow() -> "DslAgentWorkflow":
    """Create a mock DslAgentWorkflow for testing."""
    return MagicMock()


class TestRunAgentDelegation:
    """Test WorkflowContext.run_agent() delegates to workflow."""

    @pytest.fixture
    def workflow_context(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext with mock workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        # Set up mock run_agent as async generator
        mock_event = MagicMock()

        async def mock_run_agent_gen(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            yield mock_event

        mock_workflow.run_agent = mock_run_agent_gen
        mock_workflow.test_mock_event = mock_event  # Store for tests to access

        return WorkflowContext(workflow=mock_workflow)

    @pytest.mark.asyncio
    async def test_run_agent_delegates_to_workflow(
        self,
        workflow_context: "WorkflowContext",
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent delegates to workflow.run_agent()."""
        # run_agent is now an async generator - collect events
        events = [
            event
            async for event in workflow_context.run_agent("test_agent", "arg1", "arg2")
        ]

        assert len(events) == 1
        assert events[0] is mock_workflow.test_mock_event

    @pytest.mark.asyncio
    async def test_run_agent_passes_all_args(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent passes all arguments to workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        captured_args: list[tuple[str, tuple[object, ...]]] = []

        async def mock_run_agent_gen(
            agent_name: str,
            *args: object,
        ) -> AsyncGenerator["Event", None]:
            captured_args.append((agent_name, args))
            yield MagicMock()

        mock_workflow.run_agent = mock_run_agent_gen

        ctx = WorkflowContext(workflow=mock_workflow)

        _ = [
            event
            async for event in ctx.run_agent("analyzer", "input1", "input2", "input3")
        ]

        assert len(captured_args) == 1
        assert captured_args[0] == ("analyzer", ("input1", "input2", "input3"))

    @pytest.mark.asyncio
    async def test_run_agent_returns_workflow_result(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent yields events from workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        mock_event1 = MagicMock()
        mock_event2 = MagicMock()

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

    @pytest.mark.asyncio
    async def test_run_agent_with_no_args(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent works with just agent name."""
        from streetrace.dsl.runtime.context import WorkflowContext

        captured_args: list[tuple[str, tuple[object, ...]]] = []

        async def mock_run_agent_gen(
            agent_name: str,
            *args: object,
        ) -> AsyncGenerator["Event", None]:
            captured_args.append((agent_name, args))
            yield MagicMock()

        mock_workflow.run_agent = mock_run_agent_gen

        ctx = WorkflowContext(workflow=mock_workflow)

        _ = [event async for event in ctx.run_agent("default")]

        assert len(captured_args) == 1
        assert captured_args[0] == ("default", ())
