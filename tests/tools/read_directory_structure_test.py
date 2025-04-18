import os
import shutil
import tempfile
import unittest

from streetrace.tools.read_directory_structure import read_directory_structure


class TestDirectoryStructureTool(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.mkdtemp()
        self.parent_dir = os.path.dirname(self.temp_dir) # Store parent for work_dir tests
        self.temp_dir_basename = os.path.basename(self.temp_dir)

        # Create a test directory structure
        self.create_test_directory_structure()

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def create_test_directory_structure(self):
        """Create a simple test directory structure"""
        # Create subdirectories
        self.sub_dir_name = "sub_dir"
        sub_dir = os.path.join(self.temp_dir, self.sub_dir_name)
        os.makedirs(sub_dir, exist_ok=True)

        # Create files
        self.root_file_name = "root_file.txt"
        self.sub_file_name = "sub_file.txt"
        with open(os.path.join(self.temp_dir, self.root_file_name), "w") as f:
            f.write("content")

        with open(os.path.join(sub_dir, self.sub_file_name), "w") as f:
            f.write("content")

    def test_specific_directory(self):
        """Test that tool works with a specified directory path relative to parent work_dir"""
        # Create a file in current directory to verify we're not scanning it
        current_marker = "current_dir_marker.txt"
        with open(current_marker, "w") as f:
            f.write("marker")

        try:
            # Call the tool with temp directory path and set work_dir to its parent
            result_tuple = read_directory_structure(self.temp_dir, self.parent_dir)
            result = result_tuple[0] # Access the dictionary part

            # Verify the structure paths are relative to parent_dir
            expected_file_path = os.path.join(self.temp_dir_basename, self.root_file_name)
            expected_dir_path = os.path.join(self.temp_dir_basename, self.sub_dir_name)

            self.assertIn(expected_file_path, result["files"])
            self.assertIn(expected_dir_path, result["dirs"])

            # Verify the current directory file isn't in the result
            self.assertNotIn(current_marker, result["files"])
            self.assertFalse(any(current_marker in p for p in result["files"])) # Double check

        finally:
            # Remove the marker file
            if os.path.exists(current_marker):
                os.remove(current_marker)

    def test_subdirectory_path(self):
        """Test that tool works with a subdirectory path relative to its parent work_dir"""
        sub_dir_path = os.path.join(self.temp_dir, self.sub_dir_name)

        # Call the tool with subdirectory path, using temp_dir as work_dir
        result_tuple = read_directory_structure(sub_dir_path, self.temp_dir)
        result = result_tuple[0] # Access the dictionary part

        # Verify the structure only includes the subdirectory contents, relative to temp_dir
        self.assertEqual(len(result["dirs"]), 0) # No sub-sub-directories
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(os.path.join(self.sub_dir_name, self.sub_file_name), result["files"][0])

        # Verify root directory file isn't included
        self.assertNotIn(self.root_file_name, result["files"])

    def test_with_explicit_work_dir(self):
        """Test that tool respects the work_dir restriction"""
        # Set work_dir explicitly to the temp directory
        result_tuple = read_directory_structure(self.temp_dir, self.temp_dir)
        result = result_tuple[0] # Access the dictionary part

        # Verify the structure - paths relative to temp_dir
        self.assertIn(self.root_file_name, result["files"])
        self.assertIn(self.sub_dir_name, result["dirs"])
        self.assertNotIn(self.sub_file_name, result["files"]) # Not in root listing

        # Now try to access a path outside of work_dir (parent dir)
        with self.assertRaises(ValueError) as context:
            read_directory_structure(self.parent_dir, self.temp_dir)

        self.assertTrue("Security error" in str(context.exception))
        self.assertTrue("outside the allowed root path" in str(context.exception))


if __name__ == "__main__":
    unittest.main()
