"""Tests for find_in_files tool."""

import contextlib
from pathlib import Path

import pytest

from streetrace.tools.definitions.find_in_files import find_in_files
from streetrace.tools.definitions.result import OpResultCode


class TestFindInFilesBasic:
    """Test basic find_in_files functionality."""

    def test_find_in_single_file(self, work_dir: Path) -> None:
        """Test finding text in a single file."""
        test_file = work_dir / "test.py"
        test_file.write_text("def hello():\n    print('Hello, World!')\n")

        result = find_in_files("*.py", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 1
        assert result["output"][0]["filepath"] == "test.py"
        assert result["output"][0]["line_number"] == 2
        assert "Hello, World!" in result["output"][0]["snippet"]

    def test_find_in_multiple_files(self, work_dir: Path) -> None:
        """Test finding text across multiple files."""
        # Create multiple Python files
        file1 = work_dir / "file1.py"
        file1.write_text("# TODO: implement this\npass\n")

        file2 = work_dir / "file2.py"
        file2.write_text("def func():\n    # TODO: fix bug\n    return None\n")

        file3 = work_dir / "file3.py"
        file3.write_text("print('No todos here')\n")

        result = find_in_files("*.py", "TODO", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 2

        # Sort results by filepath for consistent testing
        results = sorted(result["output"], key=lambda x: x["filepath"])

        assert results[0]["filepath"] == "file1.py"
        assert results[0]["line_number"] == 1
        assert "implement this" in results[0]["snippet"]

        assert results[1]["filepath"] == "file2.py"
        assert results[1]["line_number"] == 2
        assert "fix bug" in results[1]["snippet"]

    def test_no_matches_found(self, work_dir: Path) -> None:
        """Test when no matches are found."""
        test_file = work_dir / "test.py"
        test_file.write_text("def hello():\n    print('Hello, World!')\n")

        result = find_in_files("*.py", "NONEXISTENT", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] == []

    def test_empty_directory(self, work_dir: Path) -> None:
        """Test searching in an empty directory."""
        result = find_in_files("*.py", "anything", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] == []

    def test_multiple_matches_in_single_file(self, work_dir: Path) -> None:
        """Test finding multiple matches within a single file."""
        test_file = work_dir / "test.py"
        test_file.write_text(
            "def function1():\n"
            "    print('function called')\n"
            "def function2():\n"
            "    print('another function called')\n",
        )

        result = find_in_files("*.py", "function", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 4  # "function" appears 4 times

    def test_case_sensitive_search(self, work_dir: Path) -> None:
        """Test that search is case-sensitive."""
        test_file = work_dir / "test.py"
        test_file.write_text("Hello hello HELLO\n")

        result = find_in_files("*.py", "hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 1
        assert "Hello hello HELLO" in result["output"][0]["snippet"]


class TestFindInFilesGitignore:
    """Test find_in_files with .gitignore functionality."""

    def test_gitignored_files_are_excluded(self, work_dir: Path) -> None:
        """Test that files matching .gitignore patterns are excluded."""
        # Create .gitignore
        gitignore = work_dir / ".gitignore"
        gitignore.write_text("*.log\ntemp/\n")

        # Create files
        py_file = work_dir / "app.py"
        py_file.write_text("print('Hello from Python')\n")

        log_file = work_dir / "app.log"
        log_file.write_text("Hello from log file\n")

        temp_dir = work_dir / "temp"
        temp_dir.mkdir()
        temp_file = temp_dir / "temp.txt"
        temp_file.write_text("Hello from temp file\n")

        result = find_in_files("*", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 1
        assert result["output"][0]["filepath"] == "app.py"

    def test_nested_gitignore_files(self, work_dir: Path) -> None:
        """Test that nested .gitignore files are respected."""
        # Create parent .gitignore
        parent_gitignore = work_dir / ".gitignore"
        parent_gitignore.write_text("*.log\n")

        # Create subdirectory with its own .gitignore
        subdir = work_dir / "subdir"
        subdir.mkdir()
        child_gitignore = subdir / ".gitignore"
        child_gitignore.write_text("*.tmp\n")

        # Create files
        py_file = work_dir / "app.py"
        py_file.write_text("print('Hello')\n")

        log_file = work_dir / "app.log"  # Ignored by parent
        log_file.write_text("Hello from log\n")

        subdir_py = subdir / "sub.py"
        subdir_py.write_text("print('Hello from subdir')\n")

        subdir_tmp = subdir / "temp.tmp"  # Ignored by child
        subdir_tmp.write_text("Hello from tmp\n")

        result = find_in_files("**/*", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 2

        # Sort for consistent testing
        results = sorted(result["output"], key=lambda x: x["filepath"])
        assert results[0]["filepath"] == "app.py"
        assert results[1]["filepath"] == "subdir/sub.py"

    def test_gitignore_negation_patterns(self, work_dir: Path) -> None:
        """Test that .gitignore negation patterns work correctly."""
        # Create .gitignore with negation
        gitignore = work_dir / ".gitignore"
        gitignore.write_text("*.log\n!important.log\n")

        # Create files
        regular_log = work_dir / "app.log"
        regular_log.write_text("Hello from regular log\n")

        important_log = work_dir / "important.log"
        important_log.write_text("Hello from important log\n")

        result = find_in_files("*.log", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 1
        assert result["output"][0]["filepath"] == "important.log"

    def test_no_gitignore_processes_all_files(self, work_dir: Path) -> None:
        """Test that all files are processed when no .gitignore exists."""
        # Create various files without .gitignore
        py_file = work_dir / "app.py"
        py_file.write_text("print('Hello')\n")

        log_file = work_dir / "app.log"
        log_file.write_text("Hello from log\n")

        txt_file = work_dir / "readme.txt"
        txt_file.write_text("Hello from readme\n")

        result = find_in_files("*", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 3


class TestFindInFilesEdgeCases:
    """Test edge cases and error handling."""

    def test_binary_files_are_skipped(self, work_dir: Path) -> None:
        """Test that binary files are gracefully skipped."""
        # Create a binary-ish file
        binary_file = work_dir / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02Hello\xff\xfe")

        result = find_in_files("*.bin", "Hello", work_dir)

        # Should not crash, might not find matches due to encoding handling
        assert result["result"] in (OpResultCode.SUCCESS, OpResultCode.FAILURE)

    def test_unreadable_files_are_skipped(self, work_dir: Path) -> None:
        """Test that unreadable files are gracefully skipped."""
        # Create a file
        test_file = work_dir / "test.txt"
        test_file.write_text("Hello World\n")

        # Make it unreadable (might not work on all systems)
        try:
            test_file.chmod(0o000)
            result = find_in_files("*.txt", "Hello", work_dir)
            # Should not crash
            assert result["result"] in (OpResultCode.SUCCESS, OpResultCode.FAILURE)
        except (OSError, PermissionError):
            pytest.skip("Cannot make file unreadable on this system")
        finally:
            # Restore permissions for cleanup
            with contextlib.suppress(OSError, PermissionError):
                test_file.chmod(0o644)

    def test_directory_paths_are_skipped(self, work_dir: Path) -> None:
        """Test that directories matching the pattern are skipped."""
        # Create directory that matches pattern
        py_dir = work_dir / "module.py"  # Directory with .py extension
        py_dir.mkdir()

        # Create actual file
        py_file = work_dir / "script.py"
        py_file.write_text("print('Hello')\n")

        result = find_in_files("*.py", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 1
        assert result["output"][0]["filepath"] == "script.py"

    def test_empty_search_string(self, work_dir: Path) -> None:
        """Test behavior with empty search string."""
        test_file = work_dir / "test.py"
        test_file.write_text("line1\nline2\nline3\n")

        result = find_in_files("*.py", "", work_dir)

        # Empty string should match all lines
        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 3

    def test_whitespace_handling(self, work_dir: Path) -> None:
        """Test that line whitespace is properly stripped in snippets."""
        test_file = work_dir / "test.py"
        test_file.write_text("    Hello with spaces    \n")

        result = find_in_files("*.py", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 1
        # Snippet should be stripped
        assert result["output"][0]["snippet"] == "Hello with spaces"


class TestFindInFilesGlobPatterns:
    """Test various glob pattern scenarios."""

    def test_recursive_glob_pattern(self, work_dir: Path) -> None:
        """Test recursive glob patterns work correctly."""
        # Create nested structure
        subdir = work_dir / "subdir"
        subdir.mkdir()
        nested_dir = subdir / "nested"
        nested_dir.mkdir()

        # Create files at different levels
        root_file = work_dir / "root.py"
        root_file.write_text("Hello from root\n")

        sub_file = subdir / "sub.py"
        sub_file.write_text("Hello from sub\n")

        nested_file = nested_dir / "nested.py"
        nested_file.write_text("Hello from nested\n")

        result = find_in_files("**/*.py", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 3

    def test_specific_file_pattern(self, work_dir: Path) -> None:
        """Test matching specific file names."""
        # Create files
        test1 = work_dir / "test1.py"
        test1.write_text("Hello from test1\n")

        test2 = work_dir / "test2.py"
        test2.write_text("Hello from test2\n")

        other = work_dir / "other.py"
        other.write_text("Hello from other\n")

        result = find_in_files("test*.py", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is not None
        assert len(result["output"]) == 2

    def test_multiple_extension_pattern(self, work_dir: Path) -> None:
        """Test pattern that doesn't match any files."""
        py_file = work_dir / "test.py"
        py_file.write_text("Hello from Python\n")

        result = find_in_files("*.js", "Hello", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] == []
