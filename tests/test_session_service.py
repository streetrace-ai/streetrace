import inspect
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.session_service import MDSessionSerializer, MDSessionService

# Helper to get path of this test file to load sibling .json and .md files
THIS_FILE_PATH = Path(inspect.getsourcefile(lambda: 0) or ".")
EXAMPLE_SESSION_JSON_PATH = THIS_FILE_PATH.parent / (THIS_FILE_PATH.name + ".json")
EXAMPLE_SESSION_MD_PATH = THIS_FILE_PATH.parent / (THIS_FILE_PATH.name + ".md")


@pytest.fixture
def example_session() -> Session:
    """Provide a Session object loaded from the example JSON file."""
    if not EXAMPLE_SESSION_JSON_PATH.exists():
        pytest.fail(f"Example session JSON not found: {EXAMPLE_SESSION_JSON_PATH}")
    return Session.model_validate_json(
        EXAMPLE_SESSION_JSON_PATH.read_text(encoding="utf-8"),
    )


@pytest.fixture
def example_markdown_content() -> str:
    """Provide the content of the example Markdown file."""
    if not EXAMPLE_SESSION_MD_PATH.exists():
        pytest.fail(f"Example session Markdown not found: {EXAMPLE_SESSION_MD_PATH}")
    return EXAMPLE_SESSION_MD_PATH.read_text(encoding="utf-8")


class TestMDSessionSerializer:
    temp_dir_path: Path
    serializer: MDSessionSerializer

    @classmethod
    def setup_class(cls):
        # Create a temporary directory for testing a fresh serializer
        cls.temp_dir_path = Path(tempfile.mkdtemp(prefix="streetrace_test_serializer_"))
        cls.serializer = MDSessionSerializer(cls.temp_dir_path)

    @classmethod
    def teardown_class(cls):
        # Clean up temporary directory
        print(cls.temp_dir_path)
        # shutil.rmtree(cls.temp_dir_path)

    def test_empty_list_sessions(self):
        """Test listing sessions from an empty store."""
        sessions_iter = self.serializer.list_saved(
            app_name="empty_app", user_id="empty_user",
        )
        assert list(sessions_iter) == []

    def test_write_json_state(self):
        """Test listing sessions from an empty store."""
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
        md = file_path.read_text().splitlines()
        expected = [
            "# @pytest - @test_app, Thu May 15 17:46:43 2025 UTC",
            "",
            "## State",
            "",
            "* `another key`: ",
            "  ```json",
            "  {",
            '    "eg": 1',
            "  }",
            "  ```",
            "",
            "",
        ]
        assert md == expected

    def test_tool_call(self):
        """Test listing sessions from an empty store."""
        events = [
            Event(
                author="test_app",
                timestamp=1747331203,
                content=genai_types.Content(
                    parts=[
                        genai_types.Part.from_function_call(
                            name="some_tool",
                            args={"some": "args", "and": {"some": "others"}},
                        ),
                    ],
                ),
            ),
        ]
        session = Session(
            id="1",
            app_name="test_app",
            user_id="pytest",
            events=events,
            last_update_time=1747331203,
        )
        file_path = self.serializer.write(session)
        assert file_path.exists()
        assert file_path.stat().st_size > 0
        md_raw = file_path.read_text()
        md = md_raw.splitlines()
        expected = [
            "# @pytest - @test_app, Thu May 15 17:46:43 2025 UTC",
            "",
            "## Events",
            "",
            "### test_app, Thu May 15 17:46:43 2025 UTC",
            "",
            "#### call: `some_tool`",
            "",
            "    ```json",
            "    {",
            '      "args": {',
            '        "some": "args",',
            '        "and": {',
            '          "some": "others"',
            "        }",
            "      },",
            '      "name": "some_tool"',
            "    }",
            "    ```",
            "",
            "",
        ]
        assert md == expected

    def test_tool_response(self):
        """Test listing sessions from an empty store."""
        events = [
            Event(
                author="user",
                timestamp=1747331203,
                content=genai_types.Content(
                    parts=[
                        genai_types.Part.from_function_response(
                            name="some_tool",
                            response={"some": "values", "and": {"some": "others"}},
                        ),
                    ],
                ),
            ),
        ]
        session = Session(
            id="1",
            app_name="test_app",
            user_id="pytest",
            events=events,
            last_update_time=1747331203,
        )
        file_path = self.serializer.write(session)
        assert file_path.exists()
        assert file_path.stat().st_size > 0
        md_raw = file_path.read_text()
        md = md_raw.splitlines()
        expected = [
            "# @pytest - @test_app, Thu May 15 17:46:43 2025 UTC",
            "",
            "## Events",
            "",
            "### pytest, Thu May 15 17:46:43 2025 UTC",
            "",
            "#### response: `some_tool`",
            "",
            "    ```json",
            "    {",
            '      "name": "some_tool",',
            '      "response": {',
            '        "some": "values",',
            '        "and": {',
            '          "some": "others"',
            "        }",
            "      }",
            "    }",
            "    ```",
            "",
            "",
        ]
        assert md == expected

    def test_write_session(self, example_session: Session):
        """Test listing sessions from an empty store."""
        file_path = self.serializer.write(example_session)
        assert file_path.exists()
        assert file_path.stat().st_size > 0
        md = file_path.read_text().splitlines()
        assert (
            len([line for line in md if line.startswith("#### call: `write_file`")])
            == 1
        )
        assert (
            len([line for line in md if line.startswith("#### response: `write_file`")])
            == 1
        )
        assert len([line for line in md if line.startswith("### Final response")]) == 1
        assert len([line for line in md if line.startswith("### krmrn42, ")]) == 1
        assert len([line for line in md if line.startswith("### StreetRace, ")]) == 1

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
        # Check if parent dirs were removed if empty
        assert (
            not written_path.parent.exists()
        ), "Session directory was not removed after delete."
        assert (
            not written_path.parent.parent.exists()
        ), "User directory was not removed after delete."


