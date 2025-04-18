import os
import shutil
import tempfile
import unittest

from streetrace.tools.read_directory_structure import read_directory_structure


class TestDirectoryStructureTool(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.mkdtemp()

        # Create a test directory structure
        self.create_test_directory_structure()

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def create_test_directory_structure(self):
        """Create a simple test directory structure"""
        # Create subdirectories
        sub_dir = os.path.join(self.temp_dir, "sub_dir")
        os.makedirs(sub_dir, exist_ok=True)

        # Create files
        with open(os.path.join(self.temp_dir, "root_file.txt"), "w") as f:
            f.write("content")

        with open(os.path.join(sub_dir, "sub_file.txt"), "w") as f:
            f.write("content")

    def test_specific_directory(self):
        """Test that tool works with a specified directory path"""
        # Create a file in current directory to verify we're not scanning it
        current_marker = "current_dir_marker.txt"
        with open(current_marker, "w") as f:
            f.write("marker")

        try:
            # Call the tool with temp directory path and set work_dir to include it
            structure = read_directory_structure(
                self.temp_dir, os.path.dirname(self.temp_dir)
            )

            # Verify the structure
            self.assertIn(
                os.path.basename(self.temp_dir) + "/root_file.txt", structure["files"]
            )
            self.assertIn(
                os.path.basename(self.temp_dir) + "/sub_dir", structure["dirs"]
            )

            # Verify the current directory file isn't in the result
            self.assertNotIn(current_marker, structure["files"])

        finally:
            # Remove the marker file
            if os.path.exists(current_marker):
                os.remove(current_marker)

    def test_subdirectory_path(self):
        """Test that tool works with a subdirectory path"""
        sub_dir_path = os.path.join(self.temp_dir, "sub_dir")

        # Call the tool with subdirectory path, using temp_dir as work_dir
        result = read_directory_structure(sub_dir_path, self.temp_dir)

        # Verify the structure only includes the subdirectory contents
        self.assertIn("sub_dir/sub_file.txt", result["files"])

        # Verify root directory files aren't included
        self.assertNotIn("root_file.txt", result.get(".", {}).get("files", []))

    def test_with_explicit_work_dir(self):
        """Test that tool respects the work_dir restriction"""
        # Set work_dir explicitly to the temp directory
        result = read_directory_structure(self.temp_dir, self.temp_dir)

        # Verify the structure
        self.assertIn("root_file.txt", result["files"])

        # Now try to access a path outside of work_dir
        parent_dir = os.path.dirname(self.temp_dir)

        with self.assertRaises(ValueError) as context:
            read_directory_structure(parent_dir, self.temp_dir)

        self.assertTrue("Security error" in str(context.exception))


if __name__ == "__main__":
    unittest.main()
