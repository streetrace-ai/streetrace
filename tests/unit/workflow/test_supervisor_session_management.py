"""Test Supervisor session management functionality.

This module tests how the Supervisor handles session creation, retrieval, and
post-processing of completed workload interactions.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from streetrace.input_handler import InputContext
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorSessionManagement:
    """Test Supervisor session management scenarios."""

    @pytest.mark.asyncio
    async def test_get_or_create_session_called_once(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that get_or_create_session is properly called."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.get_or_create_session = AsyncMock(
            return_value=mock_session,
        )

        mock_event = events_mocker(content="Response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_session_called_once(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that validate_session is properly called."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.validate_session = AsyncMock(
            return_value=mock_session,
        )

        mock_event = events_mocker(content="Response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        shallow_supervisor.session_manager.validate_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_properties_passed_to_workload(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that session properties are correctly passed to workload."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        # Create custom session with specific properties
        custom_session = Mock()
        custom_session.app_name = "custom_app"
        custom_session.user_id = "custom_user"
        custom_session.id = "custom_session_123"

        shallow_supervisor.session_manager.validate_session = AsyncMock(
            return_value=custom_session,
        )

        # Create custom event
        events = [events_mocker(content="Final response.")]
        mock_workload.run_async.return_value = self._async_iter(events)

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert workload.run_async was called with the session
        mock_workload.run_async.assert_called_once()
        call_args = mock_workload.run_async.call_args
        assert call_args[0][0] is custom_session

    @pytest.mark.asyncio
    async def test_post_process_called_with_correct_parameters(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that post_process is called with correct parameters."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert post_process was called with correct parameters
        shallow_supervisor.session_manager.post_process.assert_called_once_with(
            user_input=input_context.user_input,
            original_session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_post_process_called_even_with_escalation(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that post_process is called even when workload escalates."""
        # Arrange
        input_context = InputContext(user_input="Problematic request")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Mock escalation event
        events = [events_mocker(escalate=True, content="Escalation needed")]
        mock_workload.run_async.return_value = self._async_iter(events)

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert post_process was still called
        shallow_supervisor.session_manager.post_process.assert_called_once_with(
            user_input=input_context.user_input,
            original_session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_post_process_called_with_no_final_response(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that post_process is called even when no final response is received."""
        # Arrange
        input_context = InputContext(user_input="Request without response")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Mock only non-final events
        events = [events_mocker(is_final_response=False)]
        mock_workload.run_async.return_value = self._async_iter(events)

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert post_process was still called
        shallow_supervisor.session_manager.post_process.assert_called_once_with(
            user_input=input_context.user_input,
            original_session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_post_process_with_none_payload(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that post_process handles None payload correctly."""
        input_context = InputContext()
        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        # Arrange
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert post_process was called with None payload
        shallow_supervisor.session_manager.post_process.assert_called_once_with(
            user_input=None,
            original_session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_manage_current_session_called_per_event(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that manage_current_session is called for each event."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Create multiple events
        events = [
            events_mocker(is_final_response=False),
            events_mocker(is_final_response=False),
            events_mocker(content="Final response."),
        ]
        mock_workload.run_async.return_value = self._async_iter(events)

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert manage_current_session was called for each event
        assert (
            shallow_supervisor.session_manager.manage_current_session.call_count == 3
        )

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item
