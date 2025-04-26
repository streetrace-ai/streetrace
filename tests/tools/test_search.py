import shutil  # Import shutil for robust directory removal
import unittest
from pathlib import Path

from streetrace.tools.search import search_files  # Use correct import path


class TestSearchFiles(unittest.TestCase):

    def setUp(self) -> None:
        # Create dummy files for testing
        self.test_dir = Path("test_search_files_temp")
        self.test_dir.mkdir(exist_ok=True)
        self.file1_rel_path = "file1.txt"
        self.file2_rel_path = "file2.txt"
        self.file1_abs_path = (self.test_dir / self.file1_rel_path).resolve()
        self.file2_abs_path = (self.test_dir / self.file2_rel_path).resolve()

        self.file1_abs_path.write_text(
            "This is the first file.\nIt contains some text.\nThis is a test.\n",
            encoding="utf-8",
        )
        self.file2_abs_path.write_text(
            "This is the second file.\nIt has different content.\nAnother test here.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        # Remove dummy files and directory using shutil
        if self.test_dir.exists():
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
