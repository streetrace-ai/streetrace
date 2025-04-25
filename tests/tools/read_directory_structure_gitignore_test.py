import os
import shutil
import tempfile
import unittest

from streetrace.tools.read_directory_structure import read_directory_structure


class TestReadDirectoryStructure(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.mkdtemp()

        # Create base structure
        self.create_test_directory_structure()

    def tearDown(self) -> None:
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def create_test_directory_structure(self) -> None:
        """Create a test directory structure with various files and subdirectories."""
        # Create directories
        dir1 = os.path.join(self.temp_dir, "dir1")
        dir2 = os.path.join(self.temp_dir, "dir2")
        subdir1 = os.path.join(dir1, "subdir1")
        subdir2 = os.path.join(dir2, "subdir2")

        for d in [dir1, dir2, subdir1, subdir2]:
            os.makedirs(d, exist_ok=True)

        # Create files in root
        with open(os.path.join(self.temp_dir, "root_file.txt"), "w") as f:
            f.write("content")

        with open(os.path.join(self.temp_dir, "root_file.log"), "w") as f:
            f.write("log content")

        # Create files in dir1
        with open(os.path.join(dir1, "dir1_file.txt"), "w") as f:
            f.write("content")

        with open(os.path.join(dir1, "dir1_file.log"), "w") as f:
            f.write("log content")

        # Create files in subdir1
        with open(os.path.join(subdir1, "subdir1_file.txt"), "w") as f:
            f.write("content")

        with open(os.path.join(subdir1, "subdir1_file.tmp"), "w") as f:
            f.write("tmp content")

        # Create files in dir2
        with open(os.path.join(dir2, "dir2_file.txt"), "w") as f:
            f.write("content")

        with open(os.path.join(dir2, "dir2_file.log"), "w") as f:
            f.write("log content")

        # Create files in subdir2
        with open(os.path.join(subdir2, "subdir2_file.txt"), "w") as f:
            f.write("content")

        with open(os.path.join(subdir2, "subdir2_file.cache"), "w") as f:
            f.write("cache content")

    def test_no_gitignore(self) -> None:
        """Test reading directory structure without any gitignore files."""
        result_tuple = read_directory_structure(
            self.temp_dir,
            os.path.dirname(self.temp_dir),
        )
        result = result_tuple[0]  # Access the dictionary part

        # Get the base name of the temp directory for constructing relative paths
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify structure
        # Check root directories and files (relative to parent of temp_dir)
        assert os.path.join(temp_dir_basename, "dir1") in result["dirs"]
        assert os.path.join(temp_dir_basename, "dir2") in result["dirs"]
        assert os.path.join(temp_dir_basename, "root_file.txt") in result["files"]
        assert os.path.join(temp_dir_basename, "root_file.log") in result["files"]

        # Since it's not recursive, subdir files shouldn't be listed directly
        assert (
            os.path.join(temp_dir_basename, "dir1", "subdir1_file.txt")
            not in result["files"]
        )

    def test_root_gitignore(self) -> None:
        """Test with a gitignore in the root that ignores all .log files."""
        # Create root gitignore
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("*.log\n")

        result_tuple = read_directory_structure(
            self.temp_dir,
            os.path.dirname(self.temp_dir),
        )
        result = result_tuple[0]  # Access the dictionary part
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify structure - log files should be ignored
        assert os.path.join(temp_dir_basename, "root_file.log") not in result["files"]
        assert os.path.join(temp_dir_basename, "root_file.txt") in result["files"]

        # Check dir1 and dir2 are still present
        assert os.path.join(temp_dir_basename, "dir1") in result["dirs"]
        assert os.path.join(temp_dir_basename, "dir2") in result["dirs"]

    def test_nested_gitignore(self) -> None:
        """Test with gitignore files at different levels."""
        # Create root gitignore - ignore logs
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("*.log\n")

        # Create dir1 gitignore - ignore tmp files (This won't affect root listing)
        with open(os.path.join(self.temp_dir, "dir1", ".gitignore"), "w") as f:
            f.write("*.tmp\n")

        # Create dir2 gitignore - ignore cache files (This won't affect root listing)
        with open(os.path.join(self.temp_dir, "dir2", ".gitignore"), "w") as f:
            f.write("*.cache\n")

        result_tuple = read_directory_structure(
            self.temp_dir,
            os.path.dirname(self.temp_dir),
        )
        result = result_tuple[0]  # Access the dictionary part
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify log files are ignored at the root level
        assert os.path.join(temp_dir_basename, "root_file.log") not in result["files"]
        assert os.path.join(temp_dir_basename, "root_file.txt") in result["files"]
        # Nested gitignores don't affect the listing of the parent directory itself
        assert os.path.join(temp_dir_basename, "dir1") in result["dirs"]
        assert os.path.join(temp_dir_basename, "dir2") in result["dirs"]

    def test_ignore_directory(self) -> None:
        """Test ignoring entire directories."""
        # Create root gitignore that ignores dir2
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("dir2/\n")

        result_tuple = read_directory_structure(
            self.temp_dir,
            os.path.dirname(self.temp_dir),
        )
        result = result_tuple[0]  # Access the dictionary part
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify dir2 is not included
        assert os.path.join(temp_dir_basename, "dir1") in result["dirs"]
        assert os.path.join(temp_dir_basename, "dir2") not in result["dirs"]

        # Verify dir2 file isn't listed either
        assert (
            os.path.join(temp_dir_basename, "dir2", "dir2_file.txt")
            not in result["files"]
        )

    def test_pattern_override(self) -> None:
        """Test that patterns can be overridden in nested directories (won't affect root listing)."""
        # Create root gitignore - ignore all txt files
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("*.txt\n")

        # Create dir1 gitignore - but keep specific txt files (doesn't affect root listing)
        with open(os.path.join(self.temp_dir, "dir1", ".gitignore"), "w") as f:
            f.write("!dir1_file.txt\n")  # Don't ignore this specific txt

        result_tuple = read_directory_structure(
            self.temp_dir,
            os.path.dirname(self.temp_dir),
        )
        result = result_tuple[0]  # Access the dictionary part
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify root txt file is ignored
        assert os.path.join(temp_dir_basename, "root_file.txt") not in result["files"]
        assert os.path.join(temp_dir_basename, "root_file.log") in result["files"]
        # Dirs themselves aren't ignored by *.txt
        assert os.path.join(temp_dir_basename, "dir1") in result["dirs"]
        assert os.path.join(temp_dir_basename, "dir2") in result["dirs"]


if __name__ == "__main__":
    unittest.main()
