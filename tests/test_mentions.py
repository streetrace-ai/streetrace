import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from streetrace.prompt_processor import PromptProcessor
from streetrace.ui.console_ui import ConsoleUI


class TestMentions(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        """Set up temporary directories once for the class."""
        cls.base_temp_dir = Path(tempfile.mkdtemp(prefix="streetrace_test_mentions_"))
        cls.test_dir = cls.base_temp_dir / "workdir"
        cls.subdir = cls.test_dir / "subdir"
        cls.outside_dir = cls.base_temp_dir / "outside"
        cls.config_dir = cls.base_temp_dir / ".streetrace"

        cls.subdir.mkdir(parents=True, exist_ok=True)
        cls.outside_dir.mkdir(parents=True, exist_ok=True)
        cls.config_dir.mkdir(parents=True, exist_ok=True)

        # Create test files
        with (cls.test_dir / "file1.txt").open("w") as f:
            f.write("Content of file1")
        with (cls.subdir / "file2.py").open("w") as f:
            f.write("Content of file2")
        with (cls.test_dir / "other.md").open("w") as f:
            f.write("Markdown content")
        with (cls.outside_dir / "secret.txt").open("w") as f:
            f.write("Secret content")
        cls.special_filename = "file_with-hyphen.log"
        with (cls.test_dir / cls.special_filename).open("w") as f:
            f.write("Special chars file")

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up the temporary directories once after all tests."""
        if hasattr(cls, "base_temp_dir") and cls.base_temp_dir.exists():
            shutil.rmtree(cls.base_temp_dir)

    def setUp(self) -> None:
        """Instantiate PromptProcessor for each test."""
        # Mock the UI to avoid console output during tests
        self.mock_ui = MagicMock(spec=ConsoleUI)
        # Instantiate PromptProcessor with the mock UI and temp config dir
        self.prompt_processor = PromptProcessor(
            ui=self.mock_ui,
            config_dir=self.config_dir,
        )

    # --- Test methods using prompt_processor.parse_and_load_mentions ---

    def test_no_mentions(self) -> None:
        prompt = "This is a regular prompt."
        # Call the method on the instance
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert result == []

    def test_one_valid_mention_root(self) -> None:
        prompt = "Please check @file1.txt for details."
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 1
        assert result[0] == (Path("file1.txt"), "Content of file1")

    def test_one_valid_mention_subdir(self) -> None:
        mention_path = Path("subdir") / "file2.py"
        prompt = f"Look at @{mention_path} implementation."
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 1
        assert result[0] == (mention_path, "Content of file2")

    def test_multiple_valid_mentions(self) -> None:
        mention_path_subdir = Path("subdir") / "file2.py"
        prompt = f"Compare @file1.txt and @{mention_path_subdir}."
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 2
        expected = [
            ("file1.txt", "Content of file1"),
            (mention_path_subdir, "Content of file2"),
        ]
        assert len(result) == len(expected)

    def test_duplicate_mentions(self) -> None:
        prompt = "Check @file1.txt and also @file1.txt again."
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 1
        assert result[0] == (Path("file1.txt"), "Content of file1")

    def test_mention_non_existent_file(self) -> None:
        prompt = "What about @nonexistent.txt?"
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert result == []
        # Check if error was displayed via mock UI
        self.mock_ui.display_error.assert_called()

    def test_mention_directory(self) -> None:
        prompt = "Look in @subdir"
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert result == []
        # Check if error was displayed via mock UI
        self.mock_ui.display_error.assert_called()

    def test_mixed_validity_mentions(self) -> None:
        mention_path_subdir = Path("subdir") / "file2.py"
        prompt = f"See @file1.txt and @nonexistent.md and @{mention_path_subdir}"
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 2
        expected = [
            ("file1.txt", "Content of file1"),
            (mention_path_subdir, "Content of file2"),
        ]
        assert len(result) == len(expected)
        # Check if error was displayed for nonexistent.md
        self.mock_ui.display_error.assert_called_with(
            "Mentioned path @nonexistent.md not found or is not a file. Skipping.",
        )

    def test_mention_outside_working_dir_relative(self) -> None:
        outside_file_path = self.outside_dir / "secret.txt"
        rel_path_to_outside = Path(
            os.path.relpath(str(outside_file_path), str(self.test_dir)),
        )
        prompt = f"Trying to access @{rel_path_to_outside}"
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert (
            result == []
        ), f"Security check failed for relative path: {rel_path_to_outside}"
        # Check if warning was displayed via mock UI
        self.mock_ui.display_warning.assert_called()

    def test_mention_outside_working_dir_absolute(self) -> None:
        abs_path_to_secret = self.outside_dir / "secret.txt"
        prompt = f"Trying to access @{abs_path_to_secret}"
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert (
            result == []
        ), f"Security check failed for absolute path: {abs_path_to_secret}"
        # Check if warning was displayed via mock UI
        self.mock_ui.display_warning.assert_called()

    def test_mention_with_dot_slash(self) -> None:
        prompt = "Check @./file1.txt"
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 1
        # The returned path should be exactly what was mentioned if valid
        assert result[0] == (Path("./file1.txt"), "Content of file1")

    def test_mention_with_spaces_around(self) -> None:
        prompt = "Check  @file1.txt  now."
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 1
        assert result[0] == (Path("file1.txt"), "Content of file1")

    def test_mention_at_end_of_prompt(self) -> None:
        prompt = "The file is @other.md"
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 1
        assert result[0] == (Path("other.md"), "Markdown content")

    def test_mention_special_chars_in_path(self) -> None:
        prompt = f"Look at @{self.special_filename}"
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 1
        assert result[0] == (Path(self.special_filename), "Special chars file")

    def test_mention_with_trailing_punctuation(self) -> None:
        prompt = "Check @file1.txt, then @subdir/file2.py."
        result = self.prompt_processor.parse_and_load_mentions(prompt, self.test_dir)
        assert len(result) == 2
        expected = [
            (Path("file1.txt"), "Content of file1"),
            (Path("subdir") / "file2.py", "Content of file2"),
        ]
        assert len(result) == len(expected)


if __name__ == "__main__":
    unittest.main()
