"""Tests for utility functions and classes in session_service.py."""

from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from streetrace.session_service import DisplaySessionsList, _session_id


def test_session_id_with_user_provided_id():
    """Test that _session_id returns the user-provided ID when given."""
    assert _session_id("my-custom-id") == "my-custom-id"


def test_session_id_without_user_provided_id():
    """Test that _session_id generates an ID based on current time when not provided."""
    expected_id = "2023-05-15_10-30"

    with patch("streetrace.session_service.datetime") as mock_dt:
        mock_datetime = Mock()
        mock_datetime.strftime.return_value = expected_id
        mock_dt.now.return_value = mock_datetime

        result = _session_id()

        mock_dt.now.assert_called_once()
        assert result == expected_id


class TestDisplaySessionsList:
    """Tests for the DisplaySessionsList model and its renderer."""

    @pytest.fixture
    def mock_console(self):
        """Create a mock console for testing."""
        return Console()

    @pytest.fixture
    def empty_sessions_list(self):
        """Create an empty sessions list."""
        from google.adk.sessions.base_session_service import ListSessionsResponse

        return DisplaySessionsList(
            app_name="test-app",
            user_id="test-user",
            list_sessions=ListSessionsResponse(sessions=[]),
        )

    @pytest.fixture
    def populated_sessions_list(self):
        """Create a populated sessions list."""
        from google.adk.sessions import Session
        from google.adk.sessions.base_session_service import ListSessionsResponse

        sessions = [
            Session(
                id="session1",
                app_name="test-app",
                user_id="test-user",
                last_update_time=1622541234,
            ),
            Session(
                id="session2",
                app_name="test-app",
                user_id="test-user",
                last_update_time=1622541567,
            ),
        ]

        return DisplaySessionsList(
            app_name="test-app",
            user_id="test-user",
            list_sessions=ListSessionsResponse(sessions=sessions),
        )

    def test_render_list_of_sessions_empty(self, empty_sessions_list, mock_console):
        """Test rendering an empty sessions list."""
        from streetrace.session_service import render_list_of_sessions

        # Use a patch to check what's being printed without actually printing
        with patch.object(mock_console, "print") as mock_print:
            render_list_of_sessions(empty_sessions_list, mock_console)

            # Check that the correct message was printed
            mock_print.assert_called_once()
            args, _ = mock_print.call_args
            assert "No sessions found" in args[0]
            assert empty_sessions_list.app_name in args[0]
            assert empty_sessions_list.user_id in args[0]

    def test_render_list_of_sessions_populated(
        self,
        populated_sessions_list,
        mock_console,
    ):
        """Test rendering a populated sessions list."""
        from streetrace.session_service import render_list_of_sessions

        # Use a patch to check what's being printed without actually printing
        with patch.object(mock_console, "print") as mock_print:
            render_list_of_sessions(populated_sessions_list, mock_console)

            # Check that the correct message was printed
            mock_print.assert_called_once()
            args, _ = mock_print.call_args
            assert "Available sessions" in args[0]
            assert populated_sessions_list.app_name in args[0]
            assert populated_sessions_list.user_id in args[0]
            assert "session1" in args[0]
            assert "session2" in args[0]
