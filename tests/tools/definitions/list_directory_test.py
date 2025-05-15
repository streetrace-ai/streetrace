import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from streetrace.tools.definitions.list_directory import list_directory


class TestDirectoryStructureTool(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory structure for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.parent_dir = self.temp_dir.parent  # Store parent for work_dir tests
        self.temp_dir_basename = self.temp_dir.name

        # Create a test directory structure
        self.create_test_directory_structure()

    def tearDown(self) -> None:
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def create_test_directory_structure(self) -> None:
        """Create a simple test directory structure."""
        # Create subdirectories
        self.sub_dir_name = "sub_dir"
        sub_dir = self.temp_dir / self.sub_dir_name
        sub_dir.mkdir(parents=True, exist_ok=True)

        # Create files
        self.root_file_name = "root_file.txt"
        self.sub_file_name = "sub_file.txt"
        (self.temp_dir / self.root_file_name).write_text("content")
        (sub_dir / self.sub_file_name).write_text("content")

    def test_specific_directory(self) -> None:
        """Test that tool works with a specified directory path relative to parent work_dir."""
        # Create a file in current directory to verify we're not scanning it
        current_marker = Path("current_dir_marker.txt")
        current_marker.write_text("marker")

        try:
            # Call the tool with temp directory path and set work_dir to its parent
            result = list_directory(str(self.temp_dir), self.parent_dir)

            # Verify the structure paths are relative to parent_dir
            expected_file_path = str(Path(self.temp_dir_basename) / self.root_file_name)
            expected_dir_path = str(Path(self.temp_dir_basename) / self.sub_dir_name)

            assert expected_file_path in result["files"]
            assert expected_dir_path in result["dirs"]

            # Verify the current directory file isn't in the result
            assert current_marker.name not in result["files"]
            assert not any(
                current_marker.name in p for p in result["files"]
            )  # Double check

        finally:
            # Remove the marker file
            if current_marker.exists():
                current_marker.unlink()

    def test_subdirectory_path(self) -> None:
        """Test that tool works with a subdirectory path relative to its parent work_dir."""
        sub_dir_path = self.temp_dir / self.sub_dir_name

        # Call the tool with subdirectory path, using temp_dir as work_dir
        result = list_directory(str(sub_dir_path), self.temp_dir)

        # Verify the structure only includes the subdirectory contents, relative to temp_dir
        assert len(result["dirs"]) == 0  # No sub-sub-directories
        assert len(result["files"]) == 1
        assert str(Path(self.sub_dir_name) / self.sub_file_name) == result["files"][0]

        # Verify root directory file isn't included
        assert self.root_file_name not in result["files"]

    def test_with_explicit_work_dir(self) -> None:
        """Test that tool respects the work_dir restriction."""
        # Set work_dir explicitly to the temp directory
        result = list_directory(self.temp_dir, self.temp_dir)

        # Verify the structure - paths relative to temp_dir
        assert self.root_file_name in result["files"]
        assert self.sub_dir_name in result["dirs"]
        assert self.sub_file_name not in result["files"]  # Not in root listing

        # Now try to access a path outside of work_dir (parent dir)
        with pytest.raises(ValueError) as context:
            list_directory(str(self.parent_dir), self.temp_dir)

        assert "Security error" in str(context.value)
        # Updated assertion message
        assert "outside the allowed working directory" in str(context.value)


if __name__ == "__main__":
    unittest.main()
