"""Test CompactCommand error handling scenarios.

This module tests how CompactCommand handles various error conditions including
LLM failures, malformed responses, and other exception scenarios.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock

import pytest
from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.args import Args
from streetrace.commands.definitions.compact_command import CompactCommand
from streetrace.llm.model_factory import ModelFactory
from streetrace.session_service import SessionManager
from streetrace.system_context import SystemContext
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus


class TestCompactCommandErrorHandling:
    """Test CompactCommand error handling scenarios."""

    @pytest.fixture
    def mock_dependencies(self) -> dict[str, Mock]:
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
            "model_factory": Mock(spec=ModelFactory),
        }

    @pytest.fixture
    def sample_events_with_content(self) -> list[Mock]:
        """Create sample mock events with content for testing."""
        user_event = Mock(spec=Event)
        user_event.author = "user"
        user_event.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message")],
        )
        user_event.is_final_response.return_value = False
        user_event.model_copy.return_value = user_event

        assistant_event = Mock(spec=Event)
        assistant_event.author = "assistant"
        assistant_event.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Assistant response")],
        )
        assistant_event.is_final_response.return_value = False
        assistant_event.model_copy.return_value = assistant_event

        return [user_event, assistant_event]

    @pytest.fixture
    def compact_command(self, mock_dependencies: dict[str, Mock]) -> CompactCommand:
        """Create a CompactCommand instance with mocked dependencies."""
        return CompactCommand(**mock_dependencies)

    async def _async_iter_responses(self, responses: list[Mock]):
        """Create an async iterator from a list of responses."""
        for response in responses:
            yield response

    @pytest.mark.asyncio
    async def test_llm_returns_empty_summary(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events_with_content: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when LLM returns empty or None summary."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events_with_content
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock LLM response with empty summary
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = ""  # Empty summary

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async("")

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list

        # Should show warning about failed compaction
        warning_found = any(
            isinstance(call[0][0], ui_events.Warn)
            and "could not be compacted" in call[0][0].lower()
            for call in ui_calls
        )
        assert warning_found

        # Verify no session replacement occurred
        assert not mock_dependencies[
            "session_manager"
        ].replace_current_session_events.called

    @pytest.mark.asyncio
    async def test_llm_returns_none_content(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events_with_content: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when LLM response has no content."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events_with_content
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
            await compact_command.execute_async("")

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list

        # Should show warning about failed compaction
        warning_found = any(
            isinstance(call[0][0], ui_events.Warn)
            and "could not be compacted" in call[0][0].lower()
            for call in ui_calls
        )
        assert warning_found

        # Verify no session replacement occurred
        assert not mock_dependencies[
            "session_manager"
        ].replace_current_session_events.called

    @pytest.mark.asyncio
    async def test_llm_returns_no_parts(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events_with_content: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when LLM response content has no parts."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events_with_content
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock LLM response with content but no parts
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
            await compact_command.execute_async("")

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list

        # Should show warning about failed compaction
        warning_found = any(
            isinstance(call[0][0], ui_events.Warn)
            and "could not be compacted" in call[0][0].lower()
            for call in ui_calls
        )
        assert warning_found

        # Verify no session replacement occurred
        assert not mock_dependencies[
            "session_manager"
        ].replace_current_session_events.called

    @pytest.mark.asyncio
    async def test_llm_exception_propagates(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events_with_content: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """LLM exceptions are properly propagated (fail-fast for core components)."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events_with_content
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock LLM to raise an exception
        async def _async_exception() -> AsyncGenerator[Mock, None]:
            if False:  # Make this an async generator
                yield
            msg = "LLM connection failed"
            raise Exception(msg)  # noqa: TRY002

        mock_model = Mock()
        mock_model.generate_content_async.return_value = _async_exception()
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with (
            patch_litellm_modify_params(),
            # Act & Assert - Exception should propagate (fail-fast for core components)
            pytest.raises(Exception, match="LLM connection failed"),
        ):
            await compact_command.execute_async("")
