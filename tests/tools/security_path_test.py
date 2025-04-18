import json
import os
import shutil
import tempfile
import unittest

from streetrace.tools.read_directory_structure import read_directory_structure


class TestSecurityPath(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.mkdtemp()
        self.work_dir = os.path.join(self.temp_dir, "root")
        self.allowed_dir = os.path.join(self.work_dir, "allowed")
        self.sibling_dir = os.path.join(self.temp_dir, "sibling")

        # Create directory structure
        for d in [self.work_dir, self.allowed_dir, self.sibling_dir]:
            os.makedirs(d, exist_ok=True)

        # Create some files
        with open(os.path.join(self.allowed_dir, "allowed_file.txt"), "w") as f:
            f.write("allowed content")

        with open(os.path.join(self.sibling_dir, "sibling_file.txt"), "w") as f:
            f.write("sibling content")

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_valid_path(self):
        """Test accessing a valid path within the root path"""
        # This should work - allowed_dir is within work_dir
        result = read_directory_structure(self.allowed_dir, self.work_dir)
        self.assertIn("allowed/allowed_file.txt", result["files"])

    def test_same_as_work_dir(self):
        """Test accessing the root path itself"""
        # This should work - path is the same as work_dir
        result = read_directory_structure(self.work_dir, self.work_dir)
        self.assertIn("allowed", result["dirs"])

    def test_directory_traversal(self):
        """Test that directory traversal is prevented"""
        # Try to access a sibling directory (outside work_dir)
        with self.assertRaises(ValueError) as context:
            read_directory_structure(self.sibling_dir, self.work_dir)

        # Check that the error message is helpful
        self.assertIn("Security error", str(context.exception))
        self.assertIn("outside the allowed root path", str(context.exception))

    def test_parent_directory_traversal(self):
        """Test that parent directory traversal is prevented"""
        # Try to access parent directory using ..
        parent_path = os.path.join(self.work_dir, "..")

        with self.assertRaises(ValueError) as context:
            read_directory_structure(parent_path, self.work_dir)

        self.assertIn("Security error", str(context.exception))

    def test_absolute_path_traversal(self):
        """Test that absolute path outside root is prevented"""
        # Try to access an absolute path outside root
        with self.assertRaises(ValueError) as context:
            read_directory_structure("/tmp", self.work_dir)

        self.assertIn("Security error", str(context.exception))


if __name__ == "__main__":
    unittest.main()
