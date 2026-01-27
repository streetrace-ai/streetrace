"""Test Supervisor workload interaction and event handling.

Test how the Supervisor interacts with workloads, processes events from the workload
execution loop, and handles different types of workload responses including final
responses, escalations, and error conditions.
"""

from unittest.mock import Mock

import pytest

from streetrace.input_handler import InputContext
from streetrace.ui.adk_event_renderer import Event as EventWrapper
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorAgentInteraction:
    """Test Supervisor workload interaction scenarios."""

    @pytest.mark.asyncio
    async def test_workload_creation_and_cleanup(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that workload is properly created and cleaned up."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Final response.")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert workload creation and cleanup
        shallow_supervisor.workload_manager.create_workload.assert_called_once_with(
            "default",
        )
        # Context manager methods are called on the returned value
        ctx_mgr = shallow_supervisor.workload_manager.create_workload.return_value
        ctx_mgr.__aenter__.assert_called_once()
        ctx_mgr.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_workload_run_async_called(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that workload.run_async is called with session and content."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Final response.")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert workload.run_async was called with correct arguments
        mock_workload.run_async.assert_called_once()
        call_args = mock_workload.run_async.call_args
        assert call_args[0][0] is mock_session  # session argument
        assert call_args[0][1] is not None  # content argument

    @pytest.mark.asyncio
    async def test_multiple_events_before_final_response(
        self,
        mock_session_manager,
        mock_workload_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test processing multiple events before reaching final response."""
        # Arrange
        input_context = InputContext(user_input="Complex request")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        events = [
            events_mocker(is_final_response=False),
            events_mocker(is_final_response=False),
            events_mocker(content="Mock response."),
        ]

        mock_workload.run_async.return_value = self._async_iter(events)

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert all events were dispatched to UI
        assert shallow_supervisor.ui_bus.dispatch_ui_update.call_count == 3
        actual_calls = [
            call[0][0]
            for call in shallow_supervisor.ui_bus.dispatch_ui_update.call_args_list
        ]
        assert actual_calls == [EventWrapper(event) for event in events]

        # Assert post-processing was called after final response
        shallow_supervisor.session_manager.post_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_workload_escalation_handling(
        self,
        mock_session_manager,
        mock_workload_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test handling workload escalation responses."""
        # Arrange
        input_context = InputContext(user_input="Problematic request")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock escalation event
        escalation_event = events_mocker(escalate=True, content=[])

        mock_workload.run_async.return_value = self._async_iter([escalation_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert escalation was handled
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called_once_with(
            EventWrapper(escalation_event),
        )
        shallow_supervisor.session_manager.post_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_workload_no_final_response(
        self,
        mock_session_manager,
        mock_workload_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test handling when workload produces no final response."""
        # Arrange
        input_context = InputContext(user_input="Request without response")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock only non-final events (no final response)
        event1 = events_mocker(is_final_response=False)
        event2 = events_mocker(is_final_response=False)

        events = [event1, event2]

        mock_workload.run_async.return_value = self._async_iter(events)

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert all events were dispatched
        assert shallow_supervisor.ui_bus.dispatch_ui_update.call_count == 2

        # Assert post-processing was still called (with default final response text)
        shallow_supervisor.session_manager.post_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_final_response_with_no_content_parts(
        self,
        mock_session_manager,
        mock_workload_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test handling final response with content but no parts."""
        # Arrange
        input_context = InputContext(user_input="Test request")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock final event with content but no parts
        final_event = Mock()
        final_event = events_mocker(content=[])

        mock_workload.run_async.return_value = self._async_iter([final_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert event was dispatched and post-processing occurred
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called_once_with(
            EventWrapper(final_event),
        )
        shallow_supervisor.session_manager.post_process.assert_called_once()

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item
