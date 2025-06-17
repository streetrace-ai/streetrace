"""Test Supervisor agent interaction and event handling.

This module tests how the Supervisor interacts with agents, processes events from the
agent execution loop, and handles different types of agent responses including final
responses, escalations, and error conditions.
"""

from unittest.mock import Mock, patch

import pytest

from streetrace.prompt_processor import ProcessedPrompt
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorAgentInteraction:
    """Test Supervisor agent interaction scenarios."""

    @pytest.mark.asyncio
    async def test_agent_creation_and_cleanup(
        self,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test that agent is properly created and cleaned up."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_adk_runner(),
        ):
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert agent creation and cleanup
        shallow_supervisor.agent_manager.create_agent.assert_called_once_with("default")
        # Context manager methods are called on the returned value
        create_agent_result = shallow_supervisor.agent_manager.create_agent.return_value
        create_agent_result.__aenter__.assert_called_once()
        create_agent_result.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_runner_initialization_and_execution(
        self,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test that Runner is properly initialized with correct parameters."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_runner = mock_adk_runner()

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_runner,
        ) as runner_context:
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert Runner initialization
        runner_context.assert_called_once_with(
            app_name=mock_session.app_name,
            session_service=shallow_supervisor.session_manager.session_service,
            agent=shallow_supervisor.agent_manager.create_agent.return_value.__aenter__.return_value,
        )

        # Assert Runner execution
        mock_runner.run_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_events_before_final_response(
        self,
        mock_session_manager,
        mock_agent_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
        events_mocker,
    ) -> None:
        """Test processing multiple events before reaching final response."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Complex request", mentions=[])

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        events = [
            events_mocker(is_final_response=False),
            events_mocker(is_final_response=False),
            events_mocker(content="Mock response."),
        ]

        mock_runner = mock_adk_runner(events)

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert all events were dispatched to UI
        assert shallow_supervisor.ui_bus.dispatch_ui_update.call_count == 3
        actual_calls = [
            call[0][0]
            for call in shallow_supervisor.ui_bus.dispatch_ui_update.call_args_list
        ]
        assert actual_calls == events

        # Assert post-processing was called after final response
        shallow_supervisor.session_manager.post_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_escalation_handling(
        self,
        mock_session_manager,
        mock_agent_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
        events_mocker,
    ) -> None:
        """Test handling agent escalation responses."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Problematic request", mentions=[])

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock escalation event
        escalation_event = events_mocker(escalate=True, content=[])

        mock_runner = mock_adk_runner([escalation_event])

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert escalation was handled
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called_once_with(
            escalation_event,
        )
        shallow_supervisor.session_manager.post_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_no_final_response(
        self,
        mock_session_manager,
        mock_agent_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
        events_mocker,
    ) -> None:
        """Test handling when agent produces no final response."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Request without response", mentions=[])

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock only non-final events (no final response)
        event1 = events_mocker(is_final_response=False)
        event2 = events_mocker(is_final_response=False)

        events = [event1, event2]

        mock_runner = mock_adk_runner(events)

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert all events were dispatched
        assert shallow_supervisor.ui_bus.dispatch_ui_update.call_count == 2

        # Assert post-processing was still called (with default final response text)
        shallow_supervisor.session_manager.post_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_final_response_with_no_content_parts(
        self,
        mock_session_manager,
        mock_agent_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
        events_mocker,
    ) -> None:
        """Test handling final response with content but no parts."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test request", mentions=[])

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock final event with content but no parts
        final_event = Mock()
        final_event = events_mocker(content=[])

        mock_runner = mock_adk_runner([final_event])

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert event was dispatched and post-processing occurred
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called_once_with(
            final_event,
        )
        shallow_supervisor.session_manager.post_process.assert_called_once()
