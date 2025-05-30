"""Test CompactCommand history cleanup scenarios.

This module tests scenarios where CompactCommand cleans up history without summarization,
such as when there are no tail events requiring LLM processing.
"""

from unittest.mock import Mock, patch

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


class TestCompactCommandHistoryCleanup:
    """Test CompactCommand history cleanup scenarios."""

    @pytest.fixture
    def mock_dependencies(self) -> dict:
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
    def compact_command(self, mock_dependencies: dict) -> CompactCommand:
        """Create a CompactCommand instance with mocked dependencies."""
        return CompactCommand(**mock_dependencies)

    @pytest.mark.asyncio
    async def test_cleanup_only_final_events_no_tail(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict,
    ) -> None:
        """Test cleanup when all events are final (no tail events to summarize)."""
        # Arrange - Create mock events that are all final
        event1 = Mock(spec=Event)
        event1.author = "user"
        event1.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message 1")],
        )
        event1.is_final_response.return_value = True
        event1.model_copy.return_value = event1

        event2 = Mock(spec=Event)
        event2.author = "assistant"
        event2.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Assistant response 1")],
        )
        event2.is_final_response.return_value = True
        event2.model_copy.return_value = event2

        event3 = Mock(spec=Event)
        event3.author = "user"
        event3.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message 2")],
        )
        event3.is_final_response.return_value = True
        event3.model_copy.return_value = event3

        final_events = [event1, event2, event3]

        session = Mock(spec=Session)
        session.events = final_events
        mock_dependencies["session_manager"].get_current_session.return_value = session

        with patch("litellm.modify_params", True):
            # Act
            await compact_command.execute_async()

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list
        assert len(ui_calls) >= 2

        # Should show "Compacting conversation history..." message first
        start_message = ui_calls[0][0][0]
        assert isinstance(start_message, ui_events.Info)
        assert "compacting conversation history" in start_message.lower()

        # Should show warning about cleanup
        cleanup_warning = ui_calls[1][0][0]
        assert isinstance(cleanup_warning, ui_events.Warn)
        assert "history was cleaned up" in cleanup_warning.lower()
        assert "non-final responses removed" in cleanup_warning.lower()

        # Should show success message
        success_message = ui_calls[2][0][0]
        assert isinstance(success_message, ui_events.Info)
        assert "session compacted successfully" in success_message.lower()

        # Verify session replacement with final events only
        mock_dependencies[
            "session_manager"
        ].replace_current_session_events.assert_called_once()
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]
        assert len(replaced_events) == 3  # All original final events

        # Verify no LLM call was made
        assert not mock_dependencies["model_factory"].get_current_model.called

    @pytest.mark.asyncio
    async def test_cleanup_mixed_events_keeps_final_only(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict,
    ) -> None:
        """Test cleanup when there are mixed final and non-final events but no tail events."""
        # Arrange - Mix of final and non-final events, but no tail events
        event1 = Mock(spec=Event)
        event1.author = "user"
        event1.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message 1")],
        )
        event1.is_final_response.return_value = True  # User messages are final
        event1.model_copy.return_value = event1

        event2 = Mock(spec=Event)  # Non-final event
        event2.author = "assistant"
        event2.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Partial response")],
        )
        event2.is_final_response.return_value = False  # Non-final assistant
        event2.model_copy.return_value = event2

        event3 = Mock(spec=Event)  # Final event - this should clear tail_events
        event3.author = "user"
        event3.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message 2")],
        )
        event3.is_final_response.return_value = True  # Final user message
        event3.model_copy.return_value = event3

        mixed_events = [event1, event2, event3]

        session = Mock(spec=Session)
        session.events = mixed_events
        mock_dependencies["session_manager"].get_current_session.return_value = session

        with patch("litellm.modify_params", True):
            # Act
            await compact_command.execute_async()

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list

        # Should show cleanup warning
        cleanup_warning_found = any(
            isinstance(call[0][0], ui_events.Warn)
            and "history was cleaned up" in call[0][0].lower()
            for call in ui_calls
        )
        assert cleanup_warning_found

        # Verify session replacement occurred with only final events
        mock_dependencies[
            "session_manager"
        ].replace_current_session_events.assert_called_once()
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # Should only have the final events (user messages)
        assert len(replaced_events) == 2

        # Verify no LLM call was made (no tail events)
        assert not mock_dependencies["model_factory"].get_current_model.called

    @pytest.mark.asyncio
    async def test_cleanup_preserves_event_order(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict,
    ) -> None:
        """Test that cleanup preserves the order of final events."""
        # Arrange - Events with specific content to test ordering
        event1 = Mock(spec=Event)
        event1.author = "user"
        event1.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="First user message")],
        )
        event1.is_final_response.return_value = True  # First user - final
        event1.model_copy.return_value = event1

        event2 = Mock(spec=Event)  # Non-final - should be removed
        event2.author = "assistant"
        event2.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Partial assistant response")],
        )
        event2.is_final_response.return_value = False  # Partial assistant - non-final
        event2.model_copy.return_value = event2

        event3 = Mock(spec=Event)
        event3.author = "user"
        event3.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="Second user message")],
        )
        event3.is_final_response.return_value = True  # Second user - final
        event3.model_copy.return_value = event3

        event4 = Mock(spec=Event)  # Final assistant response
        event4.author = "assistant"
        event4.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Final assistant response")],
        )
        event4.is_final_response.return_value = True  # Final assistant - final
        event4.model_copy.return_value = event4

        ordered_events = [event1, event2, event3, event4]

        session = Mock(spec=Session)
        session.events = ordered_events
        mock_dependencies["session_manager"].get_current_session.return_value = session

        with patch("litellm.modify_params", True):
            # Act
            await compact_command.execute_async()

        # Assert
        mock_dependencies[
            "session_manager"
        ].replace_current_session_events.assert_called_once()
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # Should have 3 final events in correct order
        assert len(replaced_events) == 3

        # Verify order by checking content
        assert "first user message" in replaced_events[0].content.parts[0].text.lower()
        assert "second user message" in replaced_events[1].content.parts[0].text.lower()
        assert (
            "final assistant response"
            in replaced_events[2].content.parts[0].text.lower()
        )
