"""Tests for telemetry span creation in supervisor."""

from unittest.mock import MagicMock, patch

import pytest

from streetrace.input_handler import InputContext
from streetrace.workflow.supervisor import Supervisor


@pytest.fixture
def mock_tracer():
    """Create a mock tracer for OpenTelemetry."""
    with (
        patch("opentelemetry.trace.get_tracer") as get_tracer_mock,
        patch("opentelemetry.trace.get_current_span") as get_current_span_mock,
    ):
        mock_tracer_obj = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_span.is_recording.return_value = True
        mock_tracer_obj.start_as_current_span.return_value = mock_span
        get_tracer_mock.return_value = mock_tracer_obj
        get_current_span_mock.return_value = mock_span
        yield mock_tracer_obj, mock_span


class TestSupervisorTelemetry:
    """Test Supervisor telemetry span creation."""

    @pytest.mark.asyncio
    async def test_supervisor_creates_streetrace_agent_run_span(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_workload,
        mock_tracer,
        events_mocker,
    ) -> None:
        """Test that supervisor creates a parent span named 'streetrace_agent_run'."""
        tracer, _ = mock_tracer

        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        # Mock event
        mock_event = events_mocker(content="Test response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        ctx = InputContext(user_input="test input", agent_name="test_agent")
        await supervisor.handle(ctx)

        # Verify the span was created with the correct name
        tracer.start_as_current_span.assert_called_once_with("streetrace_agent_run")

    @pytest.mark.asyncio
    async def test_supervisor_span_wraps_entire_workload_run(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_workload,
        mock_tracer,
        events_mocker,
    ) -> None:
        """Test that the span wraps the entire workload run including execution."""
        _, mock_span = mock_tracer

        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        # Mock event
        mock_event = events_mocker(content="Test response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        ctx = InputContext(user_input="test input", agent_name="test_agent")
        await supervisor.handle(ctx)

        # Verify the span's context manager methods were called
        mock_span.__enter__.assert_called_once()
        mock_span.__exit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_supervisor_uses_correct_workload_name(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that supervisor uses the specified workload name."""
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        # Mock event
        mock_event = events_mocker(content="Test response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        ctx = InputContext(user_input="test input", agent_name="custom_workload")
        await supervisor.handle(ctx)

        # Verify the workload manager was called with the correct name
        mock_workload_manager.create_workload.assert_called_once_with("custom_workload")

    @pytest.mark.asyncio
    async def test_supervisor_uses_default_workload_when_none_specified(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that supervisor uses 'default' when no workload name specified."""
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        # Mock event
        mock_event = events_mocker(content="Test response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        ctx = InputContext(user_input="test input")  # No agent_name specified
        await supervisor.handle(ctx)

        # Verify the workload manager was called with "default"
        mock_workload_manager.create_workload.assert_called_once_with("default")

    @pytest.mark.asyncio
    async def test_supervisor_span_created_before_workload_execution(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_workload,
        mock_tracer,
        events_mocker,
    ) -> None:
        """Test that telemetry span is created before workload execution."""
        tracer, mock_span = mock_tracer

        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        # Track execution order
        execution_order = []

        # Mock span enter to track when it happens
        original_enter = mock_span.__enter__

        def track_span_enter(*args, **kwargs):
            execution_order.append("span_enter")
            return original_enter(*args, **kwargs)

        mock_span.__enter__ = track_span_enter

        # Mock workload run_async to track when it happens
        async def track_run_async(
            session,  # noqa: ARG001
            content,  # noqa: ARG001
        ):
            execution_order.append("workload_run")
            mock_event = events_mocker(content="Test response")
            yield mock_event

        mock_workload.run_async = track_run_async

        ctx = InputContext(user_input="test input")
        await supervisor.handle(ctx)

        # Verify span was entered before workload ran
        assert execution_order.index("span_enter") < execution_order.index(
            "workload_run",
        )

    @pytest.mark.asyncio
    async def test_supervisor_span_closed_after_workload_completes(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_workload,
        mock_tracer,
        events_mocker,
    ) -> None:
        """Test that telemetry span is closed after workload completes."""
        _, mock_span = mock_tracer

        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        # Track execution order
        execution_order = []

        # Mock span exit to track when it happens
        original_exit = mock_span.__exit__

        def track_span_exit(*args, **kwargs):
            execution_order.append("span_exit")
            return original_exit(*args, **kwargs)

        mock_span.__exit__ = track_span_exit

        # Mock workload run_async to track completion
        async def track_run_async(
            session,  # noqa: ARG001
            content,  # noqa: ARG001
        ):
            mock_event = events_mocker(content="Test response")
            yield mock_event
            execution_order.append("workload_complete")

        mock_workload.run_async = track_run_async

        ctx = InputContext(user_input="test input")
        await supervisor.handle(ctx)

        # Verify workload completed before span exited
        assert execution_order.index("workload_complete") < execution_order.index(
            "span_exit",
        )

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item
