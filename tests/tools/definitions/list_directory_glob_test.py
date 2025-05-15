import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from streetrace.tools.definitions.list_directory import list_directory


class TestReadDirectoryStructureGlob(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory structure for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.temp_subdir = self.temp_dir / "subdir"
        self.temp_nested_subdir = self.temp_subdir / "nested"

        # Create directories
        self.temp_subdir.mkdir(exist_ok=True)
        self.temp_nested_subdir.mkdir(exist_ok=True)

        # Create files at different levels
        self.root_file1 = self.temp_dir / "root_file1.txt"
        self.root_file2 = self.temp_dir / "root_file2.log"
        self.subdir_file = self.temp_subdir / "subdir_file.txt"
        self.nested_file = self.temp_nested_subdir / "nested_file.txt"

        # Write some content to the files
        for file_path in [
            self.root_file1,
            self.root_file2,
            self.subdir_file,
            self.nested_file,
        ]:
            file_path.write_text("test content")

    def tearDown(self) -> None:
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_non_recursive_listing(self) -> None:
        """Test that the function only lists current directory level."""
        # Use the same path for both parameters to pass security check
        result = list_directory(self.temp_dir, self.temp_dir)

        # Should contain both files in the root and the subdir
        expected_files = [
            self.root_file1.name,
            self.root_file2.name,
        ]
        expected_dirs = [self.temp_subdir.name]

        # Sort expected results for comparison
        expected_files.sort()
        expected_dirs.sort()

        # Convert actual results to basenames for comparison
        actual_files = [Path(f).name for f in result["files"]]
        actual_dirs = [Path(d).name for d in result["dirs"]]
        actual_files.sort()
        actual_dirs.sort()

        assert expected_files == actual_files
        assert expected_dirs == actual_dirs

        # Files from nested directories should not be included
        nested_basenames = [
            self.nested_file.name,
            self.subdir_file.name,
        ]
        for basename in nested_basenames:
            assert basename not in actual_files

    def test_relative_paths(self) -> None:
        """Test that paths are returned relative to work_dir."""
        # Set work_dir to parent of temp_dir
        parent_dir = self.temp_dir.parent
        result = list_directory(self.temp_dir, parent_dir)

        # All paths should be relative to parent_dir
        temp_dir_basename = self.temp_dir.name

        for file_path in result["files"]:
            assert file_path.startswith(temp_dir_basename + os.sep)

        for dir_path in result["dirs"]:
            assert dir_path.startswith(temp_dir_basename + os.sep)

    def test_subdirectory_listing(self) -> None:
        """Test listing a subdirectory."""
        # Use temp_dir as work_dir, list temp_subdir
        result = list_directory(str(self.temp_subdir), self.temp_dir)

        # Paths should be relative to temp_dir
        expected_dir_rel = str(
            Path(self.temp_subdir.name) / self.temp_nested_subdir.name,
        )
        expected_file_rel = str(
            Path(self.temp_subdir.name) / self.subdir_file.name,
        )

        assert len(result["dirs"]) == 1
        assert len(result["files"]) == 1

        assert result["dirs"][0] == expected_dir_rel
        assert result["files"][0] == expected_file_rel

    def test_gitignore_respect(self) -> None:
        """Test that gitignore patterns are respected."""
        # Create a .gitignore file that ignores .log files
        gitignore_path = self.temp_dir / ".gitignore"
        gitignore_path.write_text("*.log\n")

        # Use the same path for both parameters to pass security check
        result = list_directory(self.temp_dir, self.temp_dir)

        # .log files should be excluded
        for file_path in result["files"]:
            assert not file_path.endswith(".log")

        # But .txt files should be included
        txt_files = [f for f in result["files"] if f.endswith(".txt")]
        assert len(txt_files) > 0
        assert self.root_file1.name in txt_files

    def test_security_check(self) -> None:
        """Test that security checks prevent directory traversal."""
        # Attempt to access parent directory
        with pytest.raises(ValueError) as context:
            list_directory(str(self.temp_dir.parent), self.temp_dir)

        assert "Security error" in str(context.value)


if __name__ == "__main__":
    unittest.main()
