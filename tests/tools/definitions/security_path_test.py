import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from streetrace.tools.definitions.list_directory import list_directory


class TestSecurityPath(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory structure for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.work_dir = self.temp_dir / "root"
        self.allowed_dir = self.work_dir / "allowed"
        self.allowed_file = self.allowed_dir / "allowed_file.txt"
        self.sibling_dir = self.temp_dir / "sibling"

        # Create directory structure
        for d in [self.work_dir, self.allowed_dir, self.sibling_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Create some files
        self.allowed_file.write_text("allowed content")
        (self.sibling_dir / "sibling_file.txt").write_text("sibling content")

    def tearDown(self) -> None:
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_valid_path(self) -> None:
        """Test accessing a valid path within the root path."""
        # This should work - allowed_dir is within work_dir
        result = list_directory(str(self.allowed_dir), self.work_dir)

        # Paths should be relative to work_dir
        expected_file_path = self.allowed_file.relative_to(self.work_dir)
        assert len(result["dirs"]) == 0
        assert len(result["files"]) == 1
        assert result["files"][0] == str(expected_file_path)

    def test_same_as_work_dir(self) -> None:
        """Test accessing the root path itself."""
        # This should work - path is the same as work_dir
        result = list_directory(self.work_dir, self.work_dir)

        # Paths should be relative to work_dir
        expected_dir_path = self.allowed_dir.relative_to(self.work_dir)
        assert len(result["files"]) == 0  # No files directly in work_dir
        assert len(result["dirs"]) == 1
        assert result["dirs"][0] == str(expected_dir_path)

    def test_directory_traversal(self) -> None:
        """Test that directory traversal is prevented."""
        # Try to access a sibling directory (outside work_dir)
        with pytest.raises(ValueError) as context:
            list_directory(str(self.sibling_dir), self.work_dir)

        # Check that the error message is helpful
        assert "Security error" in str(context.value)
        assert "outside the allowed working directory" in str(context.value)

    def test_parent_directory_traversal(self) -> None:
        """Test that parent directory traversal is prevented."""
        # Try to access parent directory using ..
        parent_path = self.work_dir / ".."

        with pytest.raises(ValueError) as context:
            list_directory(str(parent_path), self.work_dir)

        assert "Security error" in str(context.value)
        assert "outside the allowed working directory" in str(context.value)

    def test_absolute_path_traversal(self) -> None:
        """Test that absolute path outside root is prevented."""
        # Try to access an absolute path outside root
        with pytest.raises(ValueError) as context:
            # Use /tmp or another guaranteed absolute path outside the test temp dir
            list_directory("/tmp", self.work_dir)  # noqa: S108

        assert "Security error" in str(context.value)
        assert "outside the allowed working directory" in str(context.value)


if __name__ == "__main__":
    unittest.main()
