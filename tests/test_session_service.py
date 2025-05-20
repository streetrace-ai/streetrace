import inspect
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from google.adk.sessions import Session

from streetrace.session_service import JSONSessionSerializer, JSONSessionService

THIS_FILE_PATH = Path(inspect.getsourcefile(lambda: 0) or ".")
EXAMPLE_SESSION_JSON_PATH = THIS_FILE_PATH.parent / (THIS_FILE_PATH.name + ".json")
EXAMPLE_SESSION_MD_PATH = THIS_FILE_PATH.parent / (THIS_FILE_PATH.name + ".json")


@pytest.fixture
def example_session() -> Session:
    """Provide a Session object loaded from the example JSON file."""
    if not EXAMPLE_SESSION_JSON_PATH.exists():  # pragma: no cover
        pytest.fail(f"Example session JSON not found: {EXAMPLE_SESSION_JSON_PATH}")
    return Session.model_validate_json(
        EXAMPLE_SESSION_JSON_PATH.read_text(encoding="utf-8"),
    )


@pytest.fixture
def temp_file(tmp_path: Path) -> Path:
    """Create a temporary JSON file path."""
    return tmp_path / "test_session.json"


class TestSessionSerializer:
    temp_dir_path: Path
    serializer: JSONSessionSerializer

    @classmethod
    def setup_class(cls):
        cls.temp_dir_path = Path(
            tempfile.mkdtemp(prefix="streetrace_test_serializer_"),
        )
        print(cls.temp_dir_path)  # noqa: T201 left for debugging
        cls.serializer = JSONSessionSerializer(cls.temp_dir_path)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir_path)

    def test_read_write_sessions(self, example_session: Session):
        session_path = self.serializer.write(example_session)

        assert session_path.is_file()
        assert session_path.lstat().st_size > 0

        session = self.serializer.read(
            example_session.app_name,
            example_session.user_id,
            example_session.id,
        )

        assert session is not None
        assert session == example_session
        assert session is not example_session

        all_sessions: list[Session] = list(
            self.serializer.list_saved(
                app_name=example_session.app_name,
                user_id=example_session.user_id,
            ),
        )

        assert len(all_sessions) == 1
        assert all_sessions[0].app_name == example_session.app_name
        assert all_sessions[0].user_id == example_session.user_id
        assert all_sessions[0].id == example_session.id
        assert len(all_sessions[0].events) == 0
        assert len(all_sessions[0].state) == 0

    def test_write_json_state(self):
        """Test writing a session with JSON state and verify output."""
        state_obj = {"another key": {"eg": 1}}
        session = Session(
            id="1",
            app_name="test_app",
            user_id="pytest",
            state=state_obj,
            last_update_time=1747331203,
        )
        file_path = self.serializer.write(session)
        assert file_path.exists()
        assert file_path.stat().st_size > 0

        saved_session = self.serializer.read(
            app_name="test_app",
            user_id="pytest",
            session_id="1",
        )

        assert saved_session.state
        assert "another key" in saved_session.state
        assert saved_session.state["another key"] == {"eg": 1}

    def test_delete_session(self, example_session: Session):
        """Test deleting a session file."""
        session_to_delete = example_session.model_copy(deep=True)
        session_to_delete.id = "test-delete-session"
        session_to_delete.app_name = "delete_app"
        session_to_delete.user_id = "delete_user"

        written_path = self.serializer.write(session_to_delete)
        assert written_path.is_file(), "File to be deleted was not written."

        self.serializer.delete(
            app_name=session_to_delete.app_name,
            user_id=session_to_delete.user_id,
            session_id=session_to_delete.id,
        )
        assert not written_path.is_file(), "Session file was not deleted."
        assert not written_path.parent.exists(), (
            "Session directory was not removed after delete."
        )
        assert not written_path.parent.parent.exists(), (
            "User directory was not removed after delete."
        )


class TestSessionService:
    temp_dir_path: Path
    service: JSONSessionService

    @classmethod
    def setup_class(cls):
        cls.temp_dir_path = Path(tempfile.mkdtemp(prefix="streetrace_test_service_"))
        cls.logger_patcher = patch("streetrace.session_service.logger")
        cls.mock_logger = cls.logger_patcher.start()
        cls.service = JSONSessionService(cls.temp_dir_path)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir_path)
        cls.logger_patcher.stop()

    def test_list_delete_session(self):
        """Test listing and deleting sessions through the service."""
        s_info1 = {
            "app_name": "listdel_app",
            "user_id": "listdel_user",
            "session_id": "s1",
        }
        s_info2 = {
            "app_name": "listdel_app",
            "user_id": "listdel_user",
            "session_id": "s2",
        }
        self.service.create_session(**s_info1, state={"key": "val1"})
        self.service.create_session(**s_info2, state={"key": "val2"})

        listed = self.service.list_sessions(
            app_name=s_info1["app_name"],
            user_id=s_info1["user_id"],
        )
        assert len(listed.sessions) == 2
        session_ids = {s.id for s in listed.sessions}
        assert "s1" in session_ids
        assert "s2" in session_ids
        for s in listed.sessions:
            assert not s.state
            assert not s.events

        self.service.delete_session(**s_info1)
        listed_after_del = self.service.list_sessions(
            app_name=s_info1["app_name"],
            user_id=s_info1["user_id"],
        )
        assert len(listed_after_del.sessions) == 1
        assert listed_after_del.sessions[0].id == "s2"

        md_path_s1 = (
            self.temp_dir_path
            / s_info1["app_name"]
            / s_info1["user_id"]
            / (s_info1["session_id"] + ".json")
        )
        assert not md_path_s1.is_file()

    def test_get_non_existent_session(self):
        """Test getting a session that does not exist in memory or disk."""
        session = self.service.get_session(
            app_name="no_app",
            user_id="no_user",
            session_id="no_session",
        )
        assert session is None
