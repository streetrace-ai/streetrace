"""Tests for gitignore functionality in path_utils."""

import contextlib
from pathlib import Path

import pytest

from streetrace.tools.definitions.path_utils import (
    is_ignored,
    load_gitignore_for_directory,
)


class TestLoadGitignoreForDirectory:
    """Test gitignore loading functionality."""

    def test_no_gitignore_returns_empty_spec(self, work_dir: Path) -> None:
        """Test that directories without .gitignore return empty PathSpec."""
        spec = load_gitignore_for_directory(work_dir)
        assert not spec.match_file("test.txt")
        assert not spec.match_file("test/")

    def test_single_gitignore_file(self, work_dir: Path) -> None:
        """Test loading patterns from a single .gitignore file."""
        gitignore_content = """
# Comment line
*.log
temp/
!important.log
"""
        gitignore_path = work_dir / ".gitignore"
        gitignore_path.write_text(gitignore_content)

        spec = load_gitignore_for_directory(work_dir)

        # Test ignored patterns
        assert spec.match_file("app.log")
        assert spec.match_file("temp/")
        assert spec.match_file("temp/file.txt")

        # Test negated pattern
        assert not spec.match_file("important.log")

        # Test unmatched files
        assert not spec.match_file("app.py")

    def test_nested_gitignore_files(self, work_dir: Path) -> None:
        """Test that nested .gitignore files are processed correctly."""
        # Create parent .gitignore
        parent_gitignore = work_dir / ".gitignore"
        parent_gitignore.write_text("*.log\nbuild/\n")

        # Create subdirectory with its own .gitignore
        subdir = work_dir / "subdir"
        subdir.mkdir()
        child_gitignore = subdir / ".gitignore"
        child_gitignore.write_text("*.tmp\n!important.tmp\n")

        spec = load_gitignore_for_directory(subdir)

        # Should inherit from parent
        assert spec.match_file("app.log")
        assert spec.match_file("build/")

        # Should have child patterns
        assert spec.match_file("test.tmp")
        assert not spec.match_file("important.tmp")

    def test_gitignore_file_reading_errors_are_handled(self, work_dir: Path) -> None:
        """Test that errors reading .gitignore files don't crash the function."""
        # Create a .gitignore file
        gitignore_path = work_dir / ".gitignore"
        gitignore_path.write_text("*.log\n")

        # Make it unreadable (this might not work on all systems)
        try:
            gitignore_path.chmod(0o000)
            spec = load_gitignore_for_directory(work_dir)
            # Should still return a spec, even if empty due to read error
            assert spec is not None
        except (OSError, PermissionError):
            # On some systems we can't make files unreadable
            pytest.skip("Cannot make file unreadable on this system")
        finally:
            # Restore permissions for cleanup
            with contextlib.suppress(OSError, PermissionError):
                gitignore_path.chmod(0o644)

    def test_empty_lines_and_comments_ignored(self, work_dir: Path) -> None:
        """Test that empty lines and comments are properly ignored."""
        gitignore_content = """
# This is a comment
*.log

# Another comment

temp/
    # Indented comment
*.tmp
"""
        gitignore_path = work_dir / ".gitignore"
        gitignore_path.write_text(gitignore_content)

        spec = load_gitignore_for_directory(work_dir)

        assert spec.match_file("app.log")
        assert spec.match_file("temp/")
        assert spec.match_file("file.tmp")


class TestIsIgnored:
    """Test file ignore checking functionality."""

    def test_file_not_ignored_with_empty_spec(self, work_dir: Path) -> None:
        """Test that files are not ignored when no patterns exist."""
        spec = load_gitignore_for_directory(work_dir)  # Empty spec
        test_file = work_dir / "test.txt"
        test_file.touch()

        assert not is_ignored(test_file, work_dir, spec)

    def test_file_ignored_by_pattern(self, work_dir: Path) -> None:
        """Test that files matching ignore patterns are ignored."""
        gitignore_path = work_dir / ".gitignore"
        gitignore_path.write_text("*.log\ntemp/\n")

        spec = load_gitignore_for_directory(work_dir)

        # Create test files
        log_file = work_dir / "app.log"
        log_file.touch()
        temp_dir = work_dir / "temp"
        temp_dir.mkdir()

        assert is_ignored(log_file, work_dir, spec)
        assert is_ignored(temp_dir, work_dir, spec)

    def test_directory_detection(self, work_dir: Path) -> None:
        """Test that directories are properly detected and matched."""
        gitignore_path = work_dir / ".gitignore"
        gitignore_path.write_text("build/\n")

        spec = load_gitignore_for_directory(work_dir)

        # Create directory
        build_dir = work_dir / "build"
        build_dir.mkdir()

        assert is_ignored(build_dir, work_dir, spec)

    def test_relative_path_handling(self, work_dir: Path) -> None:
        """Test that relative paths are handled correctly."""
        gitignore_path = work_dir / ".gitignore"
        gitignore_path.write_text("*.log\n")

        spec = load_gitignore_for_directory(work_dir)

        # Test with absolute path
        abs_file = work_dir / "app.log"
        abs_file.touch()
        assert is_ignored(abs_file, work_dir, spec)

        # Test with relative path (simulated)
        rel_file = Path("app.log")
        assert is_ignored(rel_file, work_dir, spec)

    def test_nested_directory_patterns(self, work_dir: Path) -> None:
        """Test patterns that match files in nested directories."""
        gitignore_path = work_dir / ".gitignore"
        gitignore_path.write_text("**/*.log\nsrc/temp/\n")

        spec = load_gitignore_for_directory(work_dir)

        # Create nested structure
        nested_dir = work_dir / "deep" / "nested"
        nested_dir.mkdir(parents=True)
        nested_log = nested_dir / "app.log"
        nested_log.touch()

        src_temp = work_dir / "src" / "temp"
        src_temp.mkdir(parents=True)

        assert is_ignored(nested_log, work_dir, spec)
        assert is_ignored(src_temp, work_dir, spec)

    def test_negation_patterns(self, work_dir: Path) -> None:
        """Test that negation patterns work correctly."""
        gitignore_path = work_dir / ".gitignore"
        gitignore_path.write_text("*.log\n!important.log\n")

        spec = load_gitignore_for_directory(work_dir)

        # Create test files
        regular_log = work_dir / "app.log"
        regular_log.touch()
        important_log = work_dir / "important.log"
        important_log.touch()

        assert is_ignored(regular_log, work_dir, spec)
        assert not is_ignored(important_log, work_dir, spec)
