"""Test CompactCommand LLM failure scenarios.

This module tests how CompactCommand handles various LLM failure scenarios,
including no response, empty response, and partial responses.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.args import Args
from streetrace.commands.definitions.compact_command import CompactCommand
from streetrace.session_service import SessionManager
from streetrace.system_context import SystemContext
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus


class TestCompactCommandLlmFailures:
    """Test CompactCommand LLM failure scenarios."""

    @pytest.fixture
    def mock_dependencies(self, mock_model_factory) -> dict[str, Mock]:
        """Create mock dependencies for CompactCommand."""
        mock_args = Mock(spec=Args)
        mock_args.model = "test-model"

        mock_system_context = Mock(spec=SystemContext)
        mock_system_context.get_system_message.return_value = "system message"

        return {
            "ui_bus": Mock(spec=UiBus),
            "args": mock_args,
            "session_manager": Mock(spec=SessionManager),
            "system_context": mock_system_context,
            "model_factory": mock_model_factory,
        }

    @pytest.fixture
    def compact_command(self, mock_dependencies: dict[str, Mock]) -> CompactCommand:
        """Create a CompactCommand instance with mocked dependencies."""
        return CompactCommand(**mock_dependencies)

    @pytest.fixture
    def sample_events(self) -> list[Mock]:
        """Create sample events for testing."""
        user_event = Mock(spec=Event)
        user_event.author = "user"
        user_event.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message")],
        )
        user_event.model_copy.return_value = user_event

        assistant_event = Mock(spec=Event)
        assistant_event.author = "assistant"
        assistant_event.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Assistant response")],
        )
        assistant_event.model_copy.return_value = assistant_event

        return [user_event, assistant_event]

    async def _async_iter_responses(self, responses: list[Mock]):
        """Create an async iterator from a list of responses."""
        for response in responses:
            yield response

    @pytest.mark.asyncio
    async def test_llm_returns_empty_summary(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when LLM returns empty summary."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock LLM response with no text
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = ""  # Empty text

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list

        # Should show warning about failed compaction
        warning_found = any(
            isinstance(call[0][0], ui_events.Warn)
            and "could not be compacted" in call[0][0].lower()
            for call in ui_calls
        )
        assert warning_found

        # Should NOT replace session events
        assert not mock_dependencies[
            "session_manager"
        ].replace_current_session_events.called

    @pytest.mark.asyncio
    async def test_llm_returns_no_content(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when LLM returns response with no content."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock LLM response with no content
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = None

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list

        # Should show warning about failed compaction
        warning_found = any(
            isinstance(call[0][0], ui_events.Warn)
            and "could not be compacted" in call[0][0].lower()
            for call in ui_calls
        )
        assert warning_found

        # Should NOT replace session events
        assert not mock_dependencies[
            "session_manager"
        ].replace_current_session_events.called

    @pytest.mark.asyncio
    async def test_llm_returns_no_parts(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when LLM returns content with no parts."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock LLM response with no parts
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = []  # No parts

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list

        # Should show warning about failed compaction
        warning_found = any(
            isinstance(call[0][0], ui_events.Warn)
            and "could not be compacted" in call[0][0].lower()
            for call in ui_calls
        )
        assert warning_found

        # Should NOT replace session events
        assert not mock_dependencies[
            "session_manager"
        ].replace_current_session_events.called

    @pytest.mark.asyncio
    async def test_llm_returns_only_partial_responses(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when LLM returns only partial responses."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock LLM response with only partial responses
        partial_response1 = Mock()
        partial_response1.partial = True
        partial_response1.content = Mock()
        partial_response1.content.role = "assistant"
        partial_response1.content.parts = [Mock()]
        partial_response1.content.parts[0].text = "Partial text 1"

        partial_response2 = Mock()
        partial_response2.partial = True
        partial_response2.content = Mock()
        partial_response2.content.role = "assistant"
        partial_response2.content.parts = [Mock()]
        partial_response2.content.parts[0].text = "Partial text 2"

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [partial_response1, partial_response2],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list

        # Should show warning about failed compaction
        warning_found = any(
            isinstance(call[0][0], ui_events.Warn)
            and "could not be compacted" in call[0][0].lower()
            for call in ui_calls
        )
        assert warning_found

        # Should NOT replace session events
        assert not mock_dependencies[
            "session_manager"
        ].replace_current_session_events.called

    @pytest.mark.asyncio
    async def test_llm_returns_mixed_partial_and_final_responses(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when LLM returns mix of partial and final responses."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock LLM response with partial and final
        partial_response = Mock()
        partial_response.partial = True
        partial_response.content = Mock()
        partial_response.content.role = "assistant"
        partial_response.content.parts = [Mock()]
        partial_response.content.parts[0].text = "Partial text"

        final_response = Mock()
        final_response.partial = False
        final_response.content = Mock()
        final_response.content.role = "assistant"
        final_response.content.parts = [Mock()]
        final_response.content.parts[0].text = "Final summary text"

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [partial_response, final_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert successful compaction
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list

        # Should show summary display
        summary_found = any(
            isinstance(call[0][0], ui_events.Markdown)
            and "final summary text" in call[0][0].lower()
            for call in ui_calls
        )
        assert summary_found

        # Should show success message
        success_found = any(
            isinstance(call[0][0], ui_events.Info)
            and "session compacted successfully" in call[0][0].lower()
            for call in ui_calls
        )
        assert success_found

        # Should replace session events
        mock_dependencies[
            "session_manager"
        ].replace_current_session_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_multiple_final_responses_uses_all_text(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test that multiple final responses are concatenated properly."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock LLM response with multiple final responses
        final_response1 = Mock()
        final_response1.partial = False
        final_response1.content = Mock()
        final_response1.content.role = "assistant"
        final_response1.content.parts = [Mock()]
        final_response1.content.parts[0].text = "First part of summary. "

        final_response2 = Mock()
        final_response2.partial = False
        final_response2.content = Mock()
        final_response2.content.role = "assistant"
        final_response2.content.parts = [Mock()]
        final_response2.content.parts[0].text = "Second part of summary."

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [final_response1, final_response2],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # Summary should contain concatenated text
        summary_event = replaced_events[-1]  # Last event should be summary
        summary_text = summary_event.content.parts[0].text
        assert "first part of summary" in summary_text.lower()
        assert "second part of summary" in summary_text.lower()
        assert summary_text == "First part of summary. Second part of summary."
