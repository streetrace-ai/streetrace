import os
import shutil
import tempfile
import unittest

import pytest

from streetrace.tools.read_directory_structure import read_directory_structure


class TestReadDirectoryStructureGlob(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_subdir = os.path.join(self.temp_dir, "subdir")
        self.temp_nested_subdir = os.path.join(self.temp_subdir, "nested")

        # Create directories
        os.makedirs(self.temp_subdir, exist_ok=True)
        os.makedirs(self.temp_nested_subdir, exist_ok=True)

        # Create files at different levels
        self.root_file1 = os.path.join(self.temp_dir, "root_file1.txt")
        self.root_file2 = os.path.join(self.temp_dir, "root_file2.log")
        self.subdir_file = os.path.join(self.temp_subdir, "subdir_file.txt")
        self.nested_file = os.path.join(self.temp_nested_subdir, "nested_file.txt")

        # Write some content to the files
        for file_path in [
            self.root_file1,
            self.root_file2,
            self.subdir_file,
            self.nested_file,
        ]:
            with open(file_path, "w") as f:
                f.write("test content")

    def tearDown(self) -> None:
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_non_recursive_listing(self) -> None:
        """Test that the function only lists current directory level."""
        # Use the same path for both parameters to pass security check
        result_tuple = read_directory_structure(self.temp_dir, self.temp_dir)
        result = result_tuple[0]  # Access the dictionary part

        # Should contain both files in the root and the subdir
        expected_files = [
            os.path.basename(self.root_file1),
            os.path.basename(self.root_file2),
        ]
        expected_dirs = [os.path.basename(self.temp_subdir)]

        # Sort expected results for comparison
        expected_files.sort()
        expected_dirs.sort()

        # Convert actual results to basenames for comparison
        actual_files = [os.path.basename(f) for f in result["files"]]
        actual_dirs = [os.path.basename(d) for d in result["dirs"]]
        actual_files.sort()
        actual_dirs.sort()

        assert expected_files == actual_files
        assert expected_dirs == actual_dirs

        # Files from nested directories should not be included
        nested_basenames = [
            os.path.basename(self.nested_file),
            os.path.basename(self.subdir_file),
        ]
        for basename in nested_basenames:
            assert basename not in actual_files

    def test_relative_paths(self) -> None:
        """Test that paths are returned relative to work_dir."""
        # Set work_dir to parent of temp_dir
        parent_dir = os.path.dirname(self.temp_dir)
        result_tuple = read_directory_structure(self.temp_dir, parent_dir)
        result = result_tuple[0]  # Access the dictionary part

        # All paths should be relative to parent_dir
        temp_dir_basename = os.path.basename(self.temp_dir)

        for file_path in result["files"]:
            assert file_path.startswith(temp_dir_basename + os.sep)

        for dir_path in result["dirs"]:
            assert dir_path.startswith(temp_dir_basename + os.sep)

    def test_subdirectory_listing(self) -> None:
        """Test listing a subdirectory."""
        # Use temp_dir as work_dir, list temp_subdir
        result_tuple = read_directory_structure(self.temp_subdir, self.temp_dir)
        result = result_tuple[0]  # Access the dictionary part

        # Paths should be relative to temp_dir
        expected_dir_rel = os.path.join(
            os.path.basename(self.temp_subdir),
            os.path.basename(self.temp_nested_subdir),
        )
        expected_file_rel = os.path.join(
            os.path.basename(self.temp_subdir),
            os.path.basename(self.subdir_file),
        )

        assert len(result["dirs"]) == 1
        assert len(result["files"]) == 1

        assert result["dirs"][0] == expected_dir_rel
        assert result["files"][0] == expected_file_rel

    def test_gitignore_respect(self) -> None:
        """Test that gitignore patterns are respected."""
        # Create a .gitignore file that ignores .log files
        gitignore_path = os.path.join(self.temp_dir, ".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.log\n")

        # Use the same path for both parameters to pass security check
        result_tuple = read_directory_structure(self.temp_dir, self.temp_dir)
        result = result_tuple[0]  # Access the dictionary part

        # .log files should be excluded
        for file_path in result["files"]:
            assert not file_path.endswith(".log")

        # But .txt files should be included
        txt_files = [f for f in result["files"] if f.endswith(".txt")]
        assert len(txt_files) > 0
        assert os.path.basename(self.root_file1) in txt_files

    def test_security_check(self) -> None:
        """Test that security checks prevent directory traversal."""
        # Attempt to access parent directory
        with pytest.raises(ValueError) as context:
            read_directory_structure(os.path.dirname(self.temp_dir), self.temp_dir)

        assert "Security error" in str(context.value)


if __name__ == "__main__":
    unittest.main()
