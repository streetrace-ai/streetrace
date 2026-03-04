"""Test Supervisor error handling and edge cases.

This module tests how the Supervisor handles various error conditions including
workload creation failures, execution exceptions, and other exceptional scenarios.
"""

from collections.abc import AsyncGenerator
from unittest.mock import Mock

import pytest

from streetrace.input_handler import InputContext
from streetrace.ui.adk_event_renderer import Event as EventWrapper
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorErrorHandling:
    """Test Supervisor error handling scenarios."""

    @pytest.mark.asyncio
    async def test_workload_creation_failure(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
    ) -> None:
        """Test handling when workload creation fails."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock workload creation failure
        shallow_supervisor.workload_manager.create_workload.side_effect = Exception(
            "Workload creation failed",
        )

        # Act & Assert - Exception should propagate (fail-fast for core components)
        with pytest.raises(
            ExceptionGroup,
            check=lambda eg: "Workload creation failed" in str(eg.exceptions[0]),
        ):
            await shallow_supervisor.handle(input_context)

        # Assert session was retrieved but post_process was not called due to failure
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        assert not shallow_supervisor.session_manager.post_process.called

    @pytest.mark.asyncio
    async def test_session_creation_failure(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
    ) -> None:
        """Test handling when session creation/retrieval fails."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        # Mock session creation failure
        shallow_supervisor.session_manager.get_or_create_session.side_effect = (
            Exception("Session creation failed")
        )

        # Act & Assert - Exception should propagate (fail-fast for core components)
        with pytest.raises(Exception, match="Session creation failed"):
            await shallow_supervisor.handle(input_context)

        # Assert workload creation was not attempted
        assert not shallow_supervisor.workload_manager.create_workload.called

    @pytest.mark.asyncio
    async def test_workload_execution_failure(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
    ) -> None:
        """Test handling when workload execution fails."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock workload execution failure
        async def _failing_async_iter(
            session: Mock,  # noqa: ARG001
            content: Mock,  # noqa: ARG001
        ) -> AsyncGenerator[Mock, None]:
            if False:  # Make this an async generator
                yield
            msg = "Workload execution failed"
            raise Exception(msg)  # noqa: TRY002

        mock_workload.run_async = _failing_async_iter

        # Act & Assert - Exception should propagate (fail-fast for core components)
        with pytest.raises(
            ExceptionGroup,
            check=lambda eg: "Workload execution failed" in str(eg.exceptions[0]),
        ):
            await shallow_supervisor.handle(input_context)

        # Assert session and workload were created but post_process was not called
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        shallow_supervisor.workload_manager.create_workload.assert_called_once()
        assert not shallow_supervisor.session_manager.post_process.called

    @pytest.mark.asyncio
    async def test_ui_dispatch_failure_propagates(
        self,
        mock_ui_bus,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
    ) -> None:
        """Test that UI dispatch failures propagate as expected."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock UI dispatch failure
        shallow_supervisor.ui_bus.dispatch_ui_update.side_effect = Exception(
            "UI dispatch failed",
        )

        # Create custom event
        final_event = Mock()
        final_event.is_final_response.return_value = True
        final_event.content = Mock()
        final_event.content.parts = [Mock()]
        final_event.content.parts[0].text = "Response"
        final_event.actions = None

        mock_workload.run_async.return_value = self._async_iter([final_event])

        # Act & Assert - UI failure should propagate
        with pytest.raises(Exception, match="UI dispatch failed"):
            await shallow_supervisor.handle(input_context)

    @pytest.mark.asyncio
    async def test_post_process_failure(
        self,
        mock_session_manager,
        mock_workload_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
    ) -> None:
        """Test that post_process failures dispatch error to UI bus."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock post_process failure
        post_process_error = Exception("Post-process failed")
        shallow_supervisor.session_manager.post_process.side_effect = post_process_error

        # Create custom event
        final_event = Mock()
        final_event.is_final_response.return_value = True
        final_event.content = Mock()
        final_event.content.parts = [Mock()]
        final_event.content.parts[0].text = "Response"
        final_event.actions = None

        mock_workload.run_async.return_value = self._async_iter([final_event])

        # Act & Assert - Exception should propagate (fail-fast for core components)
        with pytest.raises(
            ExceptionGroup,
            check=lambda eg: "Post-process failed" in str(eg.exceptions[0]),
        ):
            await shallow_supervisor.handle(input_context)

        # Assert that error was dispatched to UI bus
        # The UI should have been called twice:
        # 1. For the event during processing
        # 2. For the error when post_process failed
        assert shallow_supervisor.ui_bus.dispatch_ui_update.call_count == 2

        # First call: event wrapper
        first_call = shallow_supervisor.ui_bus.dispatch_ui_update.call_args_list[0]
        assert isinstance(first_call[0][0], EventWrapper)

        # Second call: error event with the post_process failure message
        from streetrace.ui import ui_events

        second_call = shallow_supervisor.ui_bus.dispatch_ui_update.call_args_list[1]
        error_event = second_call[0][0]
        assert isinstance(error_event, ui_events.Error)
        # The error message should contain both the workload name and the exception
        error_str = str(error_event)
        assert "default" in error_str
        assert "Post-process failed" in error_str

    @pytest.mark.asyncio
    async def test_workload_context_manager_exit_failure(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
    ) -> None:
        """Test handling when workload context manager exit fails."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Create custom event
        final_event = Mock()
        final_event.is_final_response.return_value = True
        final_event.content = Mock()
        final_event.content.parts = [Mock()]
        final_event.content.parts[0].text = "Response"
        final_event.actions = None

        # Mock workload with failing exit
        workload_ctx = shallow_supervisor.workload_manager.create_workload.return_value
        workload_ctx.__aexit__.side_effect = Exception("Workload cleanup failed")

        mock_workload.run_async.return_value = self._async_iter([final_event])

        # Act & Assert - Exception should propagate (fail-fast for core components)
        with pytest.raises(
            ExceptionGroup,
            check=lambda eg: "Workload cleanup failed" in str(eg.exceptions[0]),
        ):
            await shallow_supervisor.handle(input_context)

    @pytest.mark.asyncio
    async def test_event_processing_with_missing_attributes(
        self,
        mock_session_manager,
        mock_workload_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
    ) -> None:
        """Test handling events with missing or None attributes."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock event with missing attributes
        problematic_event = Mock()
        problematic_event.is_final_response.return_value = True
        problematic_event.content = None  # Missing content
        problematic_event.actions = None  # Missing actions

        mock_workload.run_async.return_value = self._async_iter([problematic_event])

        # Act - Should handle gracefully
        await shallow_supervisor.handle(input_context)

        # Assert processing completed successfully
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called_once_with(
            EventWrapper(problematic_event),
        )
        shallow_supervisor.session_manager.post_process.assert_called_once()

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item
