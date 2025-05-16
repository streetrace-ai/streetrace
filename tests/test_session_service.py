import inspect
import shutil
import tempfile
from pathlib import Path

import marko
import marko.md_renderer
import pytest
from google.adk.sessions import Session

from streetrace.session_service import MDSessionSerializer


class TestMDSessionSerializer:
    def setup_class(self):

        this_path = inspect.getsourcefile(lambda:0)
        if not this_path:
            msg = "Path to current module not identified"
            raise ValueError(msg)
        this_path = Path(this_path + ".json")
        self.session = Session.model_validate_json(this_path.read_text())
        # Create a temporary directory structure for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.serializer = MDSessionSerializer(self.temp_dir)
        self.app_name = "test_app"
        self.user_id = "test_user"


    def teardown_class(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_empty_list(self):
        saved_sessions = self.serializer.list_saved(app_name=self.app_name, user_id=self.user_id)
        with pytest.raises(expected_exception=StopIteration):
            next(saved_sessions)

    def test_write_session(self):
        session_path = self.serializer.write(self.session)
        assert session_path.is_file()
        assert session_path.stat().st_size > 0

    def test_marko(self):
        ast = marko.parse("#### call: `read_file`")
        print("rst:", ast)
        markdown = marko.Markdown(renderer=marko.renderer.).render(ast)
        print("markdown:", markdown)

        ast = marko.Markdown().parse(md)
        print("rst:", ast)
        markdown = marko.Markdown(renderer=marko.md_renderer.MarkdownRenderer).render(ast)
        print("markdown:", markdown)
