"""Test Supervisor session management functionality.

This module tests how the Supervisor handles session creation, retrieval, and
post-processing of completed agent interactions.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from streetrace.input_handler import InputContext
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorSessionManagement:
    """Test Supervisor session management scenarios."""

    @pytest.mark.asyncio
    async def test_get_or_create_session_called_once(
        self,
        mock_session_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test that get_or_create_session is properly called."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager

        shallow_supervisor.session_manager.get_or_create_session = AsyncMock(
            return_value=mock_session,
        )

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_adk_runner(),
        ):
            # Act
            await shallow_supervisor.handle(input_context)

        # Assert
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_session_called_once(
        self,
        mock_session_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test that get_or_create_session is properly called."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager

        shallow_supervisor.session_manager.validate_session = AsyncMock(
            return_value=mock_session,
        )

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_adk_runner(),
        ):
            # Act
            await shallow_supervisor.handle(input_context)

        # Assert
        shallow_supervisor.session_manager.validate_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_properties_used_in_runner(
        self,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
        mock_adk_runner,
        events_mocker,
    ) -> None:
        """Test that session properties are correctly passed to Runner."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager

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

        mock_runner = mock_adk_runner(events)

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_runner,
        ) as mock_runner_patch:
            # Act
            await shallow_supervisor.handle(input_context)

        # Assert Runner was initialized with correct session properties
        mock_runner_patch.assert_called_once_with(
            app_name="custom_app",
            session_service=shallow_supervisor.session_manager.session_service,
            agent=shallow_supervisor.agent_manager.create_agent.return_value.__aenter__.return_value,
        )

        # Assert Runner.run_async was called with correct session properties
        mock_runner.run_async.assert_called_once()
        call_kwargs = mock_runner.run_async.call_args.kwargs
        assert call_kwargs["user_id"] == "custom_user"
        assert call_kwargs["session_id"] == "custom_session_123"

    @pytest.mark.asyncio
    async def test_post_process_called_with_correct_parameters(
        self,
        mock_session_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test that post_process is called with correct parameters."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_adk_runner(),
        ):
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
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
        events_mocker,
    ) -> None:
        """Test that post_process is called even when agent escalates."""
        # Arrange
        input_context = InputContext(user_input="Problematic request")

        shallow_supervisor.session_manager = mock_session_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Mock escalation event
        events = [events_mocker(escalate=True, content="Escalation needed")]

        mock_runner = mock_adk_runner(events)

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
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
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
        events_mocker,
    ) -> None:
        """Test that post_process is called even when no final response is received."""
        # Arrange
        input_context = InputContext(user_input="Request without response")

        shallow_supervisor.session_manager = mock_session_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        # Mock only non-final events
        events = [events_mocker(is_final_response=False)]

        mock_runner = mock_adk_runner(events)

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
            # Act
            await shallow_supervisor.handle(input_context)

        # Assert post_process was still called
        shallow_supervisor.session_manager.post_process.assert_called_once_with(
            user_input=input_context.user_input,
            original_session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_session_service_passed_to_runner(
        self,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test that session service from session manager is passed to Runner."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_adk_runner(),
        ) as mock_runner_patch:
            # Act
            await shallow_supervisor.handle(input_context)

        # Assert Runner was initialized with the session service
        mock_runner_patch.assert_called_once_with(
            app_name=mock_session.app_name,
            session_service=shallow_supervisor.session_manager.session_service,
            agent=shallow_supervisor.agent_manager.create_agent.return_value.__aenter__.return_value,
        )

    @pytest.mark.asyncio
    async def test_post_process_with_none_payload(
        self,
        mock_session_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test that post_process handles None payload correctly."""
        input_context = InputContext()
        shallow_supervisor.session_manager = mock_session_manager
        # Arrange
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_adk_runner(),
        ):
            # Act
            await shallow_supervisor.handle(input_context)

        # Assert post_process was called with None payload
        shallow_supervisor.session_manager.post_process.assert_called_once_with(
            user_input=None,
            original_session=mock_session,
        )
