"""Test CompactCommand successful summarization scenarios.

This module tests the successful path where CompactCommand has history to summarize,
successfully gets LLM summary, and properly replaces session events.
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


class TestCompactCommandSuccessfulSummarization:
    """Test CompactCommand successful summarization scenarios."""

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

    async def _async_iter_responses(self, responses: list[Mock]):
        """Create an async iterator from a list of responses."""
        for response in responses:
            yield response

    @pytest.mark.asyncio
    async def test_successful_summarization_with_mixed_events(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test successful summarization with both user and assistant events."""
        # Arrange - Create events with mixed authors
        user_event = Mock(spec=Event)
        user_event.author = "user"
        user_event.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message 1")],
        )
        user_event.model_copy.return_value = user_event

        assistant_event = Mock(spec=Event)
        assistant_event.author = "assistant"
        assistant_event.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Assistant response 1")],
        )
        assistant_event.model_copy.return_value = assistant_event

        user_event2 = Mock(spec=Event)
        user_event2.author = "user"
        user_event2.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message 2")],
        )
        user_event2.model_copy.return_value = user_event2

        events = [user_event, assistant_event, user_event2]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock successful LLM response
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = "Summary of the conversation"

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert UI updates
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list
        assert len(ui_calls) >= 3

        # Should show "Compacting conversation history..." message first
        start_message = ui_calls[0][0][0]
        assert isinstance(start_message, ui_events.Info)
        assert "compacting conversation history" in start_message.lower()

        # Should show summary markdown
        summary_display = ui_calls[1][0][0]
        assert isinstance(summary_display, ui_events.Markdown)
        assert "summary of the conversation" in summary_display.lower()

        # Should show success message
        success_message = ui_calls[2][0][0]
        assert isinstance(success_message, ui_events.Info)
        assert "session compacted successfully" in success_message.lower()

        # Verify session replacement with user events + summary
        mock_dependencies[
            "session_manager"
        ].replace_current_session_events.assert_called_once()
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # Should have: user events + summary event
        assert len(replaced_events) == 2  # 1 user event + 1 summary
        assert replaced_events[0].author == "user"
        assert replaced_events[1].author == "assistant"
        assert (
            "summary of the conversation"
            in replaced_events[1].content.parts[0].text.lower()
        )

    @pytest.mark.asyncio
    async def test_preserves_assistant_author_name(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test that the original assistant author name is preserved in summary."""
        # Arrange - Create events with custom assistant name
        user_event = Mock(spec=Event)
        user_event.author = "user"
        user_event.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message")],
        )
        user_event.model_copy.return_value = user_event

        custom_assistant_event = Mock(spec=Event)
        custom_assistant_event.author = "custom_assistant"
        custom_assistant_event.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Custom assistant response")],
        )
        custom_assistant_event.model_copy.return_value = custom_assistant_event

        events = [user_event, custom_assistant_event]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock successful LLM response
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = "Summary text"

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # Should preserve the custom assistant name in summary event
        assert len(replaced_events) == 2  # 1 user event + 1 summary
        assert replaced_events[1].author == "custom_assistant"

    @pytest.mark.asyncio
    async def test_uses_default_assistant_when_no_assistant_events(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test that default 'assistant' name is used when no assistant events exist."""
        # Arrange - Only user events
        user_event1 = Mock(spec=Event)
        user_event1.author = "user"
        user_event1.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message 1")],
        )
        user_event1.model_copy.return_value = user_event1

        user_event2 = Mock(spec=Event)
        user_event2.author = "user"
        user_event2.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message 2")],
        )
        user_event2.model_copy.return_value = user_event2

        events = [user_event1, user_event2]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock successful LLM response
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = "Summary text"

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # Should use default "assistant" name for summary event
        assert len(replaced_events) == 3  # 2 user events + 1 summary
        assert replaced_events[2].author == "assistant"

    @pytest.mark.asyncio
    async def test_llm_request_includes_compact_message(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test that LLM request includes the COMPACT message."""
        # Arrange
        user_event = Mock(spec=Event)
        user_event.author = "user"
        user_event.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message")],
        )
        user_event.model_copy.return_value = user_event

        events = [user_event]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock successful LLM response
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = "Summary text"

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert LLM was called with correct parameters
        mock_model.generate_content_async.assert_called_once()
        llm_request = mock_model.generate_content_async.call_args[1]["llm_request"]

        # Should have original content + COMPACT message
        assert len(llm_request.contents) == 2
        assert llm_request.contents[0].parts[0].text == "User message"

        # COMPACT message should be appended
        compact_message = llm_request.contents[1]
        assert compact_message.role == "user"
        assert (
            "analyze the conversation history" in compact_message.parts[0].text.lower()
        )

    @pytest.mark.asyncio
    async def test_system_instruction_included_in_llm_request(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test that system instruction is included in LLM request."""
        # Arrange
        user_event = Mock(spec=Event)
        user_event.author = "user"
        user_event.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message")],
        )
        user_event.model_copy.return_value = user_event

        events = [user_event]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=session,
        )

        # Mock successful LLM response
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = "Summary text"

        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        llm_request = mock_model.generate_content_async.call_args[1]["llm_request"]
        assert llm_request.model == "test-model"
        assert llm_request.config.system_instruction == "system message"
