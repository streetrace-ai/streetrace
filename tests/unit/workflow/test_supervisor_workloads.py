"""Test Supervisor integration with WorkloadManager.

This module tests the Supervisor's ability to work with WorkloadManager
for unified workload execution, including event handling, session management,
and error handling.
"""

from unittest.mock import Mock, patch

import pytest

from streetrace.input_handler import InputContext
from streetrace.ui.adk_event_renderer import Event as EventWrapper
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorWorkloadManagerInitialization:
    """Test Supervisor initialization with WorkloadManager."""

    def test_initialization_stores_workload_manager(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
    ) -> None:
        """Test that Supervisor properly stores workload_manager dependency."""
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        assert supervisor.workload_manager is mock_workload_manager
        assert supervisor.session_manager is mock_session_manager
        assert supervisor.ui_bus is mock_ui_bus

    def test_initialization_with_workload_manager_sets_long_running(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
    ) -> None:
        """Test that Supervisor has long_running flag set."""
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        assert supervisor.long_running is True


class TestSupervisorWorkloadExecution:
    """Test Supervisor workload execution scenarios."""

    @pytest.mark.asyncio
    async def test_handle_creates_workload_via_manager(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that handle() creates workload via workload_manager."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Final response.")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await supervisor.handle(input_context)

        # Assert
        mock_workload_manager.create_workload.assert_called_once_with("default")
        # Context manager methods should be called
        ctx_mgr = mock_workload_manager.create_workload.return_value
        ctx_mgr.__aenter__.assert_called_once()
        ctx_mgr.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_uses_specified_agent_name(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that handle() uses specified agent name from context."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(
            user_input="Test prompt",
            agent_name="custom-agent",
        )
        mock_session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Final response.")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await supervisor.handle(input_context)

        # Assert
        mock_workload_manager.create_workload.assert_called_once_with("custom-agent")

    @pytest.mark.asyncio
    async def test_handle_calls_workload_run_async(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that handle() calls workload.run_async with session and content."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Final response.")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await supervisor.handle(input_context)

        # Assert
        mock_workload.run_async.assert_called_once()
        call_args = mock_workload.run_async.call_args
        assert call_args[0][0] is mock_session  # session argument
        # content argument should be a Content object
        assert call_args[0][1] is not None

    @pytest.mark.asyncio
    async def test_handle_dispatches_events_to_ui(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that handle() dispatches all events from workload to UI."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        event1 = events_mocker(is_final_response=False)
        event2 = events_mocker(is_final_response=False)
        event3 = events_mocker(content="Final response.")
        events = [event1, event2, event3]
        mock_workload.run_async.return_value = self._async_iter(events)

        # Act
        await supervisor.handle(input_context)

        # Assert
        assert mock_ui_bus.dispatch_ui_update.call_count == 3
        actual_calls = [
            call[0][0] for call in mock_ui_bus.dispatch_ui_update.call_args_list
        ]
        assert actual_calls == [
            EventWrapper(event1),
            EventWrapper(event2),
            EventWrapper(event3),
        ]

    @pytest.mark.asyncio
    async def test_handle_manages_session_after_each_event(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that handle() calls session management after each event."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        event1 = events_mocker(is_final_response=False)
        event2 = events_mocker(content="Final response.")
        mock_workload.run_async.return_value = self._async_iter([event1, event2])

        # Act
        await supervisor.handle(input_context)

        # Assert
        assert mock_session_manager.manage_current_session.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_extracts_final_response(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that handle() extracts final response text."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="The final response text.")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await supervisor.handle(input_context)

        # Assert
        assert input_context.final_response == "The final response text."

    @pytest.mark.asyncio
    async def test_handle_calls_post_process(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that handle() calls session_manager.post_process after execution."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Final response.")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await supervisor.handle(input_context)

        # Assert
        mock_session_manager.post_process.assert_called_once()

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item


class TestSupervisorWorkloadTelemetry:
    """Test Supervisor telemetry with WorkloadManager."""

    @pytest.mark.asyncio
    async def test_handle_creates_telemetry_span(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that handle() creates a telemetry span for the agent run."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Final response.")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act & Assert
        with patch("streetrace.workflow.supervisor.trace") as mock_trace:
            mock_tracer = Mock()
            mock_trace.get_tracer.return_value = mock_tracer
            mock_span = Mock()
            mock_span.__enter__ = Mock(return_value=mock_span)
            mock_span.__exit__ = Mock(return_value=None)
            mock_tracer.start_as_current_span.return_value = mock_span

            await supervisor.handle(input_context)

            mock_trace.get_tracer.assert_called_once()
            mock_tracer.start_as_current_span.assert_called_once_with(
                "streetrace_agent_run",
            )

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item


class TestSupervisorWorkloadErrorHandling:
    """Test Supervisor error handling with WorkloadManager."""

    @pytest.mark.asyncio
    async def test_handle_catches_toolset_lifecycle_error(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
    ) -> None:
        """Test that handle() catches ToolsetLifecycleError and dispatches to UI."""
        from streetrace.tools.named_toolset import ToolsetLifecycleError

        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        # Make workload.run_async raise ToolsetLifecycleError
        error = ToolsetLifecycleError("test_toolset", "Test lifecycle error")

        async def raise_error(
            *args,  # noqa: ARG001
            **kwargs,  # noqa: ARG001
        ):
            raise error
            yield  # Unreachable - makes this an async generator

        mock_workload.run_async.return_value = raise_error()

        # Act & Assert
        with pytest.raises(ExceptionGroup):
            await supervisor.handle(input_context)

        # UI should have received error notification
        error_calls = [
            call
            for call in mock_ui_bus.dispatch_ui_update.call_args_list
            if "Error" in str(type(call[0][0]))
        ]
        assert len(error_calls) == 1

    @pytest.mark.asyncio
    async def test_handle_catches_base_exception(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
    ) -> None:
        """Test that handle() catches BaseException and dispatches to UI."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        # Make workload.run_async raise a generic exception
        async def raise_error(
            *args,  # noqa: ARG001
            **kwargs,  # noqa: ARG001
        ):
            raise RuntimeError("Test runtime error")
            yield  # Unreachable - makes this an async generator

        mock_workload.run_async.return_value = raise_error()

        # Act & Assert
        with pytest.raises(ExceptionGroup):
            await supervisor.handle(input_context)

        # UI should have received error notification
        error_calls = [
            call
            for call in mock_ui_bus.dispatch_ui_update.call_args_list
            if "Error" in str(type(call[0][0]))
        ]
        assert len(error_calls) == 1


class TestSupervisorWorkloadEscalation:
    """Test Supervisor escalation handling with WorkloadManager."""

    @pytest.mark.asyncio
    async def test_handle_escalation_response(
        self,
        mock_workload_manager,
        mock_session_manager,
        mock_ui_bus,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that handle() handles escalation responses correctly."""
        # Arrange
        supervisor = Supervisor(
            workload_manager=mock_workload_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        input_context = InputContext(user_input="Test prompt")
        mock_session_manager.validate_session.return_value = mock_session

        escalation_event = events_mocker(escalate=True, content=[])
        mock_workload.run_async.return_value = self._async_iter([escalation_event])

        # Act
        await supervisor.handle(input_context)

        # Assert
        assert "escalated" in input_context.final_response.lower()

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item
