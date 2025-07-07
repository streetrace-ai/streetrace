"""Tests for the SessionManager class in session_service.py."""

from unittest.mock import AsyncMock, patch

import pytest
from google.adk.events import Event
from google.adk.sessions import Session
from google.adk.sessions.base_session_service import ListSessionsResponse
from google.genai import types as genai_types


class TestSessionManager:
    """Tests for the SessionManager class."""

    async def test_init(self, session_manager):
        """Test initialization of SessionManager."""
        assert session_manager.current_session_id == "test-session-id"
        assert session_manager.app_name == "test-app"
        assert session_manager.user_id == "test-user"

    async def test_reset_session(self, session_manager):
        """Test reset_session method."""
        # Initial session ID
        initial_id = session_manager.current_session_id

        # Reset with new ID
        with patch(
            "streetrace.session_service._session_id",
            return_value="new-session-id",
        ):
            session_manager.reset_session()
            assert session_manager.current_session_id == "new-session-id"

        # Reset with explicit ID
        session_manager.reset_session("explicit-id")
        assert session_manager.current_session_id == "explicit-id"
        assert initial_id != session_manager.current_session_id

    async def test_get_current_session_existing(
        self,
        session_manager,
        json_session_service,
        sample_session,
    ):
        """Test get_current_session when session exists."""
        # Setup the session service to return our sample session
        json_session_service.get_session = AsyncMock(return_value=sample_session)

        # Get the current session
        result = await session_manager.get_current_session()

        # Verify the correct methods were called
        json_session_service.get_session.assert_called_once_with(
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            session_id=session_manager.current_session_id,
        )

        # Verify the result
        assert result == sample_session

    async def test_get_current_session_not_existing(
        self,
        session_manager,
        json_session_service,
    ):
        """Test get_current_session when session doesn't exist."""
        # Setup the session service to return None (session doesn't exist)
        json_session_service.get_session = AsyncMock(return_value=None)

        # Get the current session
        result = await session_manager.get_current_session()

        # Verify the correct methods were called
        json_session_service.get_session.assert_called_once_with(
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            session_id=session_manager.current_session_id,
        )

        # Verify the result
        assert result is None

    async def test_get_or_create_session_existing(
        self,
        session_manager,
        json_session_service,
        sample_session,
    ):
        """Test get_or_create_session when session exists."""
        # Setup the session service to return our sample session
        json_session_service.get_session = AsyncMock(return_value=sample_session)

        # Mock create_session to verify it's not called
        json_session_service.create_session = AsyncMock()

        # Get or create the session
        result = await session_manager.get_or_create_session()

        # Verify the correct methods were called
        json_session_service.get_session.assert_called_once_with(
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            session_id=session_manager.current_session_id,
        )

        # Verify create_session was not called
        json_session_service.create_session.assert_not_called()

        # Verify the result
        assert result == sample_session
        assert session_manager.current_session == sample_session

    async def test_get_or_create_session_new(
        self,
        session_manager,
        json_session_service,
        system_context,
        context_event,
    ):
        """Test get_or_create_session when session doesn't exist."""
        # Setup the session service
        new_session = Session(
            id=session_manager.current_session_id,
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            events=[],
            state={},
        )

        session_with_context = Session(
            id=session_manager.current_session_id,
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            events=[context_event],
            state={},
        )

        # Mock sequence of returns for get_session
        json_session_service.get_session = AsyncMock(
            side_effect=[None, session_with_context],
        )
        json_session_service.create_session = AsyncMock(return_value=new_session)
        json_session_service.append_event = AsyncMock()

        # Mock system context
        system_context.get_project_context.return_value = ["Test project context"]

        # Get or create the session
        result = await session_manager.get_or_create_session()

        # Verify the methods were called correctly
        json_session_service.create_session.assert_called_once_with(
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            session_id=session_manager.current_session_id,
            state={},
        )

        # Verify that append_event was called with an event containing the project
        # context
        json_session_service.append_event.assert_called_once()

        # Verify the result
        assert result == session_with_context
        assert session_manager.current_session == session_with_context

    async def test_replace_current_session_events(
        self,
        session_manager,
        json_session_service,
        sample_session,
        user_event,
    ):
        """Test replace_current_session_events method."""
        # Setup the session service
        json_session_service.get_session = AsyncMock(return_value=sample_session)
        json_session_service.replace_events = AsyncMock()

        # Replace events
        new_events = [user_event]
        await session_manager.replace_current_session_events(new_events)

        # Verify methods were called correctly
        json_session_service.get_session.assert_called_once_with(
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            session_id=session_manager.current_session_id,
        )

        json_session_service.replace_events.assert_called_once_with(
            session=sample_session,
            new_events=new_events,
        )

    async def test_replace_current_session_events_no_session(
        self,
        session_manager,
        json_session_service,
    ):
        """Test replace_current_session_events when session doesn't exist."""
        # Setup the session service to return None (session doesn't exist)
        json_session_service.get_session = AsyncMock(return_value=None)

        # Try to replace events
        with pytest.raises(ValueError, match="Current session is missing"):
            await session_manager.replace_current_session_events([])

    async def test_display_sessions(
        self,
        session_manager,
        json_session_service,
        ui_bus,
    ):
        """Test display_sessions method."""
        # Setup mock for list_sessions
        mock_response = ListSessionsResponse(sessions=[])
        json_session_service.list_sessions = AsyncMock(return_value=mock_response)

        # Call display_sessions
        await session_manager.display_sessions()

        # Verify methods were called correctly
        json_session_service.list_sessions.assert_called_once_with(
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
        )

        # Verify UI update was dispatched
        ui_bus.dispatch_ui_update.assert_called_once()
        args, _ = ui_bus.dispatch_ui_update.call_args
        display_list = args[0]
        assert display_list.app_name == session_manager.app_name
        assert display_list.user_id == session_manager.user_id
        assert display_list.list_sessions == mock_response

    async def test_squash_turn_events(
        self,
        session_manager,
        json_session_service,
        sample_session,
        assistant_event,
    ):
        """Test _squash_turn_events method."""
        # Setup session with initial events
        session_with_events = sample_session.model_copy(deep=True)
        context_event = Event(
            author="user",
            content=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text="Context")],
            ),
        )
        user_event = Event(
            author="user",
            content=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text="User message")],
            ),
        )
        # Assistant event is from the fixture

        session_with_events.events = [context_event, user_event, assistant_event]

        # Mock replace_events
        json_session_service.replace_events = AsyncMock()

        # Call _squash_turn_events
        result = await session_manager._squash_turn_events(session_with_events)  # noqa: SLF001

        # Verify replace_events was called correctly
        json_session_service.replace_events.assert_called_once_with(
            session=session_with_events,
            new_events=[context_event, user_event, assistant_event],
        )

        # Verify the result is the assistant's message text
        assert result == "Assistant response"

    async def test_squash_turn_events_validation_errors(
        self,
        session_manager,
        sample_session,
        user_event,
        tool_event,
    ):
        """Test _squash_turn_events validation errors."""
        # Test with not enough events
        session = sample_session.model_copy(deep=True)
        session.events = [user_event]

        assert await session_manager._squash_turn_events(session) == ""  # noqa: SLF001

        # Test with last event being user's message
        session.events = [user_event, user_event]

        assert await session_manager._squash_turn_events(session) == ""  # noqa: SLF001

        # Test with last event having tool calls
        session.events = [user_event, tool_event]

        assert await session_manager._squash_turn_events(session) == ""  # noqa: SLF001

        # Test with last event having no text
        empty_event = Event(
            author="assistant",
            content=genai_types.Content(
                role="assistant",
                parts=[genai_types.Part()],
            ),
        )
        session.events = [user_event, empty_event]

        assert await session_manager._squash_turn_events(session) == ""  # noqa: SLF001

    async def test_add_project_context(
        self,
        session_manager,
        system_context,
        sample_session,
        user_event,
    ):
        """Test _add_project_context method."""
        # Setup
        processed_prompt = "Test prompt"
        assistant_response = "Assistant response"

        # Set up a session with a user event
        session = sample_session.model_copy(deep=True)
        session.events = [user_event]

        # Call _add_project_context
        session_manager._add_project_context(  # noqa: SLF001
            processed_prompt,
            assistant_response,
            session,
        )

        # Verify system_context.add_context_from_turn was called correctly
        system_context.add_context_from_turn.assert_called_once_with(
            "Test prompt",
            assistant_response,
        )

    async def test_add_project_context_no_prompt(
        self,
        session_manager,
        system_context,
        sample_session,
        user_event,
    ):
        """Test _add_project_context method when prompt is None."""
        # Setup
        assistant_response = "Assistant response"

        # Set up a session with a user event
        session = sample_session.model_copy(deep=True)
        session.events = [user_event]

        # Call _add_project_context with no processed_prompt
        session_manager._add_project_context(None, assistant_response, session)  # noqa: SLF001

        # Verify system_context.add_context_from_turn was called with the user event
        # text
        system_context.add_context_from_turn.assert_called_once_with(
            "User prompt",
            assistant_response,
        )

    async def test_post_process(
        self,
        session_manager,
        json_session_service,
        sample_session,
        assistant_event,
    ):
        """Test post_process method."""
        # Setup
        user_input = "Test prompt"

        # Configure the session with events
        session = sample_session.model_copy(deep=True)
        user_event = Event(
            author="user",
            content=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text="User message")],
            ),
        )
        session.events = [user_event, assistant_event]

        # Mock dependencies
        json_session_service.get_session = AsyncMock(return_value=session)

        # Create spies for the methods we want to verify
        with (
            patch.object(
                session_manager,
                "_squash_turn_events",
                return_value="Assistant response",
            ) as mock_squash,
            patch.object(
                session_manager,
                "_add_project_context",
            ) as mock_add_context,
        ):
            # Call post_process
            await session_manager.post_process(user_input, sample_session)

            # Verify methods were called correctly
            json_session_service.get_session.assert_called_once_with(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
            )

            mock_squash.assert_called_once_with(session)

            mock_add_context.assert_called_once_with(
                user_input=user_input,
                assistant_response="Assistant response",
                session=session,
            )

    async def test_post_process_session_not_found(
        self,
        session_manager,
        json_session_service,
        sample_session,
    ):
        """Test post_process when session is not found."""
        # Setup
        json_session_service.get_session = AsyncMock(return_value=None)

        # Call post_process with a session that doesn't exist
        with pytest.raises(ValueError, match="Session not found"):
            await session_manager.post_process(None, sample_session)
