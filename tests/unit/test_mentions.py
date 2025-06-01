import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from streetrace.args import Args
from streetrace.prompt_processor import PromptProcessor
from streetrace.ui.ui_bus import UiBus


@pytest.fixture(scope="class")
def temp_test_environment(request):
    """Set up a class-scoped temporary test directory structure."""
    base_temp_dir = Path(tempfile.mkdtemp(prefix="streetrace_test_mentions_"))
    test_dir = base_temp_dir / "workdir"
    subdir = test_dir / "subdir"
    outside_dir = base_temp_dir / "outside"

    test_dir.mkdir(parents=True, exist_ok=True)
    subdir.mkdir(parents=True, exist_ok=True)
    outside_dir.mkdir(parents=True, exist_ok=True)

    (test_dir / "file1.txt").write_text("Content of file1")
    (subdir / "file2.py").write_text("Content of file2")
    (test_dir / "other.md").write_text("Markdown content")
    (outside_dir / "secret.txt").write_text("Secret content")
    special_filename = "file_with-hyphen.log"
    (test_dir / special_filename).write_text("Special chars file")

    # Set attributes on the test class if needed
    request.cls.test_dir = test_dir
    request.cls.subdir = subdir
    request.cls.outside_dir = outside_dir
    request.cls.special_filename = special_filename

    yield

    shutil.rmtree(base_temp_dir)


@pytest.mark.usefixtures("temp_test_environment")
class TestMentions:
    def setup_method(self) -> None:
        """Instantiate PromptProcessor for each test."""
        # Mock the UI to avoid console output during tests
        self.mock_ui = MagicMock(spec=UiBus)
        # Instantiate PromptProcessor with the mock UI
        self.prompt_processor = PromptProcessor(
            ui_bus=self.mock_ui,
            args=Args(path=self.test_dir, model="test-model"),
        )

    # --- Test methods using prompt_processor.parse_and_load_mentions ---

    def test_no_mentions(self) -> None:
        prompt = "This is a regular prompt."
        # Call the method on the instance
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert result == []

    def test_one_valid_mention_root(self) -> None:
        prompt = "Please check @file1.txt for details."
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 1
        assert result[0] == (Path("file1.txt"), "Content of file1")

    def test_one_valid_mention_subdir(self) -> None:
        mention_path = Path("subdir") / "file2.py"
        prompt = f"Look at @{mention_path} implementation."
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 1
        assert result[0] == (mention_path, "Content of file2")

    def test_multiple_valid_mentions(self) -> None:
        mention_path_subdir = Path("subdir") / "file2.py"
        prompt = f"Compare @file1.txt and @{mention_path_subdir}."
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 2
        expected = [
            ("file1.txt", "Content of file1"),
            (mention_path_subdir, "Content of file2"),
        ]
        assert len(result) == len(expected)

    def test_duplicate_mentions(self) -> None:
        prompt = "Check @file1.txt and also @file1.txt again."
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 1
        assert result[0] == (Path("file1.txt"), "Content of file1")

    def test_mention_non_existent_file(self) -> None:
        prompt = "What about @nonexistent.txt?"
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert result == []
        # Check if error was displayed via mock UI
        self.mock_ui.dispatch_ui_update.assert_called()

    def test_mention_directory(self) -> None:
        prompt = "Look in @subdir"
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert result == []
        # Check if error was displayed via mock UI
        self.mock_ui.dispatch_ui_update.assert_called()

    def test_mixed_validity_mentions(self) -> None:
        mention_path_subdir = Path("subdir") / "file2.py"
        prompt = f"See @file1.txt and @nonexistent.md and @{mention_path_subdir}"
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 2
        expected = [
            ("file1.txt", "Content of file1"),
            (mention_path_subdir, "Content of file2"),
        ]
        assert len(result) == len(expected)
        # Check if error was displayed for nonexistent.md
        self.mock_ui.dispatch_ui_update.assert_any_call(
            "Skipping @nonexistent.md (path not found or is not a file).",
        )

    def test_mention_outside_working_dir_relative(self) -> None:
        outside_file_path = self.outside_dir / "secret.txt"
        rel_path_to_outside = Path(
            os.path.relpath(str(outside_file_path), str(self.test_dir)),
        )
        prompt = f"Trying to access @{rel_path_to_outside}"
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert result == [], (
            f"Security check failed for relative path: {rel_path_to_outside}"
        )
        # Check if warning was displayed via mock UI
        self.mock_ui.dispatch_ui_update.assert_called()

    def test_mention_outside_working_dir_absolute(self) -> None:
        abs_path_to_secret = self.outside_dir / "secret.txt"
        prompt = f"Trying to access @{abs_path_to_secret}"
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert result == [], (
            f"Security check failed for absolute path: {abs_path_to_secret}"
        )
        # Check if warning was displayed via mock UI
        self.mock_ui.dispatch_ui_update.assert_called()

    def test_mention_with_dot_slash(self) -> None:
        prompt = "Check @./file1.txt"
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 1
        # The returned path should be exactly what was mentioned if valid
        assert result[0] == (Path("./file1.txt"), "Content of file1")

    def test_mention_with_spaces_around(self) -> None:
        prompt = "Check  @file1.txt  now."
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 1
        assert result[0] == (Path("file1.txt"), "Content of file1")

    def test_mention_at_end_of_prompt(self) -> None:
        prompt = "The file is @other.md"
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 1
        assert result[0] == (Path("other.md"), "Markdown content")

    def test_mention_special_chars_in_path(self) -> None:
        prompt = f"Look at @{self.special_filename}"
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 1
        assert result[0] == (Path(self.special_filename), "Special chars file")

    def test_mention_with_trailing_punctuation(self) -> None:
        prompt = "Check @file1.txt, then @subdir/file2.py."
        result = self.prompt_processor.parse_and_load_mentions(prompt)
        assert len(result) == 2
        expected = [
            (Path("file1.txt"), "Content of file1"),
            (Path("subdir") / "file2.py", "Content of file2"),
        ]
        assert len(result) == len(expected)

    def test_build_context(self) -> None:
        """Test that build_context sets up the context object correctly."""
        prompt = "Check @file1.txt please"
        context = self.prompt_processor.build_context(prompt)
        assert context.prompt == prompt
        assert len(context.mentions) == 1
        assert context.mentions[0][0] == Path("file1.txt")
        assert context.mentions[0][1] == "Content of file1"


if __name__ == "__main__":
    unittest.main()
