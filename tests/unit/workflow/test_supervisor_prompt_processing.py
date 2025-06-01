"""Test Supervisor prompt processing functionality.

This module tests how the Supervisor handles different types of ProcessedPrompt inputs,
including prompts with file mentions, empty prompts, and various content structures.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from streetrace.prompt_processor import ProcessedPrompt
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorPromptProcessing:
    """Test Supervisor prompt processing scenarios."""

    @pytest.mark.asyncio
    async def test_run_async_with_simple_prompt(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test running with a simple text prompt."""
        # Arrange
        prompt = ProcessedPrompt(prompt="Hello, world!", mentions=[])

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_adk_runner(),
        ):
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        shallow_supervisor.agent_manager.create_agent.assert_called_once_with(
            "default",
        )
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called()
        shallow_supervisor.session_manager.post_process.assert_called_once_with(
            processed_prompt=prompt,
            original_session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_run_async_with_file_mentions(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test running with a prompt that has file mentions."""
        # Arrange
        mentions = [
            (Path("file1.txt"), "Content of file 1"),
            (Path("file2.py"), "print('Hello from file 2')"),
        ]
        prompt = ProcessedPrompt(prompt="Analyze these files", mentions=mentions)

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock runner

        mock_runner = mock_adk_runner()

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert - Verify the runner was called with content containing both prompt
        # and mentions
        mock_runner.run_async.assert_called_once()
        call_args = mock_runner.run_async.call_args

        # Check that new_message contains the expected content structure
        new_message = call_args.kwargs["new_message"]
        assert new_message is not None
        assert new_message.role == "user"
        assert len(new_message.parts) == 3  # 1 prompt + 2 file mentions

        # Verify mentions are formatted correctly
        assert "file1.txt" in new_message.parts[1].text
        assert "Content of file 1" in new_message.parts[1].text
        assert "file2.py" in new_message.parts[2].text
        assert "print('Hello from file 2')" in new_message.parts[2].text

    @pytest.mark.asyncio
    async def test_run_async_with_none_payload(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test running with None payload."""
        # Arrange
        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock runner

        mock_runner = mock_adk_runner()

        with patch(
            "streetrace.workflow.supervisor.Runner",
            return_value=mock_runner,
        ):
            # Act
            await shallow_supervisor.run_async(None)

        # Assert
        mock_runner.run_async.assert_called_once()
        call_args = mock_runner.run_async.call_args

        # new_message should be None when no payload is provided
        new_message = call_args.kwargs["new_message"]
        assert new_message is None

    @pytest.mark.asyncio
    async def test_run_async_with_empty_prompt(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test running with empty prompt text."""
        # Arrange
        prompt = ProcessedPrompt(prompt="", mentions=[])

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock runner
        mock_runner = mock_adk_runner()

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert
        mock_runner.run_async.assert_called_once()
        call_args = mock_runner.run_async.call_args

        # new_message should be None when prompt is empty and no mentions
        new_message = call_args.kwargs["new_message"]
        assert new_message is None

    @pytest.mark.asyncio
    async def test_run_async_with_mentions_only(
        self,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_adk_runner,
    ) -> None:
        """Test running with only file mentions but no prompt text."""
        # Arrange
        mentions = [(Path("config.json"), '{"setting": "value"}')]
        prompt = ProcessedPrompt(prompt="", mentions=mentions)

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        # Mock runner

        mock_runner = mock_adk_runner()

        with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
            # Act
            await shallow_supervisor.run_async(prompt)

        # Assert
        mock_runner.run_async.assert_called_once()
        call_args = mock_runner.run_async.call_args

        # new_message should contain only the file mention
        new_message = call_args.kwargs["new_message"]
        assert new_message is not None
        assert new_message.role == "user"
        assert len(new_message.parts) == 1  # Only 1 file mention
        assert "config.json" in new_message.parts[0].text
        assert '{"setting": "value"}' in new_message.parts[0].text
