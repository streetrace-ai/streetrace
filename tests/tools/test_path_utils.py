import unittest
from pathlib import Path

import pytest

from streetrace.tools.path_utils import (
    ensure_parent_directory_exists,
    normalize_and_validate_path,
    validate_directory_exists,
    validate_file_exists,
)


class TestPathUtils(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary test directory structure
        self.test_dir = Path(__file__).parent / "test_dir"
        self.nested_dir = self.test_dir / "nested"

        # Ensure test directories exist
        self.nested_dir.mkdir(parents=True, exist_ok=True)

        # Create test files
        self.test_file = self.test_dir / "test_file.txt"
        self.test_file.write_text("test content")

    def tearDown(self) -> None:
        # Clean up test files and directories
        if self.test_file.exists():
            self.test_file.unlink()

        if self.nested_dir.exists():
            self.nested_dir.rmdir()

        if self.test_dir.exists():
            self.test_dir.rmdir()

    def test_normalize_valid_relative_path(self) -> None:
        work_dir = self.test_dir
        path = "test_file.txt"

        result = normalize_and_validate_path(path, work_dir)
        expected = (work_dir / path).resolve()

        assert result == expected

    def test_normalize_valid_absolute_path(self) -> None:
        work_dir = self.test_dir
        path = self.test_dir / "test_file.txt"

        result = normalize_and_validate_path(path, work_dir)
        expected = Path(path).resolve()

        assert result == expected

    def test_normalize_invalid_path_outside_workdir(self) -> None:
        work_dir = self.test_dir
        path = self.test_dir / ".." / ".."

        with pytest.raises(ValueError):
            normalize_and_validate_path(path, work_dir)

    def test_normalize_path_with_parent_references(self) -> None:
        work_dir = self.test_dir
        path = "nested/../test_file.txt"

        result = normalize_and_validate_path(path, work_dir)
        expected = (work_dir / "test_file.txt").resolve()

        assert result == expected

    def test_validate_file_exists(self) -> None:
        # Test with existing file
        validate_file_exists(self.test_file)

        # Test with non-existent file
        non_existent_file = self.test_dir / "non_existent.txt"
        with pytest.raises(ValueError, match=str(non_existent_file)):
            validate_file_exists(non_existent_file)

        # Test with directory instead of file
        with pytest.raises(ValueError, match=str(self.test_dir)):
            validate_file_exists(self.test_dir)

    def test_validate_directory_exists(self) -> None:
        # Test with existing directory
        validate_directory_exists(self.test_dir)

        # Test with non-existent directory
        non_existent_dir = self.test_dir / "non_existent_dir"
        with pytest.raises(ValueError, match=str(non_existent_dir)):
            validate_directory_exists(non_existent_dir)

        # Test with file instead of directory
        with pytest.raises(ValueError, match=str(self.test_file)):
            validate_directory_exists(self.test_file)

    def test_ensure_parent_directory_exists(self) -> None:
        # Path to a new file in an existing directory
        new_file_in_existing_dir = self.test_dir / "new_file.txt"
        ensure_parent_directory_exists(new_file_in_existing_dir)

        # Path to a new file in a new directory
        new_dir = self.test_dir / "new_dir"
        new_file_in_new_dir = new_dir / "new_file.txt"
        ensure_parent_directory_exists(new_file_in_new_dir)

        # Check directory was created
        assert new_dir.exists()
        assert new_dir.is_dir()

        # Clean up the new directory
        new_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
