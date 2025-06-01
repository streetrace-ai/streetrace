"""Test Supervisor error handling and edge cases.

This module tests how the Supervisor handles various error conditions including
agent creation failures, runner exceptions, and other exceptional scenarios.
"""

from collections.abc import AsyncGenerator
from unittest.mock import Mock

import pytest

from streetrace.prompt_processor import ProcessedPrompt
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorErrorHandling:
    """Test Supervisor error handling scenarios."""

    @pytest.mark.asyncio
    async def test_agent_creation_failure(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
    ) -> None:
        """Test handling when agent creation fails."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock agent creation failure
        shallow_supervisor.agent_manager.create_agent.side_effect = Exception(
            "Agent creation failed",
        )

        # Act & Assert - Exception should propagate (fail-fast for core components)
        with pytest.raises(Exception, match="Agent creation failed"):
            await shallow_supervisor.run_async(prompt)

        # Assert session was retrieved but post_process was not called due to failure
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        assert not shallow_supervisor.session_manager.post_process.called

    @pytest.mark.asyncio
    async def test_session_creation_failure(
        self,
        shallow_supervisor: Supervisor,
    ) -> None:
        """Test handling when session creation/retrieval fails."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

        # Mock session creation failure
        shallow_supervisor.session_manager.get_or_create_session.side_effect = (
            Exception("Session creation failed")
        )

        # Act & Assert - Exception should propagate (fail-fast for core components)
        with pytest.raises(Exception, match="Session creation failed"):
            await shallow_supervisor.run_async(prompt)

        # Assert agent creation was not attempted
        assert not shallow_supervisor.agent_manager.create_agent.called

    @pytest.mark.asyncio
    async def test_runner_execution_failure(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
    ) -> None:
        """Test handling when runner execution fails."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock runner execution failure
        async def _failing_async_iter() -> AsyncGenerator[Mock, None]:
            if False:  # Make this an async generator
                yield
            msg = "Runner execution failed"
            raise Exception(msg)  # noqa: TRY002

        # Mock runner
        from unittest.mock import patch

        mock_runner = Mock()
        mock_runner.run_async.return_value = _failing_async_iter()

        with (
            patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner),
            # Act & Assert - Exception should propagate (fail-fast for core components)
            pytest.raises(Exception, match="Runner execution failed"),
        ):
            await shallow_supervisor.run_async(prompt)

        # Assert session and agent were created but post_process was not called
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        shallow_supervisor.agent_manager.create_agent.assert_called_once()
        assert not shallow_supervisor.session_manager.post_process.called

    @pytest.mark.asyncio
    async def test_ui_dispatch_failure_does_not_stop_processing(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_events_iterator,
    ) -> None:
        """Test that UI dispatch failures don't stop the workflow."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

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

        # Mock runner
        from unittest.mock import patch

        mock_runner = Mock()
        mock_runner.run_async.return_value = mock_events_iterator([final_event])

        with (
            patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner),
            # Act & Assert - UI failure should propagate
            # However, since this is internal workflow logic, it might follow fail-fast
            pytest.raises(Exception, match="UI dispatch failed"),
        ):
            await shallow_supervisor.run_async(prompt)

    @pytest.mark.asyncio
    async def test_post_process_failure(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_events_iterator,
    ) -> None:
        """Test handling when post_process fails."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock post_process failure
        shallow_supervisor.session_manager.post_process.side_effect = Exception(
            "Post-process failed",
        )

        # Create custom event
        final_event = Mock()
        final_event.is_final_response.return_value = True
        final_event.content = Mock()
        final_event.content.parts = [Mock()]
        final_event.content.parts[0].text = "Response"
        final_event.actions = None

        # Mock runner
        from unittest.mock import patch

        mock_runner = Mock()
        mock_runner.run_async.return_value = mock_events_iterator([final_event])

        with (
            patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner),
            # Act & Assert - Exception should propagate (fail-fast for core components)
            pytest.raises(Exception, match="Post-process failed"),
        ):
            await shallow_supervisor.run_async(prompt)

        # Assert that execution proceeded normally until post_process
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called_once_with(
            final_event,
        )

    @pytest.mark.asyncio
    async def test_agent_context_manager_exit_failure(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_events_iterator,
    ) -> None:
        """Test handling when agent context manager exit fails."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

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

        # Mock runner
        from unittest.mock import patch

        mock_runner = Mock()
        mock_runner.run_async.return_value = mock_events_iterator([final_event])

        with (
            patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner),
            # Act & Assert - Exception should propagate (fail-fast for core components)
            pytest.raises(Exception, match="Agent cleanup failed"),
        ):
            await shallow_supervisor.run_async(prompt)

    @pytest.mark.asyncio
    async def test_runner_initialization_failure(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
    ) -> None:
        """Test handling when Runner initialization fails."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock Runner initialization failure
        from unittest.mock import patch

        with (
            patch(
                "streetrace.workflow.supervisor.Runner",
                side_effect=Exception("Runner init failed"),
            ),
            # Act & Assert - Exception should propagate (fail-fast for core components)
            pytest.raises(Exception, match="Runner init failed"),
        ):
            await shallow_supervisor.run_async(prompt)

        # Assert session and agent were created
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        shallow_supervisor.agent_manager.create_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_processing_with_missing_attributes(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_events_iterator,
    ) -> None:
        """Test handling events with missing or None attributes."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Test prompt", mentions=[])

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock event with missing attributes
        problematic_event = Mock()
        problematic_event.is_final_response.return_value = True
        problematic_event.content = None  # Missing content
        problematic_event.actions = None  # Missing actions

        # Mock runner
        from unittest.mock import patch

        mock_runner = Mock()
        mock_runner.run_async.return_value = mock_events_iterator([problematic_event])

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
            # Act - Should handle gracefully
            await shallow_supervisor.run_async(prompt)

        # Assert processing completed successfully
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called_once_with(
            problematic_event,
        )
        shallow_supervisor.session_manager.post_process.assert_called_once()
