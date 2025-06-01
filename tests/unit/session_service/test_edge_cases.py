"""Tests for edge cases and uncovered lines in session_service.py."""

from unittest.mock import ANY, Mock, patch

import pytest
from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.session_service import JSONSessionSerializer


class TestJSONSessionSerializerEdgeCases:
    """Tests for edge cases in JSONSessionSerializer."""

    def test_list_saved_empty_session(self, session_storage_dir):
        """Test list_saved when a session is None."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Create a test directory structure
        app_dir = session_storage_dir / "test-app" / "test-user"
        app_dir.mkdir(parents=True, exist_ok=True)

        # Create a file that will return None when parsed
        test_file = app_dir / "empty-session.json"
        test_file.write_text("{}")  # Valid JSON but will result in None session

        # Mock Session.model_validate_json to return None
        with (
            patch("google.adk.sessions.Session.model_validate_json", return_value=None),
            patch("streetrace.session_service.logger") as mock_logger,
        ):
            # List sessions
            sessions = list(
                serializer.list_saved(
                    app_name="test-app",
                    user_id="test-user",
                ),
            )

            # Check that the warning was logged and no sessions were returned
            assert len(sessions) == 0
            mock_logger.warning.assert_called_once_with(
                "Failed to read/parse session file %s for listing, skipping.",
                ANY,
            )

    def test_list_saved_with_non_file(self, session_storage_dir):
        """Test list_saved with a non-file in the directory."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Create a test directory structure
        app_dir = session_storage_dir / "test-app" / "test-user"
        app_dir.mkdir(parents=True, exist_ok=True)

        # Create a directory with a .json extension to test the is_file check
        (app_dir / "not-a-file.json").mkdir()

        # List sessions
        sessions = list(
            serializer.list_saved(
                app_name="test-app",
                user_id="test-user",
            ),
        )

        # Verify no sessions were returned
        assert len(sessions) == 0

    def test_list_saved_empty_dir(self, session_storage_dir):
        """Test list_saved with a directory that doesn't exist."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # List sessions from a non-existent directory
        sessions = list(
            serializer.list_saved(
                app_name="nonexistent",
                user_id="nonexistent",
            ),
        )

        # Verify no sessions were returned
        assert len(sessions) == 0


class TestSessionManagerEdgeCases:
    """Tests for edge cases in SessionManager."""

    def test_get_or_create_session_assertion_error(
        self,
        session_manager,
        json_session_service,
        system_context,
    ):
        """Test get_or_create_session when session is None after creation."""
        # Setup mocks to simulate creating a session but then getting None when
        # retrieving it
        json_session_service.get_session = Mock(side_effect=[None, None])
        json_session_service.create_session = Mock(return_value=Mock(spec=Session))
        json_session_service.append_event = Mock()

        # Mock system context
        system_context.get_project_context.return_value = ["Test project context"]

        # Test the assertion error case
        with pytest.raises(AssertionError, match="session is None"):
            session_manager.get_or_create_session()

        # Verify the methods were called correctly
        json_session_service.create_session.assert_called_once()
        json_session_service.append_event.assert_called_once()
        assert json_session_service.get_session.call_count == 2

    def test_squash_turn_events_tool_detection(
        self,
        session_manager,
        sample_session,
    ):
        """Test _squash_turn_events tool detection in the last message."""
        # Setup session with user event and an assistant event with tool calls
        session_with_events = sample_session.model_copy(deep=True)
        user_event = Event(
            author="user",
            content=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text="User message")],
            ),
        )

        # Create an assistant event with function calls
        assistant_event = Event(
            author="assistant",
            content=genai_types.Content(
                role="assistant",
                parts=[
                    genai_types.Part(
                        function_call=genai_types.FunctionCall(name="test_function"),
                    ),
                ],
            ),
        )

        session_with_events.events = [user_event, assistant_event]

        # Test _squash_turn_events with a message containing tool calls
        with pytest.raises(
            ValueError,
            match="Cannot post-process, the last message has tool data",
        ):
            session_manager._squash_turn_events(session_with_events, 0)  # noqa: SLF001

        # Now test with function_response
        assistant_event_with_response = Event(
            author="assistant",
            content=genai_types.Content(
                role="assistant",
                parts=[
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name="test_function",
                        ),
                    ),
                ],
            ),
        )

        session_with_events.events = [user_event, assistant_event_with_response]

        # Test _squash_turn_events with a message containing tool responses
        with pytest.raises(
            ValueError,
            match="Cannot post-process, the last message has tool data",
        ):
            session_manager._squash_turn_events(session_with_events, 0)  # noqa: SLF001

    def test_squash_turn_events_tool_detection_complex(
        self,
        session_manager,
        sample_session,
    ):
        """Test _squash_turn_events with mixed content in the assistant event."""
        # Setup session with user event and an assistant event with mixed content
        session_with_events = sample_session.model_copy(deep=True)
        user_event = Event(
            author="user",
            content=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text="User message")],
            ),
        )

        # Create an assistant event with mixed content including text and tool calls
        assistant_event = Event(
            author="assistant",
            content=genai_types.Content(
                role="assistant",
                parts=[
                    # Text part
                    genai_types.Part.from_text(text="Assistant response"),
                    # Function call part
                    genai_types.Part(
                        function_call=genai_types.FunctionCall(name="test_function"),
                    ),
                ],
            ),
        )

        session_with_events.events = [user_event, assistant_event]

        # Test _squash_turn_events with a message containing both text and tool calls
        # This should still raise an exception because of the tool call
        with pytest.raises(
            ValueError,
            match="Cannot post-process, the last message has tool data",
        ):
            session_manager._squash_turn_events(session_with_events, 0)  # noqa: SLF001

    def test_squash_turn_events_no_tools(
        self,
        session_manager,
        json_session_service,
        sample_session,
    ):
        """Test _squash_turn_events with no tool calls/responses but multiple parts."""
        # Setup session with user event and a multi-part assistant event without tool
        # calls
        session_with_events = sample_session.model_copy(deep=True)
        user_event = Event(
            author="user",
            content=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text="User message")],
            ),
        )

        # Create an assistant event with multiple text parts but no tools
        assistant_event = Event(
            author="assistant",
            content=genai_types.Content(
                role="assistant",
                parts=[
                    genai_types.Part.from_text(text="Part 1 of response"),
                    genai_types.Part.from_text(text="Part 2 of response"),
                    genai_types.Part(text=None),  # Empty part without text
                ],
            ),
        )

        session_with_events.events = [user_event, assistant_event]

        # Mock replace_events
        json_session_service.replace_events = Mock()

        # Call _squash_turn_events - this should not raise an exception
        result = session_manager._squash_turn_events(session_with_events, 0)  # noqa: SLF001

        # Verify replace_events was called and the text was extracted correctly
        json_session_service.replace_events.assert_called_once_with(
            session=session_with_events,
            new_events=[assistant_event],
            start_at=0,
        )

        assert result == "Part 1 of responsePart 2 of response"
