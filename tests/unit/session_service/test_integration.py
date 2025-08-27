"""Integration tests for session_service.py."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from google.adk.events import Event
from google.genai import types as genai_types

from streetrace.args import Args
from streetrace.session.json_serializer import JSONSessionSerializer
from streetrace.session.session_manager import SessionManager, _session_id
from streetrace.session.session_service import JSONSessionService


@pytest.fixture
def real_args() -> Args:
    """Create real Args object with test values."""
    args = Mock(spec=Args)
    args.app_name = "test-app"
    args.user_id = "test-user"
    args.session_id = None

    # Mock properties
    args.effective_app_name = "test-app"
    args.effective_user_id = "test-user"

    return args


class TestSessionServiceIntegration:
    """Integration tests for session_service module."""

    async def test_full_session_lifecycle(self, real_args, ui_bus, system_context):
        """Test the complete session lifecycle from creation to deletion."""
        # Create a temporary directory for session storage
        with tempfile.TemporaryDirectory() as temp_dir_path:
            storage_dir = Path(temp_dir_path)

            # Fixed session ID for testing
            test_session_id = "test-session"

            # Create serializer and service
            json_serializer = JSONSessionSerializer(storage_path=storage_dir)
            json_session_service = JSONSessionService(
                serializer=json_serializer,
            )

            # Create session manager with fixed session ID
            with patch(
                "streetrace.session.session_manager._session_id",
                return_value=test_session_id,
            ):
                session_manager = SessionManager(
                    args=real_args,
                    system_context=system_context,
                    ui_bus=ui_bus,
                )

                # Verify the initial session ID
                assert session_manager.current_session_id == test_session_id

                # Create a new session
                session = await session_manager.get_or_create_session()
                assert session is not None
                assert session.id == test_session_id
                assert session.app_name == real_args.effective_app_name
                assert session.user_id == real_args.effective_user_id

                # Get the existing session
                existing_session = await session_manager.get_current_session()
                assert existing_session is not None
                assert existing_session.id == test_session_id

                # Clear memory caches to ensure we're reading from disk
                json_session_service.sessions.clear()

                # Get the session again to force reading from disk
                disk_session = await session_manager.get_current_session()
                assert disk_session is not None
                assert disk_session.id == test_session_id

                # Add a user event to the session
                user_event = Event(
                    author="user",
                    content=genai_types.Content(
                        role="user",
                        parts=[genai_types.Part.from_text(text="Test user message")],
                    ),
                )
                await json_session_service.append_event(disk_session, user_event)

                # Add an assistant event
                assistant_event = Event(
                    author="assistant",
                    content=genai_types.Content(
                        role="assistant",
                        parts=[
                            genai_types.Part.from_text(text="Test assistant response"),
                        ],
                    ),
                )
                await json_session_service.append_event(disk_session, assistant_event)

                # Clear memory cache again
                json_session_service.sessions.clear()

                # Get session again for post-processing
                current_session = await session_manager.get_current_session()
                assert current_session is not None

                # List all sessions
                await session_manager.display_sessions()

                # Reset the session with a new ID
                new_session_id = "new-session"
                with patch(
                    "streetrace.session.session_manager._session_id",
                    return_value=new_session_id,
                ):
                    session_manager.reset_session()
                    assert session_manager.current_session_id == new_session_id

                # Create a new session with the new ID
                new_session = await session_manager.get_or_create_session()
                assert new_session.id == new_session_id

                # List all sessions again
                await session_manager.display_sessions()

                # Clean up - delete sessions
                await json_session_service.delete_session(
                    app_name=real_args.effective_app_name,
                    user_id=real_args.effective_user_id,
                    session_id=test_session_id,
                )

                await json_session_service.delete_session(
                    app_name=real_args.effective_app_name,
                    user_id=real_args.effective_user_id,
                    session_id=new_session_id,
                )

    def test_session_id_generation(self):
        """Test session ID generation with timezone awareness."""
        # Test with a fixed time
        expected_id = "2023-01-15_10-30"

        with patch("streetrace.session.session_manager.datetime") as mock_dt:
            mock_datetime = Mock()
            mock_datetime.strftime.return_value = expected_id
            mock_dt.now.return_value = mock_datetime

            session_id = _session_id()
            assert session_id == expected_id
