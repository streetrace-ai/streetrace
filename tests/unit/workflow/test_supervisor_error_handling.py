"""Test Supervisor error handling and edge cases.

This module tests how the Supervisor handles various error conditions including
agent creation failures, runner exceptions, and other exceptional scenarios.
"""

from collections.abc import AsyncGenerator
from unittest.mock import Mock, patch

import pytest

from streetrace.input_handler import InputContext
from streetrace.ui.adk_event_renderer import Event as EventWrapper
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorErrorHandling:
    """Test Supervisor error handling scenarios."""

    @pytest.mark.asyncio
    async def test_agent_creation_failure(
        self,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
        mock_session,
    ) -> None:
        """Test handling when agent creation fails."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock agent creation failure
        shallow_supervisor.agent_manager.create_agent.side_effect = Exception(
            "Agent creation failed",
        )

        # Act & Assert - Exception should propagate (fail-fast for core components)
        with pytest.raises(
            ExceptionGroup,
            check=lambda eg: "Agent creation failed" in str(eg.exceptions[0]),
        ):
            await shallow_supervisor.handle(input_context)

        # Assert session was retrieved but post_process was not called due to failure
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        assert not shallow_supervisor.session_manager.post_process.called

    @pytest.mark.asyncio
    async def test_session_creation_failure(
        self,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
    ) -> None:
        """Test handling when session creation/retrieval fails."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager

        # Mock session creation failure
        shallow_supervisor.session_manager.get_or_create_session.side_effect = (
            Exception("Session creation failed")
        )

        # Act & Assert - Exception should propagate (fail-fast for core components)
        with pytest.raises(Exception, match="Session creation failed"):
            await shallow_supervisor.handle(input_context)

        # Assert agent creation was not attempted
        assert not shallow_supervisor.agent_manager.create_agent.called

    @pytest.mark.asyncio
    async def test_runner_execution_failure(
        self,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
        mock_session,
    ) -> None:
        """Test handling when runner execution fails."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock runner execution failure
        async def _failing_async_iter() -> AsyncGenerator[Mock, None]:
            if False:  # Make this an async generator
                yield
            msg = "Runner execution failed"
            raise Exception(msg)  # noqa: TRY002

        mock_runner = Mock()
        mock_runner.run_async.return_value = _failing_async_iter()

        with (
            patch("google.adk.Runner", return_value=mock_runner),
            # Act & Assert - Exception should propagate (fail-fast for core components)
            pytest.raises(
                ExceptionGroup,
                check=lambda eg: "Runner execution failed" in str(eg.exceptions[0]),
            ),
        ):
            await shallow_supervisor.handle(input_context)

        # Assert session and agent were created but post_process was not called
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        shallow_supervisor.agent_manager.create_agent.assert_called_once()
        assert not shallow_supervisor.session_manager.post_process.called

    @pytest.mark.asyncio
    async def test_ui_dispatch_failure_does_not_stop_processing(
        self,
        mock_ui_bus,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_events_iterator,
    ) -> None:
        """Test that UI dispatch failures don't stop the workflow."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager
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

        mock_runner = Mock()
        mock_runner.run_async.return_value = mock_events_iterator([final_event])

        with (
            patch("google.adk.Runner", return_value=mock_runner),
            # Act & Assert - UI failure should propagate
            # However, since this is internal workflow logic, it might follow fail-fast
            pytest.raises(Exception, match="UI dispatch failed"),
        ):
            await shallow_supervisor.handle(input_context)

    @pytest.mark.asyncio
    async def test_post_process_failure(
        self,
        mock_session_manager,
        mock_agent_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_events_iterator,
    ) -> None:
        """Test that post_process failures dispatch error to UI bus."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager
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

        mock_runner = Mock()
        mock_runner.run_async.return_value = mock_events_iterator([final_event])

        with (
            patch("google.adk.Runner", return_value=mock_runner),
            # Act & Assert - Exception should propagate (fail-fast for core components)
            pytest.raises(
                ExceptionGroup,
                check=lambda eg: "Post-process failed" in str(eg.exceptions[0]),
            ),
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
        # The error message should contain both the agent name and the exception
        error_str = str(error_event)
        assert "default" in error_str
        assert "Post-process failed" in error_str

    @pytest.mark.asyncio
    async def test_agent_context_manager_exit_failure(
        self,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_events_iterator,
    ) -> None:
        """Test handling when agent context manager exit fails."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager

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

        # Mock agent with failing exit
        context_manager = shallow_supervisor.agent_manager.create_agent.return_value
        context_manager.__aexit__.side_effect = Exception("Agent cleanup failed")

        mock_runner = Mock()
        mock_runner.run_async.return_value = mock_events_iterator([final_event])

        with (
            patch("google.adk.Runner", return_value=mock_runner),
            # Act & Assert - Exception should propagate (fail-fast for core components)
            pytest.raises(
                ExceptionGroup,
                check=lambda eg: "Agent cleanup failed" in str(eg.exceptions[0]),
            ),
        ):
            await shallow_supervisor.handle(input_context)

    @pytest.mark.asyncio
    async def test_runner_initialization_failure(
        self,
        mock_session_manager,
        mock_agent_manager,
        shallow_supervisor: Supervisor,
        mock_session,
    ) -> None:
        """Test handling when Runner initialization fails."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        with (
            patch(
                "google.adk.Runner",
                side_effect=Exception("Runner init failed"),
            ),
            # Act & Assert - Exception should propagate (fail-fast for core components)
            pytest.raises(
                ExceptionGroup,
                check=lambda eg: "Runner init failed" in str(eg.exceptions[0]),
            ),
        ):
            await shallow_supervisor.handle(input_context)

        # Assert session and agent were created
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        shallow_supervisor.agent_manager.create_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_processing_with_missing_attributes(
        self,
        mock_session_manager,
        mock_agent_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_events_iterator,
    ) -> None:
        """Test handling events with missing or None attributes."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.agent_manager = mock_agent_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock event with missing attributes
        problematic_event = Mock()
        problematic_event.is_final_response.return_value = True
        problematic_event.content = None  # Missing content
        problematic_event.actions = None  # Missing actions

        # Mock runner

        mock_runner = Mock()
        mock_runner.run_async.return_value = mock_events_iterator([problematic_event])

        with patch("google.adk.Runner", return_value=mock_runner):
            # Act - Should handle gracefully
            await shallow_supervisor.handle(input_context)

        # Assert processing completed successfully
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called_once_with(
            EventWrapper(problematic_event),
        )
        shallow_supervisor.session_manager.post_process.assert_called_once()
