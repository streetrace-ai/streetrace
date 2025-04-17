import os
import shutil
import tempfile
import unittest

import pathspec

from streetrace.tools.read_directory_structure import load_gitignore_for_directory


class TestLoadGitignore(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.mkdtemp()

        # Create nested directory structure
        self.sub_dir = os.path.join(self.temp_dir, "sub_dir")
        self.nested_dir = os.path.join(self.sub_dir, "nested_dir")
        os.makedirs(self.nested_dir, exist_ok=True)

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_no_gitignore(self):
        # Test when no .gitignore files exist
        result = load_gitignore_for_directory(self.nested_dir)
        self.assertIsNone(result)

    def test_single_gitignore(self):
        # Create a .gitignore file in the nested directory
        gitignore_path = os.path.join(self.nested_dir, ".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.log\n")

        result = load_gitignore_for_directory(self.nested_dir)

        # Verify the result is a PathSpec
        self.assertIsInstance(result, pathspec.PathSpec)

        # Create a test file to verify pattern matching
        test_log_path = os.path.join(self.nested_dir, "test.log")
        test_txt_path = os.path.join(self.nested_dir, "test.txt")
        with open(test_log_path, "w") as f:
            f.write("test content")
        with open(test_txt_path, "w") as f:
            f.write("test content")

        # Check matching using the is_ignored helper function
        self.assertTrue(self._is_file_ignored(test_log_path, self.nested_dir, result))
        self.assertFalse(self._is_file_ignored(test_txt_path, self.nested_dir, result))

    def test_parent_gitignore(self):
        # Create a .gitignore in a parent directory
        gitignore_path = os.path.join(self.temp_dir, ".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.tmp\n")

        result = load_gitignore_for_directory(self.nested_dir)

        # Create test files
        test_tmp_path = os.path.join(self.nested_dir, "test.tmp")
        test_txt_path = os.path.join(self.nested_dir, "test.txt")
        with open(test_tmp_path, "w") as f:
            f.write("test content")
        with open(test_txt_path, "w") as f:
            f.write("test content")

        # Verify pattern matching
        self.assertTrue(self._is_file_ignored(test_tmp_path, self.nested_dir, result))
        self.assertFalse(self._is_file_ignored(test_txt_path, self.nested_dir, result))

    def test_multiple_gitignore_files(self):
        # Create .gitignore files at different levels
        root_gitignore = os.path.join(self.temp_dir, ".gitignore")
        with open(root_gitignore, "w") as f:
            f.write("*.tmp\n")

        sub_gitignore = os.path.join(self.sub_dir, ".gitignore")
        with open(sub_gitignore, "w") as f:
            f.write("*.log\n")

        nested_gitignore = os.path.join(self.nested_dir, ".gitignore")
        with open(nested_gitignore, "w") as f:
            f.write("*.cache\n")

        result = load_gitignore_for_directory(self.nested_dir)

        # Create test files
        test_tmp_path = os.path.join(self.nested_dir, "test.tmp")
        test_log_path = os.path.join(self.nested_dir, "test.log")
        test_cache_path = os.path.join(self.nested_dir, "test.cache")
        test_txt_path = os.path.join(self.nested_dir, "test.txt")

        for path in [test_tmp_path, test_log_path, test_cache_path, test_txt_path]:
            with open(path, "w") as f:
                f.write("test content")

        # Verify pattern matching
        self.assertTrue(self._is_file_ignored(test_tmp_path, self.nested_dir, result))
        self.assertTrue(self._is_file_ignored(test_log_path, self.nested_dir, result))
        self.assertTrue(self._is_file_ignored(test_cache_path, self.nested_dir, result))
        self.assertFalse(self._is_file_ignored(test_txt_path, self.nested_dir, result))

    def test_pattern_precedence(self):
        # Test that more specific patterns override parent patterns
        root_gitignore = os.path.join(self.temp_dir, ".gitignore")
        with open(root_gitignore, "w") as f:
            f.write("*.txt\n")  # Ignore all .txt files

        nested_gitignore = os.path.join(self.nested_dir, ".gitignore")
        with open(nested_gitignore, "w") as f:
            f.write("!important.txt\n")  # But don't ignore important.txt

        result = load_gitignore_for_directory(self.nested_dir)

        # Create test files
        regular_txt_path = os.path.join(self.nested_dir, "regular.txt")
        important_txt_path = os.path.join(self.nested_dir, "important.txt")

        for path in [regular_txt_path, important_txt_path]:
            with open(path, "w") as f:
                f.write("test content")

        # Check precedence of rules
        self.assertTrue(
            self._is_file_ignored(regular_txt_path, self.nested_dir, result)
        )
        self.assertFalse(
            self._is_file_ignored(important_txt_path, self.nested_dir, result)
        )

    # Helper method to check if a file is ignored
    def _is_file_ignored(self, path, base_path, spec):
        relative_path = os.path.relpath(path, base_path)
        return spec.match_file(relative_path) if spec else False


if __name__ == "__main__":
    unittest.main()
