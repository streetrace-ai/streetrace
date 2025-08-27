"""Tests for edge cases and uncovered lines in session_service.py."""

from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest
from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.session.json_serializer import JSONSessionSerializer


class TestJSONSessionSerializerEdgeCases:
    """Tests for edge cases in JSONSessionSerializer."""

    async def test_list_saved_empty_session(self, session_storage_dir):
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
            patch("streetrace.session.json_serializer.logger") as mock_logger,
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

    async def test_list_saved_with_non_file(self, session_storage_dir):
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

    async def test_list_saved_empty_dir(self, session_storage_dir):
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

    async def test_get_or_create_session_assertion_error(
        self,
        session_manager,
        json_session_service,
    ):
        """Test get_or_create_session when session is None after creation."""
        # Setup mocks to simulate creating a session but then getting None when
        # retrieving it
        json_session_service.get_session = AsyncMock(side_effect=[None, None])
        json_session_service.create_session = AsyncMock(return_value=Mock(spec=Session))

        # Test the assertion error case
        with pytest.raises(AssertionError, match="session is None"):
            await session_manager.get_or_create_session()

        # Verify the methods were called correctly
        json_session_service.create_session.assert_called_once()
        assert json_session_service.get_session.call_count == 2

    async def test_squash_turn_events_no_tools(
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
        json_session_service.replace_events = AsyncMock()

        # Call _squash_turn_events - this should not raise an exception
        result = await session_manager._squash_turn_events(session_with_events)  # noqa: SLF001

        # Verify replace_events was called and the text was extracted correctly
        json_session_service.replace_events.assert_called_once_with(
            session=session_with_events,
            new_events=[user_event, assistant_event],
        )

        assert result == "Part 1 of responsePart 2 of response"
