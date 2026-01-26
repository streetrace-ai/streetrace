"""Tests for WorkflowContext.run_agent() delegation to workflow.

Test that run_agent properly delegates to the parent workflow.
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.workflow import DslAgentWorkflow


@pytest.fixture
def mock_workflow() -> "DslAgentWorkflow":
    """Create a mock DslAgentWorkflow for testing."""
    workflow = MagicMock()
    workflow.run_agent = AsyncMock(return_value="agent_result")
    return workflow


class TestRunAgentDelegation:
    """Test WorkflowContext.run_agent() delegates to workflow."""

    @pytest.fixture
    def workflow_context(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext with mock workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        return WorkflowContext(workflow=mock_workflow)

    @pytest.mark.asyncio
    async def test_run_agent_delegates_to_workflow(
        self,
        workflow_context: "WorkflowContext",
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent delegates to workflow.run_agent()."""
        result = await workflow_context.run_agent("test_agent", "arg1", "arg2")

        mock_workflow.run_agent.assert_called_once_with("test_agent", "arg1", "arg2")
        assert result == "agent_result"

    @pytest.mark.asyncio
    async def test_run_agent_passes_all_args(
        self,
        workflow_context: "WorkflowContext",
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent passes all arguments to workflow."""
        await workflow_context.run_agent("analyzer", "input1", "input2", "input3")

        mock_workflow.run_agent.assert_called_once_with(
            "analyzer", "input1", "input2", "input3",
        )

    @pytest.mark.asyncio
    async def test_run_agent_returns_workflow_result(
        self,
        workflow_context: "WorkflowContext",
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent returns the result from workflow."""
        mock_workflow.run_agent.return_value = "custom_result"

        result = await workflow_context.run_agent("agent")

        assert result == "custom_result"

    @pytest.mark.asyncio
    async def test_run_agent_with_no_args(
        self,
        workflow_context: "WorkflowContext",
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent works with just agent name."""
        await workflow_context.run_agent("default")

        mock_workflow.run_agent.assert_called_once_with("default")
