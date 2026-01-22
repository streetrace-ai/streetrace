"""Test Supervisor final response handling.

Test the Supervisor's ability to capture and store final responses from workloads
in the InputContext for downstream processing (e.g., output file writing).
"""

import pytest

from streetrace.input_handler import InputContext
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorFinalResponse:
    """Test Supervisor final response capture functionality."""

    @pytest.mark.asyncio
    async def test_final_response_stored_in_context(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that final response is stored in InputContext."""
        # Arrange
        final_response_text = "This is the final response from the workload."
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Create a final response event
        final_event = events_mocker(content=final_response_text, is_final_response=True)
        mock_workload.run_async.return_value = self._async_iter([final_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        assert input_context.final_response == final_response_text

    @pytest.mark.asyncio
    async def test_final_response_multipart_content(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test final response handling with multipart content."""
        # Arrange
        # Note: Implementation takes first part's text for final_response
        final_response_text = "First part of response"
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Create event with multiple parts
        final_event = events_mocker(
            content=[final_response_text, "Second part"],
            is_final_response=True,
        )
        mock_workload.run_async.return_value = self._async_iter([final_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        assert input_context.final_response == final_response_text

    @pytest.mark.asyncio
    async def test_final_response_not_set_for_non_final_events(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that final_response is not set for non-final events."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Create non-final events
        non_final_event = events_mocker(
            content="Intermediate response",
            is_final_response=False,
        )
        mock_workload.run_async.return_value = self._async_iter([non_final_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - should have default message since no final event was encountered
        assert input_context.final_response == "Agent did not produce a final response."

    @pytest.mark.asyncio
    async def test_final_response_escalation_handling(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test final response handling for escalation events."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Create escalation event
        escalation_event = events_mocker(
            content=None,
            is_final_response=True,
            escalate=True,
        )
        # Ensure content is None for escalation
        escalation_event.content = None
        escalation_event.error_message = "Custom error message"
        mock_workload.run_async.return_value = self._async_iter([escalation_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        expected_response = "Agent escalated: Custom error message"
        assert input_context.final_response == expected_response

    @pytest.mark.asyncio
    async def test_final_response_escalation_no_error_message(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test final response handling for escalation without error message."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Create escalation event without error message
        escalation_event = events_mocker(
            content=None,
            is_final_response=True,
            escalate=True,
        )
        # Ensure content is None for escalation
        escalation_event.content = None
        escalation_event.error_message = None
        mock_workload.run_async.return_value = self._async_iter([escalation_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        expected_response = "Agent escalated: No specific message."
        assert input_context.final_response == expected_response

    @pytest.mark.asyncio
    async def test_final_response_empty_content(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test handling of final response with empty content."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Create final event with no content
        final_event = events_mocker(content=None, is_final_response=True)
        final_event.content = None
        final_event.actions = None
        mock_workload.run_async.return_value = self._async_iter([final_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - Should get default message
        assert input_context.final_response == "Agent did not produce a final response."

    @pytest.mark.asyncio
    async def test_final_response_multiple_final_events(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that processing stops at first final response event."""
        # Arrange
        first_final_response = "First final response"
        second_final_response = "Second final response"
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Create multiple final events
        first_final_event = events_mocker(
            content=first_final_response,
            is_final_response=True,
        )
        second_final_event = events_mocker(
            content=second_final_response,
            is_final_response=True,
        )

        mock_workload.run_async.return_value = self._async_iter(
            [first_final_event, second_final_event],
        )

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - Should only capture the first final response
        assert input_context.final_response == first_final_response

    @pytest.mark.asyncio
    async def test_final_response_no_final_event(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test behavior when no final response event is generated."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Create only non-final events
        non_final_event = events_mocker(content="Intermediate", is_final_response=False)
        mock_workload.run_async.return_value = self._async_iter([non_final_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - Should get default message
        assert input_context.final_response == "Agent did not produce a final response."

    @pytest.mark.asyncio
    async def test_final_response_with_post_processing(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test that post_process is called when final response is available."""
        # Arrange
        final_response_text = "Final response for post processing"
        user_input = "Test prompt"
        input_context = InputContext(user_input=user_input)

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        final_event = events_mocker(content=final_response_text, is_final_response=True)
        mock_workload.run_async.return_value = self._async_iter([final_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        assert input_context.final_response == final_response_text
        shallow_supervisor.session_manager.post_process.assert_called_once_with(
            user_input=user_input,
            original_session=mock_session,
        )

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item
