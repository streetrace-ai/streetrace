"""Tests for the JSONSessionSerializer class in session_service.py."""

from pathlib import Path
from unittest.mock import patch

import pytest

from streetrace.session_service import JSONSessionSerializer


class TestJSONSessionSerializer:
    """Tests for the JSONSessionSerializer class."""

    def test_init(self, session_storage_dir):
        """Test initialization of JSONSessionSerializer."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)
        assert serializer.storage_path == session_storage_dir

    def test_file_path_with_separate_params(self, session_storage_dir):
        """Test _file_path method with separate parameters."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        path = serializer._file_path(  # noqa: SLF001
            app_name="test-app",
            user_id="test-user",
            session_id="test-session",
        )

        expected_path = (
            session_storage_dir / "test-app" / "test-user" / "test-session.json"
        )
        assert path == expected_path

    def test_file_path_with_session(self, session_storage_dir, sample_session):
        """Test _file_path method with a session object."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        path = serializer._file_path(session=sample_session)  # noqa: SLF001

        expected_path = (
            session_storage_dir
            / sample_session.app_name
            / sample_session.user_id
            / f"{sample_session.id}.json"
        )
        assert path == expected_path

    def test_file_path_with_missing_params(self, session_storage_dir):
        """Test _file_path method with missing parameters."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        with pytest.raises(
            ValueError,
            match="Either all of app_name, user_id, session_id have to be set",
        ):
            serializer._file_path(app_name="test-app", user_id="test-user")  # noqa: SLF001

        with pytest.raises(
            ValueError,
            match="Either all of app_name, user_id, session_id have to be set",
        ):
            serializer._file_path(app_name="test-app")  # noqa: SLF001

        with pytest.raises(
            ValueError,
            match="Either all of app_name, user_id, session_id have to be set",
        ):
            serializer._file_path()  # noqa: SLF001

    def test_write(self, session_storage_dir, sample_session):
        """Test write method."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Write the session
        path = serializer.write(sample_session)

        # Verify the file was created in the expected location
        expected_path = (
            session_storage_dir
            / sample_session.app_name
            / sample_session.user_id
            / f"{sample_session.id}.json"
        )
        assert path == expected_path
        assert path.exists()
        assert path.is_file()
        assert path.stat().st_size > 0

    def test_read_existing(self, session_storage_dir, sample_session):
        """Test read method with an existing session file."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Write the session first
        serializer.write(sample_session)

        # Read the session
        read_session = serializer.read(
            app_name=sample_session.app_name,
            user_id=sample_session.user_id,
            session_id=sample_session.id,
        )

        # Verify the session was read correctly
        assert read_session is not None
        assert read_session.id == sample_session.id
        assert read_session.app_name == sample_session.app_name
        assert read_session.user_id == sample_session.user_id
        assert read_session.state == sample_session.state

    def test_read_non_existent(self, session_storage_dir):
        """Test read method with a non-existent session file."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Try to read a non-existent session
        read_session = serializer.read(
            app_name="nonexistent",
            user_id="nonexistent",
            session_id="nonexistent",
        )

        # Verify the result is None
        assert read_session is None

    def test_read_unicode_error(self, session_storage_dir):
        """Test read method handling UnicodeDecodeError."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Create a path for a session file
        path = serializer._file_path(  # noqa: SLF001
            app_name="test-app",
            user_id="test-user",
            session_id="unicode-error",
        )
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create a mock path that raises UnicodeDecodeError when read_text is called
        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(
                Path,
                "read_text",
                side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "Invalid byte"),
            ),
            patch("streetrace.session_service.logger") as mock_logger,
        ):
            # Try to read the session
            read_session = serializer.read(
                app_name="test-app",
                user_id="test-user",
                session_id="unicode-error",
            )

            # Verify the result is None
            assert read_session is None

            # Verify the error was logged
            mock_logger.exception.assert_called_once()
            args, _ = mock_logger.exception.call_args
            assert "Cannot read session at" in args[0]

    def test_read_os_error(self, session_storage_dir):
        """Test read method handling OSError."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Create a path for a session file
        path = serializer._file_path(  # noqa: SLF001
            app_name="test-app",
            user_id="test-user",
            session_id="os-error",
        )
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create a mock path that raises OSError when read_text is called
        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(
                Path,
                "read_text",
                side_effect=OSError("Permission denied"),
            ),
            patch("streetrace.session_service.logger") as mock_logger,
        ):
            # Try to read the session
            read_session = serializer.read(
                app_name="test-app",
                user_id="test-user",
                session_id="os-error",
            )

            # Verify the result is None
            assert read_session is None

            # Verify the error was logged
            mock_logger.exception.assert_called_once()
            args, _ = mock_logger.exception.call_args
            assert "Cannot read session at" in args[0]

    def test_delete_existing(self, session_storage_dir, sample_session):
        """Test delete method with an existing session file."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Write the session first
        path = serializer.write(sample_session)
        assert path.exists()

        # Delete the session
        serializer.delete(
            app_name=sample_session.app_name,
            user_id=sample_session.user_id,
            session_id=sample_session.id,
        )

        # Verify the file was deleted
        assert not path.exists()

        # Parent directories should be removed if they're empty
        parent_dir = path.parent
        assert not parent_dir.exists()

        user_dir = parent_dir.parent
        assert not user_dir.exists()

    def test_delete_with_remaining_files(self, session_storage_dir, sample_session):
        """Test delete method when directories still contain other files."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Write the session
        path = serializer.write(sample_session)
        assert path.exists()

        # Create another session file in the same directory
        other_session = sample_session.model_copy(deep=True)
        other_session.id = "other-session"
        other_path = serializer.write(other_session)
        assert other_path.exists()

        # Delete the first session
        serializer.delete(
            app_name=sample_session.app_name,
            user_id=sample_session.user_id,
            session_id=sample_session.id,
        )

        # Verify the file was deleted
        assert not path.exists()

        # Parent directory should still exist because it contains other files
        parent_dir = path.parent
        assert parent_dir.exists()
        assert other_path.exists()

    def test_delete_non_existent(self, session_storage_dir):
        """Test delete method with a non-existent session file."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Try to delete a non-existent session
        # Should not raise any exceptions
        serializer.delete(
            app_name="nonexistent",
            user_id="nonexistent",
            session_id="nonexistent",
        )

    def test_delete_directory(self, session_storage_dir, sample_session):
        """Test delete method when the path is a directory."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Create a directory instead of a file
        path = serializer._file_path(session=sample_session)  # noqa: SLF001
        path.parent.mkdir(parents=True, exist_ok=True)
        path.mkdir(exist_ok=True)

        # Try to delete the "session"
        with patch("streetrace.session_service.logger") as mock_logger:
            serializer.delete(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
            )

            # Verify an error was logged
            mock_logger.error.assert_called_once()
            args, _ = mock_logger.error.call_args
            assert "is a directory" in args[0]

    def test_delete_error_handling(self, session_storage_dir, sample_session):
        """Test delete method error handling."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Write the session
        path = serializer.write(sample_session)
        assert path.exists()

        # Mock unlink to raise an exception
        with (
            patch.object(Path, "unlink", side_effect=OSError("Test error")),
            patch("streetrace.session_service.logger") as mock_logger,
        ):
            # Try to delete the session
            serializer.delete(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
                session_id=sample_session.id,
            )

            # Verify an error was logged
            mock_logger.exception.assert_called_once()
            args, _ = mock_logger.exception.call_args
            assert "Error deleting session file" in args[0]

    def test_list_saved(self, session_storage_dir, sample_session):
        """Test list_saved method."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Write multiple sessions
        serializer.write(sample_session)

        other_session = sample_session.model_copy(deep=True)
        other_session.id = "other-session"
        serializer.write(other_session)

        # List the sessions
        sessions = list(
            serializer.list_saved(
                app_name=sample_session.app_name,
                user_id=sample_session.user_id,
            ),
        )

        # Verify the sessions were listed correctly
        assert len(sessions) == 2
        session_ids = {s.id for s in sessions}
        assert sample_session.id in session_ids
        assert "other-session" in session_ids

        # Verify the listed sessions have the expected structure (metadata only, no
        # events or state)
        for s in sessions:
            assert s.app_name == sample_session.app_name
            assert s.user_id == sample_session.user_id
            assert not s.events
            assert not s.state

    def test_list_saved_empty(self, session_storage_dir):
        """Test list_saved method with no sessions."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # List sessions in an empty directory
        sessions = list(
            serializer.list_saved(
                app_name="test-app",
                user_id="test-user",
            ),
        )

        # Verify no sessions were found
        assert not sessions

    def test_list_saved_with_invalid_files(self, session_storage_dir, sample_session):
        """Test list_saved method with invalid session files."""
        serializer = JSONSessionSerializer(storage_path=session_storage_dir)

        # Write a valid session
        serializer.write(sample_session)

        # Create an invalid session file
        invalid_path = (
            session_storage_dir / sample_session.app_name / sample_session.user_id
        )

        # Create mock for OSError
        with patch.object(Path, "rglob") as mock_rglob:
            # Set up the mock to return a list of paths
            valid_path = serializer._file_path(session=sample_session)  # noqa: SLF001
            invalid_path = invalid_path / "invalid-session.json"
            mock_rglob.return_value = [valid_path, invalid_path]

            # Mock read_text to return valid JSON for the first file and raise OSError
            # for the second
            with (
                patch.object(Path, "is_file", return_value=True),
                patch.object(
                    Path,
                    "read_text",
                    side_effect=[
                        sample_session.model_dump_json(),
                        OSError("Error reading file"),
                    ],
                ),
                patch("streetrace.session_service.logger") as mock_logger,
            ):
                # The implementation should skip invalid files and continue with valid
                # ones
                sessions = list(
                    serializer.list_saved(
                        app_name=sample_session.app_name,
                        user_id=sample_session.user_id,
                    ),
                )

                # Verify only the valid session was listed
                assert len(sessions) == 1
                assert sessions[0].id == sample_session.id

                # Verify an error was logged for the invalid session
                mock_logger.exception.assert_called_once()
                args, _ = mock_logger.exception.call_args
                assert "Could not read session file" in args[0]
