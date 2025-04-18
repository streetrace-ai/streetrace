import os
import shutil
import tempfile
import unittest

from streetrace.tools.read_directory_structure import read_directory_structure


class TestReadDirectoryStructure(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.mkdtemp()

        # Create base structure
        self.create_test_directory_structure()

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def create_test_directory_structure(self):
        """Create a test directory structure with various files and subdirectories"""
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

    def test_no_gitignore(self):
        """Test reading directory structure without any gitignore files"""
        result_tuple = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))
        result = result_tuple[0] # Access the dictionary part

        # Get the base name of the temp directory for constructing relative paths
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify structure
        # Check root directories and files (relative to parent of temp_dir)
        self.assertIn(os.path.join(temp_dir_basename, "dir1"), result["dirs"])
        self.assertIn(os.path.join(temp_dir_basename, "dir2"), result["dirs"])
        self.assertIn(
            os.path.join(temp_dir_basename, "root_file.txt"), result["files"]
        )
        self.assertIn(
            os.path.join(temp_dir_basename, "root_file.log"), result["files"]
        )

        # Since it's not recursive, subdir files shouldn't be listed directly
        self.assertNotIn(
            os.path.join(temp_dir_basename, "dir1", "subdir1_file.txt"), result["files"]
        )

    def test_root_gitignore(self):
        """Test with a gitignore in the root that ignores all .log files"""
        # Create root gitignore
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("*.log\n")

        result_tuple = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))
        result = result_tuple[0] # Access the dictionary part
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify structure - log files should be ignored
        self.assertNotIn(
            os.path.join(temp_dir_basename, "root_file.log"), result["files"]
        )
        self.assertIn(
            os.path.join(temp_dir_basename, "root_file.txt"), result["files"]
        )

        # Check dir1 and dir2 are still present
        self.assertIn(os.path.join(temp_dir_basename, "dir1"), result["dirs"])
        self.assertIn(os.path.join(temp_dir_basename, "dir2"), result["dirs"])

    def test_nested_gitignore(self):
        """Test with gitignore files at different levels"""
        # Create root gitignore - ignore logs
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("*.log\n")

        # Create dir1 gitignore - ignore tmp files (This won't affect root listing)
        with open(os.path.join(self.temp_dir, "dir1", ".gitignore"), "w") as f:
            f.write("*.tmp\n")

        # Create dir2 gitignore - ignore cache files (This won't affect root listing)
        with open(os.path.join(self.temp_dir, "dir2", ".gitignore"), "w") as f:
            f.write("*.cache\n")

        result_tuple = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))
        result = result_tuple[0] # Access the dictionary part
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify log files are ignored at the root level
        self.assertNotIn(
            os.path.join(temp_dir_basename, "root_file.log"), result["files"]
        )
        self.assertIn(
            os.path.join(temp_dir_basename, "root_file.txt"), result["files"]
        )
        # Nested gitignores don't affect the listing of the parent directory itself
        self.assertIn(os.path.join(temp_dir_basename, "dir1"), result["dirs"])
        self.assertIn(os.path.join(temp_dir_basename, "dir2"), result["dirs"])

    def test_ignore_directory(self):
        """Test ignoring entire directories"""
        # Create root gitignore that ignores dir2
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("dir2/\n")

        result_tuple = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))
        result = result_tuple[0] # Access the dictionary part
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify dir2 is not included
        self.assertIn(os.path.join(temp_dir_basename, "dir1"), result["dirs"])
        self.assertNotIn(os.path.join(temp_dir_basename, "dir2"), result["dirs"])

        # Verify dir2 file isn't listed either
        self.assertNotIn(
            os.path.join(temp_dir_basename, "dir2", "dir2_file.txt"), result["files"]
        )

    def test_pattern_override(self):
        """Test that patterns can be overridden in nested directories (won't affect root listing)"""
        # Create root gitignore - ignore all txt files
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("*.txt\n")

        # Create dir1 gitignore - but keep specific txt files (doesn't affect root listing)
        with open(os.path.join(self.temp_dir, "dir1", ".gitignore"), "w") as f:
            f.write("!dir1_file.txt\n")  # Don't ignore this specific txt

        result_tuple = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))
        result = result_tuple[0] # Access the dictionary part
        temp_dir_basename = os.path.basename(self.temp_dir)

        # Verify root txt file is ignored
        self.assertNotIn(
            os.path.join(temp_dir_basename, "root_file.txt"), result["files"]
        )
        self.assertIn(
             os.path.join(temp_dir_basename, "root_file.log"), result["files"]
        )
        # Dirs themselves aren't ignored by *.txt
        self.assertIn(os.path.join(temp_dir_basename, "dir1"), result["dirs"])
        self.assertIn(os.path.join(temp_dir_basename, "dir2"), result["dirs"])


if __name__ == "__main__":
    unittest.main()
