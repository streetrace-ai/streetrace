import shutil
import tempfile
import unittest
from pathlib import Path

import pathspec

from streetrace.tools.definitions.list_directory import (
    load_gitignore_for_directory,
)


class TestLoadGitignore(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory structure for testing
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create nested directory structure
        self.sub_dir = self.temp_dir / "sub_dir"
        self.nested_dir = self.sub_dir / "nested_dir"
        self.nested_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_no_gitignore(self) -> None:
        # Test when no .gitignore files exist
        result = load_gitignore_for_directory(self.nested_dir)
        assert result is not None
        assert len(result.patterns) == 0

    def test_single_gitignore(self) -> None:
        # Create a .gitignore file in the nested directory
        gitignore_path = self.nested_dir / ".gitignore"
        gitignore_path.write_text("*.log\n")

        result = load_gitignore_for_directory(self.nested_dir)

        # Verify the result is a PathSpec
        assert isinstance(result, pathspec.PathSpec)

        # Create a test file to verify pattern matching
        test_log_path = self.nested_dir / "test.log"
        test_txt_path = self.nested_dir / "test.txt"
        test_log_path.write_text("test content")
        test_txt_path.write_text("test content")

        # Check matching using the is_ignored helper function
        assert self._is_file_ignored(test_log_path, self.nested_dir, result)
        assert not self._is_file_ignored(test_txt_path, self.nested_dir, result)

    def test_parent_gitignore(self) -> None:
        # Create a .gitignore in a parent directory
        gitignore_path = self.temp_dir / ".gitignore"
        gitignore_path.write_text("*.tmp\n")

        result = load_gitignore_for_directory(self.nested_dir)

        # Create test files
        test_tmp_path = self.nested_dir / "test.tmp"
        test_txt_path = self.nested_dir / "test.txt"
        test_tmp_path.write_text("test content")
        test_txt_path.write_text("test content")

        # Verify pattern matching
        assert self._is_file_ignored(test_tmp_path, self.nested_dir, result)
        assert not self._is_file_ignored(test_txt_path, self.nested_dir, result)

    def test_multiple_gitignore_files(self) -> None:
        # Create .gitignore files at different levels
        root_gitignore = self.temp_dir / ".gitignore"
        root_gitignore.write_text("*.tmp\n")

        sub_gitignore = self.sub_dir / ".gitignore"
        sub_gitignore.write_text("*.log\n")

        nested_gitignore = self.nested_dir / ".gitignore"
        nested_gitignore.write_text("*.cache\n")

        result = load_gitignore_for_directory(self.nested_dir)

        # Create test files
        test_tmp_path = self.nested_dir / "test.tmp"
        test_log_path = self.nested_dir / "test.log"
        test_cache_path = self.nested_dir / "test.cache"
        test_txt_path = self.nested_dir / "test.txt"

        for path in [test_tmp_path, test_log_path, test_cache_path, test_txt_path]:
            path.write_text("test content")

        # Verify pattern matching
        assert self._is_file_ignored(test_tmp_path, self.nested_dir, result)
        assert self._is_file_ignored(test_log_path, self.nested_dir, result)
        assert self._is_file_ignored(test_cache_path, self.nested_dir, result)
        assert not self._is_file_ignored(test_txt_path, self.nested_dir, result)

    def test_pattern_precedence(self) -> None:
        # Test that more specific patterns override parent patterns
        root_gitignore = self.temp_dir / ".gitignore"
        root_gitignore.write_text("*.txt\n")  # Ignore all .txt files

        nested_gitignore = self.nested_dir / ".gitignore"
        nested_gitignore.write_text(
            "!important.txt\n",
        )  # But don't ignore important.txt

        result = load_gitignore_for_directory(self.nested_dir)

        # Create test files
        regular_txt_path = self.nested_dir / "regular.txt"
        important_txt_path = self.nested_dir / "important.txt"

        for path in [regular_txt_path, important_txt_path]:
            path.write_text("test content")

        # Check precedence of rules
        assert self._is_file_ignored(regular_txt_path, self.nested_dir, result)
        assert not self._is_file_ignored(important_txt_path, self.nested_dir, result)

    # Helper method to check if a file is ignored
    def _is_file_ignored(
        self,
        path: Path,
        base_path: Path,
        spec: pathspec.PathSpec,
    ) -> bool:
        relative_path = path.relative_to(base_path)
        return spec.match_file(str(relative_path)) if spec else False


if __name__ == "__main__":
    unittest.main()
