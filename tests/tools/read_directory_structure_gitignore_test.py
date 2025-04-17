import os
import shutil
import tempfile
import unittest

from tools.read_directory_structure import read_directory_structure


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
        result = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))

        # Verify structure
        self.assertIn(os.path.basename(self.temp_dir) + "/dir1", result["dirs"])
        self.assertIn(os.path.basename(self.temp_dir) + "/dir2", result["dirs"])
        self.assertIn(
            os.path.basename(self.temp_dir) + "/root_file.txt", result["files"]
        )
        self.assertIn(
            os.path.basename(self.temp_dir) + "/root_file.log", result["files"]
        )

        # Check dir1 contents
        self.assertIn(os.path.basename(self.temp_dir) + "/dir1", result["dirs"])

        # Check dir2 contents
        self.assertIn(os.path.basename(self.temp_dir) + "/dir2", result["dirs"])

    def test_root_gitignore(self):
        """Test with a gitignore in the root that ignores all .log files"""
        # Create root gitignore
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("*.log\n")

        result = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))

        # Verify structure - log files should be ignored
        self.assertNotIn(
            os.path.basename(self.temp_dir) + "/root_file.log", result["files"]
        )
        self.assertIn(
            os.path.basename(self.temp_dir) + "/root_file.txt", result["files"]
        )

        # Check dir1 contents - log files should be ignored
        self.assertIn(os.path.basename(self.temp_dir) + "/dir1", result["dirs"])

        # Check dir2 contents - log files should be ignored
        self.assertIn(os.path.basename(self.temp_dir) + "/dir2", result["dirs"])

    def test_nested_gitignore(self):
        """Test with gitignore files at different levels"""
        # Create root gitignore - ignore logs
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("*.log\n")

        # Create dir1 gitignore - ignore tmp files
        with open(os.path.join(self.temp_dir, "dir1", ".gitignore"), "w") as f:
            f.write("*.tmp\n")

        # Create dir2 gitignore - ignore cache files
        with open(os.path.join(self.temp_dir, "dir2", ".gitignore"), "w") as f:
            f.write("*.cache\n")

        result = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))

        # Verify log files are ignored everywhere
        self.assertNotIn("root_file.log", result["files"])

    def test_ignore_directory(self):
        """Test ignoring entire directories"""
        # Create root gitignore that ignores dir2
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("dir2/\n")

        result = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))

        # Verify dir2 is not included
        self.assertIn(os.path.basename(self.temp_dir) + "/dir1", result["dirs"])
        self.assertNotIn(os.path.basename(self.temp_dir) + "/dir2", result["dirs"])

        # Verify dir2 entries don't exist in the result
        self.assertNotIn("dir2", result)
        self.assertNotIn("dir2/subdir2", result)

    def test_pattern_override(self):
        """Test that patterns can be overridden in nested directories"""
        # Create root gitignore - ignore all txt files
        with open(os.path.join(self.temp_dir, ".gitignore"), "w") as f:
            f.write("*.txt\n")

        # Create dir1 gitignore - but keep specific txt files
        with open(os.path.join(self.temp_dir, "dir1", ".gitignore"), "w") as f:
            f.write("!dir1_file.txt\n")  # Don't ignore this specific txt

        result = read_directory_structure(self.temp_dir, os.path.dirname(self.temp_dir))

        # Verify txt files are ignored everywhere except in dir1
        self.assertNotIn("root_file.txt", result["files"])


if __name__ == "__main__":
    unittest.main()
