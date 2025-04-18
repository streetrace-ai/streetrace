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
        self.allowed_file = os.path.join(self.allowed_dir, "allowed_file.txt")
        self.sibling_dir = os.path.join(self.temp_dir, "sibling")

        # Create directory structure
        for d in [self.work_dir, self.allowed_dir, self.sibling_dir]:
            os.makedirs(d, exist_ok=True)

        # Create some files
        with open(self.allowed_file, "w") as f:
            f.write("allowed content")

        with open(os.path.join(self.sibling_dir, "sibling_file.txt"), "w") as f:
            f.write("sibling content")

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_valid_path(self):
        """Test accessing a valid path within the root path"""
        # This should work - allowed_dir is within work_dir
        result_tuple = read_directory_structure(self.allowed_dir, self.work_dir)
        result = result_tuple[0] # Access the dictionary part

        # Paths should be relative to work_dir
        expected_file_path = os.path.relpath(self.allowed_file, self.work_dir)
        self.assertEqual(len(result["dirs"]), 0)
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(result["files"][0], expected_file_path)

    def test_same_as_work_dir(self):
        """Test accessing the root path itself"""
        # This should work - path is the same as work_dir
        result_tuple = read_directory_structure(self.work_dir, self.work_dir)
        result = result_tuple[0] # Access the dictionary part

        # Paths should be relative to work_dir
        expected_dir_path = os.path.relpath(self.allowed_dir, self.work_dir)
        self.assertEqual(len(result["files"]), 0) # No files directly in work_dir
        self.assertEqual(len(result["dirs"]), 1)
        self.assertEqual(result["dirs"][0], expected_dir_path)

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
        self.assertIn("outside the allowed root path", str(context.exception))

    def test_absolute_path_traversal(self):
        """Test that absolute path outside root is prevented"""
        # Try to access an absolute path outside root
        with self.assertRaises(ValueError) as context:
            # Use /tmp or another guaranteed absolute path outside the test temp dir
            read_directory_structure("/tmp", self.work_dir)

        self.assertIn("Security error", str(context.exception))
        self.assertIn("outside the allowed root path", str(context.exception))


if __name__ == "__main__":
    unittest.main()
