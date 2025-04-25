import os
import shutil  # Import shutil for robust directory removal
import unittest

from streetrace.tools.search import search_files  # Use correct import path


class TestSearchFiles(unittest.TestCase):

    def setUp(self) -> None:
        # Create dummy files for testing
        self.test_dir = "test_search_files_temp"
        os.makedirs(self.test_dir, exist_ok=True)
        self.file1_rel_path = "file1.txt"
        self.file2_rel_path = "file2.txt"
        self.file1_abs_path = os.path.abspath(
            os.path.join(self.test_dir, self.file1_rel_path),
        )
        self.file2_abs_path = os.path.abspath(
            os.path.join(self.test_dir, self.file2_rel_path),
        )

        with open(self.file1_abs_path, "w", encoding="utf-8") as f:
            f.write(
                "This is the first file.\nIt contains some text.\nThis is a test.\n",
            )
        with open(self.file2_abs_path, "w", encoding="utf-8") as f:
            f.write(
                "This is the second file.\nIt has different content.\nAnother test here.\n",
            )

    def tearDown(self) -> None:
        # Remove dummy files and directory using shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_search_files_found(self) -> None:
        # Test when the search string is found in the files
        pattern = "*.txt"
        search_string = "test"
        matches, msg = search_files(pattern, search_string, work_dir=self.test_dir)

        # Check message
        assert "matches found" in msg
        assert f"{len(matches)} matches found" == msg

        # Check matches (should be 2 files, 1 match per file)
        assert len(matches) == 2
        # Note: File paths in results are relative to work_dir
        matched_paths = {m["filepath"] for m in matches}
        self.assertSetEqual(matched_paths, {self.file1_rel_path, self.file2_rel_path})

        # Check details of one match
        match1 = next(m for m in matches if m["filepath"] == self.file1_rel_path)
        assert match1["line_number"] == 3
        assert match1["snippet"] == "This is a test."

    def test_search_files_not_found(self) -> None:
        # Test when the search string is not found in the files
        pattern = "*.txt"
        search_string = "nonexistent"
        matches, msg = search_files(pattern, search_string, work_dir=self.test_dir)
        assert len(matches) == 0
        assert msg == "0 matches found"

    def test_search_files_glob_pattern(self) -> None:
        # Test with a specific glob pattern
        pattern = "file1.txt"  # Relative pattern
        search_string = "first"
        matches, msg = search_files(pattern, search_string, work_dir=self.test_dir)
        assert len(matches) == 1
        assert matches[0]["filepath"] == self.file1_rel_path
        assert matches[0]["line_number"] == 1
        assert msg == "1 matches found"

    def test_search_files_empty_string(self) -> None:
        # Test with an empty search string (should match every line)
        pattern = "*.txt"
        search_string = ""
        matches, msg = search_files(pattern, search_string, work_dir=self.test_dir)
        # Total lines = 3 in file1 + 3 in file2 = 6
        assert len(matches) == 6
        assert msg == "6 matches found"


if __name__ == "__main__":
    unittest.main()
