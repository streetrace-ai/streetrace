"""Test Supervisor prompt processing functionality.

This module tests how the Supervisor handles different types of ProcessedPrompt inputs,
including prompts with file mentions, empty prompts, and various content structures.
"""

from pathlib import Path

import pytest

from streetrace.input_handler import InputContext
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorPromptProcessing:
    """Test Supervisor prompt processing scenarios."""

    @pytest.mark.asyncio
    async def test_run_async_with_simple_prompt(
        self,
        mock_session_manager,
        mock_workload_manager,
        mock_ui_bus,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test running with a simple text prompt."""
        # Arrange
        input_context = InputContext(user_input="Hello, world!")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus

        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_event = events_mocker(content="Response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        shallow_supervisor.session_manager.get_or_create_session.assert_called_once()
        shallow_supervisor.workload_manager.create_workload.assert_called_once_with(
            "default",
        )
        shallow_supervisor.ui_bus.dispatch_ui_update.assert_called()
        shallow_supervisor.session_manager.post_process.assert_called_once_with(
            user_input=input_context.user_input,
            original_session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_run_async_with_file_mentions(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test running with a prompt that has file mentions."""
        # Arrange
        mentions = [
            (Path("file1.txt"), "Content of file 1"),
            (Path("file2.py"), "print('Hello from file 2')"),
        ]
        input_context = InputContext(
            user_input="Analyze these files",
            enrich_input={str(path): content for path, content in mentions},
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        mock_event = events_mocker(content="Response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - Verify the workload.run_async was called with content
        # containing both prompt and mentions
        mock_workload.run_async.assert_called_once()
        call_args = mock_workload.run_async.call_args

        # Check that content (second argument) contains the expected structure
        content = call_args[0][1]
        assert content is not None
        assert content.role == "user"
        assert len(content.parts) == 3  # 1 prompt + 2 file mentions

        # Verify mentions are formatted correctly
        assert "file1.txt" in content.parts[1].text
        assert "Content of file 1" in content.parts[1].text
        assert "file2.py" in content.parts[2].text
        assert "print('Hello from file 2')" in content.parts[2].text

    @pytest.mark.asyncio
    async def test_run_async_with_none_payload(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test running with None payload."""
        input_context = InputContext()
        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        # Arrange
        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        mock_event = events_mocker(content="Response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        mock_workload.run_async.assert_called_once()
        call_args = mock_workload.run_async.call_args

        # content (second argument) should be None when no payload is provided
        content = call_args[0][1]
        assert content is None

    @pytest.mark.asyncio
    async def test_run_async_with_empty_prompt(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test running with empty prompt text."""
        # Arrange
        input_context = InputContext(user_input="")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        mock_event = events_mocker(content="Response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        mock_workload.run_async.assert_called_once()
        call_args = mock_workload.run_async.call_args

        # content (second argument) should be None when prompt is empty and no mentions
        content = call_args[0][1]
        assert content is None

    @pytest.mark.asyncio
    async def test_run_async_with_mentions_only(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        events_mocker,
    ) -> None:
        """Test running with only file mentions but no prompt text."""
        # Arrange
        mentions = [(Path("config.json"), '{"setting": "value"}')]
        input_context = InputContext(
            user_input="",
            enrich_input={str(path): content for path, content in mentions},
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager

        shallow_supervisor.session_manager.get_or_create_session.return_value = (
            mock_session
        )

        mock_event = events_mocker(content="Response")
        mock_workload.run_async.return_value = self._async_iter([mock_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        mock_workload.run_async.assert_called_once()
        call_args = mock_workload.run_async.call_args

        # content (second argument) should contain only the file mention
        content = call_args[0][1]
        assert content is not None
        assert content.role == "user"
        assert len(content.parts) == 1  # Only 1 file mention
        assert "config.json" in content.parts[0].text
        assert '{"setting": "value"}' in content.parts[0].text

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item
