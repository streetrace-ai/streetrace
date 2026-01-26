"""Tests for remaining WorkflowContext methods.

Test process, and escalate_to_human methods.
"""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.workflow import DslAgentWorkflow


@pytest.fixture
def mock_workflow() -> "DslAgentWorkflow":
    """Create a mock DslAgentWorkflow for testing."""
    return MagicMock()


class TestProcess:
    """Test WorkflowContext.process() method."""

    @pytest.fixture
    def workflow_context(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext instance."""
        from streetrace.dsl.runtime.context import WorkflowContext

        return WorkflowContext(workflow=mock_workflow)

    def test_process_returns_input_unchanged(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """Process returns the input when no pipeline is specified."""
        input_data = "Some input data"
        result = workflow_context.process(input_data)
        assert result == input_data

    def test_process_applies_named_pipeline(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """Process can apply a named pipeline to transform data."""
        # Register a simple pipeline
        workflow_context.vars["uppercase_pipeline"] = lambda x: str(x).upper()

        result = workflow_context.process("hello", pipeline="uppercase_pipeline")
        assert result == "HELLO"

    def test_process_chains_multiple_args(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """Process can handle multiple arguments."""
        result = workflow_context.process("arg1", "arg2", "arg3")
        # Default behavior: return first arg
        assert result == "arg1"

    def test_process_returns_none_for_empty_args(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """Process returns None when no arguments provided."""
        result = workflow_context.process()
        assert result is None


class TestEscalateToHuman:
    """Test WorkflowContext.escalate_to_human() method."""

    @pytest.fixture
    def workflow_context(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext instance."""
        from streetrace.dsl.runtime.context import WorkflowContext

        return WorkflowContext(workflow=mock_workflow)

    @pytest.mark.asyncio
    async def test_escalate_to_human_logs_message(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """escalate_to_human logs the escalation message."""
        # This should not raise
        await workflow_context.escalate_to_human("Need human help with this task")

    @pytest.mark.asyncio
    async def test_escalate_to_human_calls_callback(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """escalate_to_human calls the registered callback."""
        callback = MagicMock()
        workflow_context.set_escalation_callback(callback)

        await workflow_context.escalate_to_human("Help needed")

        callback.assert_called_once_with("Help needed")

    @pytest.mark.asyncio
    async def test_escalate_to_human_with_none_message(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """escalate_to_human handles None message gracefully."""
        callback = MagicMock()
        workflow_context.set_escalation_callback(callback)

        await workflow_context.escalate_to_human()

        # Should use default message
        callback.assert_called_once()
        assert callback.call_args[0][0] is not None

    @pytest.mark.asyncio
    async def test_escalate_to_human_without_callback(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """escalate_to_human works without a callback (just logs)."""
        # Should not raise even without callback
        await workflow_context.escalate_to_human("No callback registered")

    @pytest.mark.asyncio
    async def test_escalate_to_human_dispatches_ui_event(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """escalate_to_human dispatches a UI event when ui_bus is set."""
        from streetrace.ui.ui_bus import UiBus

        ui_bus = MagicMock(spec=UiBus)
        workflow_context.set_ui_bus(ui_bus)

        await workflow_context.escalate_to_human("UI escalation message")

        ui_bus.dispatch_ui_update.assert_called_once()


class TestContextConfiguration:
    """Test WorkflowContext configuration methods."""

    def test_set_ui_bus(self, mock_workflow: "DslAgentWorkflow") -> None:
        """set_ui_bus configures the UI bus."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.ui.ui_bus import UiBus

        ctx = WorkflowContext(workflow=mock_workflow)
        ui_bus = MagicMock(spec=UiBus)

        ctx.set_ui_bus(ui_bus)

        assert ctx._ui_bus is ui_bus  # noqa: SLF001

    def test_set_escalation_callback(self, mock_workflow: "DslAgentWorkflow") -> None:
        """set_escalation_callback configures the callback."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        callback = MagicMock()

        ctx.set_escalation_callback(callback)

        assert ctx._escalation_callback is callback  # noqa: SLF001

    def test_set_prompt_models(self, mock_workflow: "DslAgentWorkflow") -> None:
        """set_prompt_models configures prompt-to-model mapping."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        prompt_models = {"greeting": "main", "analysis": "fast"}

        ctx.set_prompt_models(prompt_models)

        assert ctx._prompt_models == prompt_models  # noqa: SLF001
