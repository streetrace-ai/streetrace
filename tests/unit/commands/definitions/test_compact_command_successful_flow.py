"""Test CompactCommand successful compaction flow.

This module tests the complete successful execution path where the command has history
to compact, successfully gets LLM summary, and replaces session events.
"""

from unittest.mock import Mock

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


class TestCompactCommandSuccessfulFlow:
    """Test CompactCommand successful compaction scenarios."""

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
    def sample_events(self) -> list[Mock]:
        """Create sample mock events for testing."""
        # Create mock events instead to avoid Pydantic restrictions
        user_event = Mock(spec=Event)
        user_event.author = "user"
        user_event.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message 1")],
        )
        user_event.is_final_response.return_value = True
        user_event.model_copy.return_value = user_event

        assistant_event = Mock(spec=Event)
        assistant_event.author = "assistant"
        assistant_event.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Assistant response 1")],
        )
        assistant_event.is_final_response.return_value = True
        assistant_event.model_copy.return_value = assistant_event

        # Non-final event that should be in tail_events
        partial_event = Mock(spec=Event)
        partial_event.author = "assistant"
        partial_event.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Partial response")],
        )
        partial_event.is_final_response.return_value = False
        partial_event.model_copy.return_value = partial_event

        return [user_event, assistant_event, partial_event]

    @pytest.fixture
    def compact_command(self, mock_dependencies: dict[str, Mock]) -> CompactCommand:
        """Create a CompactCommand instance with mocked dependencies."""
        return CompactCommand(**mock_dependencies)

    async def _async_iter_responses(self, responses: list[Mock]):
        """Create an async iterator from a list of responses."""
        for response in responses:
            yield response

    @pytest.mark.asyncio
    async def test_successful_compaction_with_tail_events(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        sample_events: list[Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test successful compaction flow when there are tail events to summarize."""
        # Arrange
        session = Mock(spec=Session)
        session.events = sample_events
        mock_dependencies["session_manager"].get_current_session.return_value = session

        # Mock the LLM response
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = "This is a summary of the conversation."

        mock_model = Mock()
        # Use the helper method to create async iterator
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [mock_response],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert UI updates
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list
        assert len(ui_calls) >= 3  # Start, summary display, success messages

        # Check for "Compacting conversation history..." message
        start_message = ui_calls[0][0][0]
        assert isinstance(start_message, ui_events.Info)
        assert "compacting conversation history" in start_message.lower()

        # Check for summary markdown display
        summary_message = ui_calls[1][0][0]
        assert isinstance(summary_message, ui_events.Markdown)
        assert "summary of the conversation" in summary_message

        # Check for success message
        success_message = ui_calls[2][0][0]
        assert isinstance(success_message, ui_events.Info)
        assert "session compacted successfully" in success_message.lower()

        # Verify session replacement was called
        mock_dependencies[
            "session_manager"
        ].replace_current_session_events.assert_called_once()
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # Should have the final events plus the summary event
        assert len(replaced_events) == 3  # 2 final events + 1 summary event

        # Verify LLM was called with correct parameters
        mock_model.generate_content_async.assert_called_once()
        llm_call_args = mock_model.generate_content_async.call_args[1]["llm_request"]
        assert llm_call_args.model == "test-model"
        assert len(llm_call_args.contents) == 4  # 3 original + 1 COMPACT message

    @pytest.mark.asyncio
    async def test_successful_compaction_empty_contents_fallback(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when events exist but have no content to summarize."""
        # Arrange
        event1 = Mock(spec=Event)
        event1.author = "user"
        event1.content = None
        event1.is_final_response.return_value = False  # Make them tail events
        event1.model_copy.return_value = event1

        event2 = Mock(spec=Event)
        event2.author = "assistant"
        event2.content = None
        event2.is_final_response.return_value = False  # Make them tail events
        event2.model_copy.return_value = event2

        events_without_content = [event1, event2]

        session = Mock(spec=Session)
        session.events = events_without_content
        mock_dependencies["session_manager"].get_current_session.return_value = session

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        ui_calls = mock_dependencies["ui_bus"].dispatch_ui_update.call_args_list
        assert len(ui_calls) >= 2

        # Should show "Nothing to compact" message
        nothing_to_compact_found = any(
            isinstance(call[0][0], ui_events.Info)
            and "nothing to compact" in call[0][0].lower()
            for call in ui_calls
        )
        assert nothing_to_compact_found

        # Verify no session replacement occurred
        assert not mock_dependencies[
            "session_manager"
        ].replace_current_session_events.called
