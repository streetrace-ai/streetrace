import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

# Import PromptProcessor instead of the old function
from streetrace.prompt_processor import PromptProcessor
from streetrace.ui.console_ui import ConsoleUI

# Removed the old imports
# from streetrace.main import parse_and_load_mentions, parse_arguments
# parse_and_load_mentions_func = parse_and_load_mentions
# parse_arguments_func = parse_arguments  # Store it too


class TestMentions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up temporary directories once for the class."""
        cls.base_temp_dir = tempfile.mkdtemp(prefix="streetrace_test_mentions_")
        cls.test_dir = os.path.join(cls.base_temp_dir, "workdir")
        cls.subdir = os.path.join(cls.test_dir, "subdir")
        cls.outside_dir = os.path.join(cls.base_temp_dir, "outside")
        cls.config_dir = os.path.join(cls.base_temp_dir, ".streetrace") # For PromptProcessor

        os.makedirs(cls.subdir)
        os.makedirs(cls.outside_dir)
        os.makedirs(cls.config_dir)

        # Create test files
        with open(os.path.join(cls.test_dir, "file1.txt"), "w") as f:
            f.write("Content of file1")
        with open(os.path.join(cls.subdir, "file2.py"), "w") as f:
            f.write("Content of file2")
        with open(os.path.join(cls.test_dir, "other.md"), "w") as f:
            f.write("Markdown content")
        with open(os.path.join(cls.outside_dir, "secret.txt"), "w") as f:
            f.write("Secret content")
        cls.special_filename = "file_with-hyphen.log"
        with open(os.path.join(cls.test_dir, cls.special_filename), "w") as f:
            f.write("Special chars file")

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary directories once after all tests."""
        if hasattr(cls, "base_temp_dir") and os.path.exists(cls.base_temp_dir):
            shutil.rmtree(cls.base_temp_dir)

    def setUp(self):
        """Instantiate PromptProcessor for each test."""
        # Mock the UI to avoid console output during tests
        self.mock_ui = MagicMock(spec=ConsoleUI)
        # Instantiate PromptProcessor with the mock UI and temp config dir
        self.prompt_processor = PromptProcessor(ui=self.mock_ui, config_dir=self.config_dir)

    # --- Test methods using prompt_processor._parse_and_load_mentions ---

    def test_no_mentions(self):
        prompt = "This is a regular prompt."
        # Call the method on the instance
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(result, [])

    def test_one_valid_mention_root(self):
        prompt = "Please check @file1.txt for details."
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("file1.txt", "Content of file1"))

    def test_one_valid_mention_subdir(self):
        mention_path = os.path.join("subdir", "file2.py")
        prompt = f"Look at @{mention_path} implementation."
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (mention_path, "Content of file2"))

    def test_multiple_valid_mentions(self):
        mention_path_subdir = os.path.join("subdir", "file2.py")
        prompt = f"Compare @file1.txt and @{mention_path_subdir}."
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 2)
        expected = [
            ("file1.txt", "Content of file1"),
            (mention_path_subdir, "Content of file2"),
        ]
        self.assertCountEqual(result, expected)

    def test_duplicate_mentions(self):
        prompt = "Check @file1.txt and also @file1.txt again."
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("file1.txt", "Content of file1"))

    def test_mention_non_existent_file(self):
        prompt = "What about @nonexistent.txt?"
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(result, [])
        # Check if error was displayed via mock UI
        self.mock_ui.display_error.assert_called()

    def test_mention_directory(self):
        prompt = "Look in @subdir"
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(result, [])
        # Check if error was displayed via mock UI
        self.mock_ui.display_error.assert_called()

    def test_mixed_validity_mentions(self):
        mention_path_subdir = os.path.join("subdir", "file2.py")
        prompt = f"See @file1.txt and @nonexistent.md and @{mention_path_subdir}"
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 2)
        expected = [
            ("file1.txt", "Content of file1"),
            (mention_path_subdir, "Content of file2"),
        ]
        self.assertCountEqual(result, expected)
        # Check if error was displayed for nonexistent.md
        self.mock_ui.display_error.assert_called_with(
            f"Mentioned path @nonexistent.md ('{os.path.realpath(os.path.join(self.test_dir, 'nonexistent.md'))}') not found or is not a file. Skipping."
        )

    def test_mention_outside_working_dir_relative(self):
        outside_file_path = os.path.join(self.outside_dir, "secret.txt")
        rel_path_to_outside = os.path.relpath(outside_file_path, self.test_dir)
        prompt = f"Trying to access @{rel_path_to_outside}"
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(
            result,
            [],
            f"Security check failed for relative path: {rel_path_to_outside}",
        )
        # Check if warning was displayed via mock UI
        self.mock_ui.display_warning.assert_called()

    def test_mention_outside_working_dir_absolute(self):
        abs_path_to_secret = os.path.join(self.outside_dir, "secret.txt")
        prompt = f"Trying to access @{abs_path_to_secret}"
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(
            result, [], f"Security check failed for absolute path: {abs_path_to_secret}"
        )
        # Check if warning was displayed via mock UI
        self.mock_ui.display_warning.assert_called()

    def test_mention_with_dot_slash(self):
        prompt = "Check @./file1.txt"
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        # The returned path should be exactly what was mentioned if valid
        self.assertEqual(result[0], ("./file1.txt", "Content of file1"))

    def test_mention_with_spaces_around(self):
        prompt = "Check  @file1.txt  now."
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("file1.txt", "Content of file1"))

    def test_mention_at_end_of_prompt(self):
        prompt = "The file is @other.md"
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("other.md", "Markdown content"))

    def test_mention_special_chars_in_path(self):
        prompt = f"Look at @{self.special_filename}"
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (self.special_filename, "Special chars file"))

    def test_mention_with_trailing_punctuation(self):
        prompt = "Check @file1.txt, then @subdir/file2.py."
        result = self.prompt_processor._parse_and_load_mentions(prompt, self.test_dir)
        self.assertEqual(len(result), 2)
        expected = [
            ("file1.txt", "Content of file1"),
            (os.path.join("subdir", "file2.py"), "Content of file2"),
        ]
        self.assertCountEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