class TestMDSessionService:
    temp_dir_path: Path
    service: MDSessionService

    @classmethod
    def setup_class(cls):
        cls.temp_dir_path = Path(tempfile.mkdtemp(prefix="streetrace_test_service_"))
        # Patch logger to avoid issues if streetrace.log is not fully set up for tests
        # We are testing service logic, not logging itself here.
        cls.logger_patcher = patch("streetrace.session_service.logger")
        cls.mock_logger = cls.logger_patcher.start()
        cls.service = MDSessionService(cls.temp_dir_path)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir_path)
        cls.logger_patcher.stop()

    def test_list_delete_session(self, example_session: Session):
        """Test listing and deleting sessions."""
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
        self.service.create_session(**s_info1)
        self.service.create_session(**s_info2)

        listed = self.service.list_sessions(
            app_name=s_info1["app_name"], user_id=s_info1["user_id"],
        )
        assert len(listed.sessions) == 2
        session_ids = {s.id for s in listed.sessions}
        assert "s1" in session_ids and "s2" in session_ids

        self.service.delete_session(**s_info1)
        listed_after_del = self.service.list_sessions(
            app_name=s_info1["app_name"], user_id=s_info1["user_id"],
        )
        assert len(listed_after_del.sessions) == 1
        assert listed_after_del.sessions[0].id == "s2"

        # Check if s1 file is deleted
        md_path_s1 = (
            self.temp_dir_path
            / s_info1["app_name"]
            / s_info1["user_id"]
            / (s_info1["session_id"] + ".md")
        )
        assert not md_path_s1.is_file()

    def test_get_non_existent_session(self):
        """Test getting a session that does not exist in memory or disk."""
        session = self.service.get_session(
            app_name="no_app", user_id="no_user", session_id="no_session",
        )
        assert session is None

    def test_md_session_service_uses_custom_serializer(self):
        """Test that MDSessionService uses the provided serializer instance."""
        mock_serializer = MDSessionSerializer(
            self.temp_dir_path / "custom_serialize_path",
        )
        mock_serializer.write = lambda session: Path("mocked_write")
        mock_serializer.read = lambda app_name, user_id, session_id, config: None

        service_with_mock = MDSessionService(
            self.temp_dir_path, serializer=mock_serializer,
        )

        with (
            patch.object(
                mock_serializer, "write", wraps=mock_serializer.write,
            ) as mock_write,
            patch.object(
                mock_serializer, "read", wraps=mock_serializer.read,
            ) as mock_read,
        ):

            s_info = {"app_name": "custom", "user_id": "ser", "session_id": "s1"}
            service_with_mock.create_session(**s_info)
            mock_write.assert_called_once()

            service_with_mock.get_session(**s_info)
            # get_session calls super().get_session first, then serializer.read
            # If session is created, it is in memory. So clear memory to test read.
            service_with_mock.sessions.clear()
            service_with_mock.get_session(**s_info)
            mock_read.assert_called_once()
