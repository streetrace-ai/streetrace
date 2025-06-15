"""Test CompactCommand event preservation and replacement scenarios.

This module tests how CompactCommand properly preserves user events and handles
event replacement during the summarization process.
"""

from unittest.mock import Mock

import pytest
from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.args import Args
from streetrace.commands.definitions.compact_command import CompactCommand
from streetrace.session_service import SessionManager
from streetrace.system_context import SystemContext
from streetrace.ui.ui_bus import UiBus


class TestCompactCommandEventPreservation:
    """Test CompactCommand event preservation and replacement scenarios."""

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

    def _create_mock_response(self, text: str) -> Mock:
        """Create a mock LLM response with given text."""
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "assistant"
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = text
        return mock_response

    @pytest.mark.asyncio
    async def test_preserves_user_events_in_order(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test that all user events are preserved in their original order."""
        # Arrange - Multiple user events with assistant events in between
        user_event1 = Mock(spec=Event)
        user_event1.author = "user"
        user_event1.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="First user message")],
        )
        user_event1.model_copy.return_value = user_event1

        user_event2 = Mock(spec=Event)
        user_event2.author = "user"
        user_event2.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="Second user message")],
        )
        user_event2.model_copy.return_value = user_event2

        user_event3 = Mock(spec=Event)
        user_event3.author = "user"
        user_event3.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="Third user message")],
        )
        user_event3.model_copy.return_value = user_event3

        assistant_event1 = Mock(spec=Event)
        assistant_event1.author = "assistant"
        assistant_event1.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="First assistant response")],
        )
        assistant_event1.model_copy.return_value = assistant_event1

        assistant_event2 = Mock(spec=Event)
        assistant_event2.author = "assistant"
        assistant_event2.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Second assistant response")],
        )
        assistant_event2.model_copy.return_value = assistant_event2

        events = [
            user_event1,
            user_event2,
            assistant_event1,
            user_event3,
            assistant_event2,
        ]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session.return_value = session

        # Mock successful LLM response
        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [self._create_mock_response("Summary of conversation")],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # Should have 3 user events + 1 summary event
        assert len(replaced_events) == 3

        # User events should be preserved in order
        assert replaced_events[0].author == "user"
        assert "first user message" in replaced_events[0].content.parts[0].text.lower()

        assert replaced_events[1].author == "user"
        assert "second user message" in replaced_events[1].content.parts[0].text.lower()

        # Summary event should be last
        assert replaced_events[2].author == "assistant"
        assert (
            "summary of conversation"
            in replaced_events[2].content.parts[0].text.lower()
        )

    @pytest.mark.asyncio
    async def test_skips_events_without_content(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test that events without content are handled properly."""
        # Arrange - Mix of events with and without content
        user_event_with_content = Mock(spec=Event)
        user_event_with_content.author = "user"
        user_event_with_content.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message with content")],
        )
        user_event_with_content.model_copy.return_value = user_event_with_content

        user_event_no_content = Mock(spec=Event)
        user_event_no_content.author = "user"
        user_event_no_content.content = None  # No content
        user_event_no_content.model_copy.return_value = user_event_no_content

        assistant_event_with_content = Mock(spec=Event)
        assistant_event_with_content.author = "assistant"
        assistant_event_with_content.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Assistant response")],
        )
        assistant_event_with_content.model_copy.return_value = (
            assistant_event_with_content
        )

        events = [
            user_event_with_content,
            user_event_no_content,
            assistant_event_with_content,
        ]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session.return_value = session

        # Mock successful LLM response
        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [self._create_mock_response("Summary text")],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        # LLM should be called with only content from events that have content
        llm_request = mock_model.generate_content_async.call_args[1]["llm_request"]
        # Should have 2 contents: user + assistant (event without content skipped) + COMPACT
        assert len(llm_request.contents) == 3

        # Session replacement should only include user event with content + summary
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]
        assert len(replaced_events) == 2  # 1 user event + 1 summary
        assert replaced_events[0].author == "user"
        assert replaced_events[1].author == "assistant"

    @pytest.mark.asyncio
    async def test_handles_only_assistant_events(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test behavior when session contains only assistant events."""
        # Arrange - Only assistant events
        assistant_event1 = Mock(spec=Event)
        assistant_event1.author = "assistant"
        assistant_event1.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Assistant response 1")],
        )
        assistant_event1.model_copy.return_value = assistant_event1

        assistant_event2 = Mock(spec=Event)
        assistant_event2.author = "custom_bot"
        assistant_event2.content = genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Custom bot response")],
        )
        assistant_event2.model_copy.return_value = assistant_event2

        events = [assistant_event1, assistant_event2]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session.return_value = session

        # Mock successful LLM response
        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [self._create_mock_response("Summary of assistant messages")],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # Should only have summary event (no user events to preserve)
        assert len(replaced_events) == 1
        assert replaced_events[0].author == "assistant"  # First assistant author found
        assert (
            "summary of assistant messages"
            in replaced_events[0].content.parts[0].text.lower()
        )

    @pytest.mark.asyncio
    async def test_preserves_user_event_structure(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test that user events are properly copied using model_copy."""
        # Arrange
        user_event = Mock(spec=Event)
        user_event.author = "user"
        user_event.content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User message")],
        )

        # Mock model_copy to return a different object to verify it's called
        copied_event = Mock(spec=Event)
        copied_event.author = "user"
        copied_event.content = user_event.content
        user_event.model_copy.return_value = copied_event

        events = [user_event]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session.return_value = session

        # Mock successful LLM response
        mock_model = Mock()
        mock_model.generate_content_async.return_value = self._async_iter_responses(
            [self._create_mock_response("Summary text")],
        )
        mock_dependencies["model_factory"].get_current_model.return_value = mock_model

        with patch_litellm_modify_params():
            # Act
            await compact_command.execute_async()

        # Assert
        # Verify model_copy was called on user event
        user_event.model_copy.assert_called_once()

        replaced_events = mock_dependencies[
            "session_manager"
        ].replace_current_session_events.call_args[0][0]

        # First event should be the copied event, not the original
        assert replaced_events[0] is copied_event
        assert replaced_events[0] is not user_event

    @pytest.mark.asyncio
    async def test_creates_new_summary_event_with_correct_structure(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
        patch_litellm_modify_params,
    ) -> None:
        """Test that summary event is created with correct structure."""
        # Arrange
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
            parts=[genai_types.Part.from_text(text="Assistant response")],
        )
        custom_assistant_event.model_copy.return_value = custom_assistant_event

        events = [user_event, custom_assistant_event]

        session = Mock(spec=Session)
        session.events = events
        mock_dependencies["session_manager"].get_current_session.return_value = session

        # Mock LLM response with specific role
        mock_response = Mock()
        mock_response.partial = False
        mock_response.content = Mock()
        mock_response.content.role = "model"  # Different role from assistant
        mock_response.content.parts = [Mock()]
        mock_response.content.parts[0].text = "Summary content"

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

        summary_event = replaced_events[-1]  # Last event should be summary

        # Should use original assistant author name
        assert summary_event.author == "custom_assistant"

        # Should use LLM response role in content
        assert summary_event.content.role == "model"

        # Should have correct text content
        assert len(summary_event.content.parts) == 1
        assert summary_event.content.parts[0].text == "Summary content"
