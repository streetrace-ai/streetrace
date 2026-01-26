"""Tests for WorkflowContext requiring workflow parameter.

Test that WorkflowContext requires a workflow reference and
has no fallback code paths.
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from streetrace.dsl.runtime.workflow import DslAgentWorkflow


@pytest.fixture
def mock_workflow() -> "DslAgentWorkflow":
    """Create a mock DslAgentWorkflow."""
    workflow = MagicMock()
    workflow.run_agent = AsyncMock(return_value="agent_result")
    workflow.run_flow = AsyncMock(return_value="flow_result")
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

        ctx = WorkflowContext(workflow=mock_workflow)

        result = await ctx.run_agent("test_agent", "arg1", "arg2")

        mock_workflow.run_agent.assert_called_once_with("test_agent", "arg1", "arg2")
        assert result == "agent_result"

    @pytest.mark.asyncio
    async def test_run_agent_passes_all_args(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent() passes all arguments to workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)

        await ctx.run_agent("agent", "a", "b", "c")

        mock_workflow.run_agent.assert_called_once_with("agent", "a", "b", "c")

    @pytest.mark.asyncio
    async def test_run_agent_returns_workflow_result(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_agent() returns the result from workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        mock_workflow.run_agent.return_value = "custom_result"
        ctx = WorkflowContext(workflow=mock_workflow)

        result = await ctx.run_agent("agent")

        assert result == "custom_result"


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

        result = await ctx.run_flow("test_flow", "arg1")

        mock_workflow.run_flow.assert_called_once_with("test_flow", "arg1")
        assert result == "flow_result"

    @pytest.mark.asyncio
    async def test_run_flow_passes_all_args(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_flow() passes all arguments to workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)

        await ctx.run_flow("flow", "x", "y", "z")

        mock_workflow.run_flow.assert_called_once_with("flow", "x", "y", "z")

    @pytest.mark.asyncio
    async def test_run_flow_returns_workflow_result(
        self,
        mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """run_flow() returns the result from workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        mock_workflow.run_flow.return_value = "custom_flow_result"
        ctx = WorkflowContext(workflow=mock_workflow)

        result = await ctx.run_flow("flow")

        assert result == "custom_flow_result"


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
