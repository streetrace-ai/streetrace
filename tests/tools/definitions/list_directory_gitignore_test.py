import shutil
import tempfile
import unittest
from pathlib import Path

from streetrace.tools.definitions.list_directory import (
    list_directory,
)


class TestReadDirectoryStructure(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory structure for testing
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create base structure
        self.create_test_directory_structure()

    def tearDown(self) -> None:
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def create_test_directory_structure(self) -> None:
        """Create a test directory structure with various files and subdirectories."""
        # Create directories
        dir1 = self.temp_dir / "dir1"
        dir2 = self.temp_dir / "dir2"
        subdir1 = dir1 / "subdir1"
        subdir2 = dir2 / "subdir2"

        for d in [dir1, dir2, subdir1, subdir2]:
            d.mkdir(parents=True, exist_ok=True)

        # Create files in root
        (self.temp_dir / "root_file.txt").write_text("content")
        (self.temp_dir / "root_file.log").write_text("log content")

        # Create files in dir1
        (dir1 / "dir1_file.txt").write_text("content")
        (dir1 / "dir1_file.log").write_text("log content")

        # Create files in subdir1
        (subdir1 / "subdir1_file.txt").write_text("content")
        (subdir1 / "subdir1_file.tmp").write_text("tmp content")

        # Create files in dir2
        (dir2 / "dir2_file.txt").write_text("content")
        (dir2 / "dir2_file.log").write_text("log content")

        # Create files in subdir2
        (subdir2 / "subdir2_file.txt").write_text("content")
        (subdir2 / "subdir2_file.cache").write_text("cache content")

    def test_no_gitignore(self) -> None:
        """Test reading directory structure without any gitignore files."""
        result = list_directory(
            str(self.temp_dir),
            self.temp_dir.parent,
        )

        # Get the base name of the temp directory for constructing relative paths
        temp_dir_basename = self.temp_dir.name

        # Verify structure
        # Check root directories and files (relative to parent of temp_dir)
        assert str(Path(temp_dir_basename) / "dir1") in result["dirs"]
        assert str(Path(temp_dir_basename) / "dir2") in result["dirs"]
        assert str(Path(temp_dir_basename) / "root_file.txt") in result["files"]
        assert str(Path(temp_dir_basename) / "root_file.log") in result["files"]

        # Since it's not recursive, subdir files shouldn't be listed directly
        assert (
            str(Path(temp_dir_basename) / "dir1" / "subdir1_file.txt")
            not in result["files"]
        )

    def test_root_gitignore(self) -> None:
        """Test with a gitignore in the root that ignores all .log files."""
        # Create root gitignore
        (self.temp_dir / ".gitignore").write_text("*.log\n")

        result = list_directory(
            str(self.temp_dir),
            self.temp_dir.parent,
        )
        temp_dir_basename = self.temp_dir.name

        # Verify structure - log files should be ignored
        assert str(Path(temp_dir_basename) / "root_file.log") not in result["files"]
        assert str(Path(temp_dir_basename) / "root_file.txt") in result["files"]

        # Check dir1 and dir2 are still present
        assert str(Path(temp_dir_basename) / "dir1") in result["dirs"]
        assert str(Path(temp_dir_basename) / "dir2") in result["dirs"]

    def test_nested_gitignore(self) -> None:
        """Test with gitignore files at different levels."""
        # Create root gitignore - ignore logs
        (self.temp_dir / ".gitignore").write_text("*.log\n")

        # Create dir1 gitignore - ignore tmp files (This won't affect root listing)
        (self.temp_dir / "dir1" / ".gitignore").write_text("*.tmp\n")

        # Create dir2 gitignore - ignore cache files (This won't affect root listing)
        (self.temp_dir / "dir2" / ".gitignore").write_text("*.cache\n")

        result = list_directory(
            str(self.temp_dir),
            self.temp_dir.parent,
        )
        temp_dir_basename = self.temp_dir.name

        # Verify log files are ignored at the root level
        assert str(Path(temp_dir_basename) / "root_file.log") not in result["files"]
        assert str(Path(temp_dir_basename) / "root_file.txt") in result["files"]
        # Nested gitignores don't affect the listing of the parent directory itself
        assert str(Path(temp_dir_basename) / "dir1") in result["dirs"]
        assert str(Path(temp_dir_basename) / "dir2") in result["dirs"]

    def test_ignore_directory(self) -> None:
        """Test ignoring entire directories."""
        # Create root gitignore that ignores dir2
        (self.temp_dir / ".gitignore").write_text("dir2/\n")

        result = list_directory(
            str(self.temp_dir),
            self.temp_dir.parent,
        )
        temp_dir_basename = self.temp_dir.name

        # Verify dir2 is not included
        assert str(Path(temp_dir_basename) / "dir1") in result["dirs"]
        assert str(Path(temp_dir_basename) / "dir2") not in result["dirs"]

        # Verify dir2 file isn't listed either
        assert (
            str(Path(temp_dir_basename) / "dir2" / "dir2_file.txt")
            not in result["files"]
        )

    def test_pattern_override(self) -> None:
        """Test that patterns can be overridden in nested directories (won't affect root listing)."""
        # Create root gitignore - ignore all txt files
        (self.temp_dir / ".gitignore").write_text("*.txt\n")

        # Create dir1 gitignore - but keep specific txt files (doesn't affect root listing)
        (self.temp_dir / "dir1" / ".gitignore").write_text(
            "!dir1_file.txt\n",
        )  # Don't ignore this specific txt

        result = list_directory(
            str(self.temp_dir),
            self.temp_dir.parent,
        )
        temp_dir_basename = self.temp_dir.name

        # Verify root txt file is ignored
        assert str(Path(temp_dir_basename) / "root_file.txt") not in result["files"]
        assert str(Path(temp_dir_basename) / "root_file.log") in result["files"]
        # Dirs themselves aren't ignored by *.txt
        assert str(Path(temp_dir_basename) / "dir1") in result["dirs"]
        assert str(Path(temp_dir_basename) / "dir2") in result["dirs"]


if __name__ == "__main__":
    unittest.main()
