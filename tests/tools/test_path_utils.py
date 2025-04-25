import os
import sys
import unittest

# Add the parent directory to path to allow importing the module
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

import pytest

from streetrace.tools.path_utils import (
    ensure_directory_exists,
    normalize_and_validate_path,
    validate_directory_exists,
    validate_file_exists,
)


class TestPathUtils(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary test directory structure
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_dir")
        self.nested_dir = os.path.join(self.test_dir, "nested")

        # Ensure test directories exist
        os.makedirs(self.nested_dir, exist_ok=True)

        # Create test files
        self.test_file = os.path.join(self.test_dir, "test_file.txt")
        with open(self.test_file, "w") as f:
            f.write("test content")

    def tearDown(self) -> None:
        # Clean up test files and directories
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

        if os.path.exists(self.nested_dir):
            os.rmdir(self.nested_dir)

        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_normalize_valid_relative_path(self) -> None:
        work_dir = self.test_dir
        path = "test_file.txt"

        result = normalize_and_validate_path(path, work_dir)
        expected = os.path.abspath(os.path.join(work_dir, path))

        assert result == expected

    def test_normalize_valid_absolute_path(self) -> None:
        work_dir = self.test_dir
        path = os.path.join(self.test_dir, "test_file.txt")

        result = normalize_and_validate_path(path, work_dir)
        expected = os.path.abspath(path)

        assert result == expected

    def test_normalize_invalid_path_outside_workdir(self) -> None:
        work_dir = self.test_dir
        path = os.path.join(self.test_dir, "..", "..")

        with pytest.raises(ValueError):
            normalize_and_validate_path(path, work_dir)

    def test_normalize_path_with_parent_references(self) -> None:
        work_dir = self.test_dir
        path = os.path.join("nested", "..", "test_file.txt")

        result = normalize_and_validate_path(path, work_dir)
        expected = os.path.abspath(os.path.join(work_dir, "test_file.txt"))

        assert result == expected

    def test_validate_file_exists(self) -> None:
        # Test with existing file
        validate_file_exists(self.test_file)

        # Test with non-existent file
        non_existent_file = os.path.join(self.test_dir, "non_existent.txt")
        with pytest.raises(ValueError):
            validate_file_exists(non_existent_file)

        # Test with directory instead of file
        with pytest.raises(ValueError):
            validate_file_exists(self.test_dir)

    def test_validate_directory_exists(self) -> None:
        # Test with existing directory
        validate_directory_exists(self.test_dir)

        # Test with non-existent directory
        non_existent_dir = os.path.join(self.test_dir, "non_existent_dir")
        with pytest.raises(ValueError):
            validate_directory_exists(non_existent_dir)

        # Test with file instead of directory
        with pytest.raises(ValueError):
            validate_directory_exists(self.test_file)

    def test_ensure_directory_exists(self) -> None:
        # Path to a new file in an existing directory
        new_file_in_existing_dir = os.path.join(self.test_dir, "new_file.txt")
        ensure_directory_exists(new_file_in_existing_dir)

        # Path to a new file in a new directory
        new_dir = os.path.join(self.test_dir, "new_dir")
        new_file_in_new_dir = os.path.join(new_dir, "new_file.txt")
        ensure_directory_exists(new_file_in_new_dir)

        # Check directory was created
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)

        # Clean up the new directory
        os.rmdir(new_dir)


if __name__ == "__main__":
    unittest.main()
