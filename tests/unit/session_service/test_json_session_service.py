"""Tests for the JSONSessionService class in session_service.py."""

from unittest.mock import AsyncMock, Mock, patch

from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.session_service import JSONSessionSerializer, JSONSessionService


class TestJSONSessionService:
    """Tests for the JSONSessionService class."""

    async def test_init(self, session_storage_dir, json_serializer):
        """Test initialization of JSONSessionService."""
        # Test with default serializer
        service = JSONSessionService(storage_path=session_storage_dir)
        assert isinstance(service.serializer, JSONSessionSerializer)
        assert service.serializer.storage_path == session_storage_dir

        # Test with provided serializer
        service_with_serializer = JSONSessionService(
            storage_path=session_storage_dir,
            serializer=json_serializer,
        )
        assert service_with_serializer.serializer is json_serializer

    async def test_get_session_from_memory(self, session_storage_dir, sample_session):
        """Test get_session method retrieving from memory."""
        # Initialize the service
        service = JSONSessionService(storage_path=session_storage_dir)

        # Add a session to memory
        app_name = sample_session.app_name
        user_id = sample_session.user_id
        session_id = sample_session.id

        # Mock the superclass get_session method to return the sample session
        with patch(
            "streetrace.session_service.InMemorySessionService.get_session",
            new=AsyncMock(return_value=sample_session),
        ) as mock_super_get:
            # Mock serializer to verify it's not called
            service.serializer = Mock(spec=JSONSessionSerializer)

            # Get the session
            result = await service.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
            )

            # Verify the session was retrieved from memory via the superclass method
            assert (
                result == sample_session
            )  # Equal, but not necessarily the same object
            mock_super_get.assert_called_once_with(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                config=None,
            )
            service.serializer.read.assert_not_called()

    async def test_get_session_from_storage(self, session_storage_dir, sample_session):
        """Test get_session method retrieving from storage."""
        # Initialize the service
        service = JSONSessionService(storage_path=session_storage_dir)

        # Mock the superclass get_session method to return None (not in memory)
        with patch(
            "streetrace.session_service.InMemorySessionService.get_session",
            new=AsyncMock(return_value=None),
        ):
            # Set up serializer to return our sample session
            service.serializer = Mock(spec=JSONSessionSerializer)
            service.serializer.read.return_value = sample_session

            # Get the session
            result = await service.get_session(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
            )

            # Verify the session was retrieved from storage and added to memory
            assert result is not None
            assert result.id == sample_session.id
            service.serializer.read.assert_called_once_with(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
                config=None,
            )

            # Verify the session was added to memory
            assert (
                service.sessions[sample_session.app_name][sample_session.user_id][
                    sample_session.id
                ]
                is not None
            )

    async def test_get_session_not_found(self, session_storage_dir):
        """Test get_session method when session doesn't exist."""
        # Initialize the service
        service = JSONSessionService(storage_path=session_storage_dir)

        # Mock the superclass get_session method to return None (not in memory)
        with patch(
            "streetrace.session_service.InMemorySessionService.get_session",
            new=AsyncMock(return_value=None),
        ):
            # Set up serializer to return None (session doesn't exist)
            service.serializer = Mock(spec=JSONSessionSerializer)
            service.serializer.read.return_value = None

            # Get a non-existent session
            result = await service.get_session(
                app_name="nonexistent",
                user_id="nonexistent",
                session_id="nonexistent",
            )

            # Verify the result is None
            assert result is None
            service.serializer.read.assert_called_once_with(
                app_name="nonexistent",
                user_id="nonexistent",
                session_id="nonexistent",
                config=None,
            )

    async def test_create_session(self, session_storage_dir, sample_session):
        """Test create_session method."""
        # Initialize the service
        service = JSONSessionService(storage_path=session_storage_dir)

        # Mock the superclass create_session method to return a session
        with patch(
            "streetrace.session_service.InMemorySessionService.create_session",
            new=AsyncMock(return_value=sample_session),
        ) as mock_create:
            # Mock the serializer
            service.serializer = Mock(spec=JSONSessionSerializer)

            # Create a session
            result = await service.create_session(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
                state=sample_session.state,
            )

            # Verify the session was created and saved
            assert result is not None
            assert result.id == sample_session.id
            assert result.app_name == sample_session.app_name
            assert result.user_id == sample_session.user_id

            mock_create.assert_called_once_with(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
                state=sample_session.state,
            )

            # Verify serializer.write was called with session keyword argument
            service.serializer.write.assert_called_once_with(session=sample_session)

    async def test_replace_events(self, session_storage_dir, sample_session):
        """Test replace_events method."""
        # Initialize the service
        service = JSONSessionService(storage_path=session_storage_dir)

        # Create a session with events
        original_events = [
            Event(
                author="user",
                content=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text="Original event 1")],
                ),
            ),
            Event(
                author="user",
                content=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text="Original event 2")],
                ),
            ),
        ]

        session_with_events = sample_session.model_copy(deep=True)
        session_with_events.events = original_events

        # New events to replace the old ones
        new_events = [
            Event(
                author="user",
                content=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text="New event")],
                ),
            ),
        ]

        # Replace events starting at index 1
        start_at = 1

        # Create a new empty session
        new_session = sample_session.model_copy(deep=True)
        new_session.events = []

        # Mock get_session to return a session with the expected events
        final_session = sample_session.model_copy(deep=True)
        final_session.events = [original_events[0], *new_events]

        async def fake_append(session, event):
            return session.events.append(event) or event

        # We need to patch the super() methods that are called directly
        with (
            patch(
                "streetrace.session_service.InMemorySessionService.create_session",
                new=AsyncMock(return_value=new_session),
            ) as mock_super_create,
            patch(
                "streetrace.session_service.InMemorySessionService.append_event",
                new=AsyncMock(side_effect=fake_append),
            ) as mock_super_append,
            patch(
                "streetrace.session_service.InMemorySessionService.get_session",
                new=AsyncMock(return_value=final_session),
            ) as mock_super_get,
        ):
            # Mock the serializer.write method
            service.serializer = Mock(spec=JSONSessionSerializer)

            # Call replace_events
            result = await service.replace_events(
                session=session_with_events,
                new_events=new_events,
                start_at=start_at,
            )

            # Verify super().create_session was called correctly
            mock_super_create.assert_called_once_with(
                app_name=session_with_events.app_name,
                user_id=session_with_events.user_id,
                session_id=session_with_events.id,
                state=session_with_events.state,
            )

            # Verify super().append_event was called for each event
            assert mock_super_append.call_count == 1 + len(
                new_events,
            )  # 1 original event + new events

            # Verify super().get_session was called
            mock_super_get.assert_called_once_with(
                app_name=session_with_events.app_name,
                user_id=session_with_events.user_id,
                session_id=session_with_events.id,
            )

            # Verify serializer.write was called
            service.serializer.write.assert_called_once()

            # Verify the result
            assert result == final_session

    async def test_list_sessions(self, session_storage_dir):
        """Test list_sessions method."""
        # Initialize the service
        service = JSONSessionService(storage_path=session_storage_dir)

        # Mock the serializer
        service.serializer = Mock(spec=JSONSessionSerializer)

        # Mock list_saved to return some sessions
        session1 = Session(id="session1", app_name="test-app", user_id="test-user")
        session2 = Session(id="session2", app_name="test-app", user_id="test-user")
        service.serializer.list_saved.return_value = [session1, session2]

        # List sessions
        result = await service.list_sessions(
            app_name="test-app",
            user_id="test-user",
        )

        # Verify serializer.list_saved was called
        service.serializer.list_saved.assert_called_once_with(
            app_name="test-app",
            user_id="test-user",
        )

        # Verify the result
        assert len(result.sessions) == 2
        session_ids = {s.id for s in result.sessions}
        assert "session1" in session_ids
        assert "session2" in session_ids

    async def test_delete_session(self, session_storage_dir, sample_session):
        """Test delete_session method."""
        # Initialize the service
        service = JSONSessionService(storage_path=session_storage_dir)

        # Mock the superclass delete_session method
        with patch(
            "streetrace.session_service.InMemorySessionService.delete_session",
        ) as mock_super_delete:
            # Mock the serializer
            service.serializer = Mock(spec=JSONSessionSerializer)

            # Delete the session
            await service.delete_session(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
            )

            # Verify superclass delete_session was called
            mock_super_delete.assert_called_once_with(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
            )

            # Verify serializer.delete was called
            service.serializer.delete.assert_called_once_with(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
            )

    async def test_append_event(self, session_storage_dir, sample_session):
        """Test append_event method."""
        # Initialize the service
        service = JSONSessionService(storage_path=session_storage_dir)

        # Create an event to append
        event = Event(
            author="user",
            content=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text="Test event")],
            ),
        )
        # Mock the superclass append_event method
        with patch(
            "streetrace.session_service.InMemorySessionService.append_event",
            new=AsyncMock(return_value=event),
        ) as mock_super_append:
            # Mock the serializer
            service.serializer = Mock(spec=JSONSessionSerializer)

            # Append the event
            result = await service.append_event(
                session=sample_session,
                event=event,
            )

            # Verify superclass append_event was called
            mock_super_append.assert_called_once_with(
                session=sample_session,
                event=event,
            )

            # Verify serializer.write was called with the session
            service.serializer.write.assert_called_once()

            # Verify the result is the event returned by the superclass method
            assert result == event
