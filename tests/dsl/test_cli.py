"""Tests for DSL CLI commands.

Test the check and dump-python CLI commands for DSL file validation
and code generation.
"""

import json
from pathlib import Path

from streetrace.dsl.cli import (
    EXIT_FILE_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERRORS,
    check_directory,
    check_file,
    dump_python,
    run_check,
    run_dump_python,
)

# =============================================================================
# Sample DSL Sources for Testing
# =============================================================================

VALID_DSL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello! How can I help you today?\"\"\"

tool fs = builtin streetrace.filesystem

agent helper:
    tools fs
    instruction greeting
"""

INVALID_DSL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting using model "undefined_model": \"\"\"Hello!\"\"\"
"""

SYNTAX_ERROR_SOURCE = """\
streetrace v1

model = broken syntax
"""


# =============================================================================
# check_file Tests
# =============================================================================


class TestCheckFile:
    """Test check_file function."""

    def test_check_valid_file(self, tmp_path: Path) -> None:
        """Check a valid DSL file returns success."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = check_file(dsl_file)
        assert result == EXIT_SUCCESS

    def test_check_file_not_found(self, tmp_path: Path) -> None:
        """Check nonexistent file returns file error."""
        dsl_file = tmp_path / "nonexistent.sr"

        result = check_file(dsl_file)
        assert result == EXIT_FILE_ERROR

    def test_check_directory_as_file(self, tmp_path: Path) -> None:
        """Check directory as file returns file error."""
        result = check_file(tmp_path)
        assert result == EXIT_FILE_ERROR

    def test_check_with_semantic_errors(self, tmp_path: Path) -> None:
        """Check file with semantic errors returns validation errors."""
        dsl_file = tmp_path / "invalid.sr"
        dsl_file.write_text(INVALID_DSL_SOURCE)

        result = check_file(dsl_file)
        assert result == EXIT_VALIDATION_ERRORS

    def test_check_with_syntax_errors(self, tmp_path: Path) -> None:
        """Check file with syntax errors returns validation errors."""
        dsl_file = tmp_path / "syntax_error.sr"
        dsl_file.write_text(SYNTAX_ERROR_SOURCE)

        result = check_file(dsl_file)
        assert result == EXIT_VALIDATION_ERRORS

    def test_check_json_output_valid(self, tmp_path: Path) -> None:
        """Check valid file with JSON output."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = check_file(dsl_file, json_output=True)
        assert result == EXIT_SUCCESS

    def test_check_json_output_invalid(self, tmp_path: Path, capsys) -> None:
        """Check invalid file with JSON output."""
        dsl_file = tmp_path / "invalid.sr"
        dsl_file.write_text(INVALID_DSL_SOURCE)

        result = check_file(dsl_file, json_output=True)
        captured = capsys.readouterr()

        assert result == EXIT_VALIDATION_ERRORS
        data = json.loads(captured.out)
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_check_verbose_output(self, tmp_path: Path, capsys) -> None:
        """Check with verbose output shows filename."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = check_file(dsl_file, verbose=True)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        assert "valid" in captured.out


# =============================================================================
# check_directory Tests
# =============================================================================


class TestCheckDirectory:
    """Test check_directory function."""

    def test_check_directory_with_valid_files(self, tmp_path: Path) -> None:
        """Check directory with all valid files."""
        (tmp_path / "file1.sr").write_text(VALID_DSL_SOURCE)
        (tmp_path / "file2.sr").write_text(VALID_DSL_SOURCE)

        result = check_directory(tmp_path)
        assert result == EXIT_SUCCESS

    def test_check_directory_with_invalid_file(self, tmp_path: Path) -> None:
        """Check directory with one invalid file."""
        (tmp_path / "valid.sr").write_text(VALID_DSL_SOURCE)
        (tmp_path / "invalid.sr").write_text(INVALID_DSL_SOURCE)

        result = check_directory(tmp_path)
        assert result == EXIT_VALIDATION_ERRORS

    def test_check_empty_directory(self, tmp_path: Path) -> None:
        """Check empty directory returns success."""
        result = check_directory(tmp_path)
        assert result == EXIT_SUCCESS

    def test_check_nonexistent_directory(self, tmp_path: Path) -> None:
        """Check nonexistent directory returns file error."""
        result = check_directory(tmp_path / "nonexistent")
        assert result == EXIT_FILE_ERROR

    def test_check_file_as_directory(self, tmp_path: Path) -> None:
        """Check file as directory returns file error."""
        dsl_file = tmp_path / "file.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = check_directory(dsl_file)
        assert result == EXIT_FILE_ERROR

    def test_check_nested_directories(self, tmp_path: Path) -> None:
        """Check recursively finds files in subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.sr").write_text(VALID_DSL_SOURCE)
        (tmp_path / "top.sr").write_text(VALID_DSL_SOURCE)

        result = check_directory(tmp_path)
        assert result == EXIT_SUCCESS


# =============================================================================
# dump_python Tests
# =============================================================================


class TestDumpPython:
    """Test dump_python function."""

    def test_dump_valid_file(self, tmp_path: Path, capsys) -> None:
        """Dump Python code from valid DSL file."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = dump_python(dsl_file)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        assert "class" in captured.out
        assert "DslAgentWorkflow" in captured.out

    def test_dump_file_not_found(self, tmp_path: Path) -> None:
        """Dump nonexistent file returns file error."""
        dsl_file = tmp_path / "nonexistent.sr"

        result = dump_python(dsl_file)
        assert result == EXIT_FILE_ERROR

    def test_dump_with_output_file(self, tmp_path: Path) -> None:
        """Dump Python code to output file."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)
        output_file = tmp_path / "output.py"

        result = dump_python(dsl_file, output_file=output_file)

        assert result == EXIT_SUCCESS
        assert output_file.exists()
        content = output_file.read_text()
        assert "class" in content

    def test_dump_without_comments(self, tmp_path: Path, capsys) -> None:
        """Dump Python code without source comments."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        # Source line comments should be filtered
        lines = [ln for ln in captured.out.split("\n") if ln.strip()]
        # Check that file is still valid Python
        assert any("class" in line for line in lines)

    def test_dump_syntax_error(self, tmp_path: Path) -> None:
        """Dump file with syntax error returns file error."""
        dsl_file = tmp_path / "error.sr"
        dsl_file.write_text(SYNTAX_ERROR_SOURCE)

        result = dump_python(dsl_file)
        assert result == EXIT_FILE_ERROR


# =============================================================================
# CLI Entry Point Tests
# =============================================================================


class TestRunCheck:
    """Test run_check CLI entry point."""

    def test_run_check_valid_file(self, tmp_path: Path) -> None:
        """Run check command on valid file."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = run_check([str(dsl_file)])
        assert result == EXIT_SUCCESS

    def test_run_check_with_verbose(self, tmp_path: Path) -> None:
        """Run check command with verbose flag."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = run_check(["-v", str(dsl_file)])
        assert result == EXIT_SUCCESS

    def test_run_check_with_json_format(self, tmp_path: Path) -> None:
        """Run check command with JSON format."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = run_check(["--format", "json", str(dsl_file)])
        assert result == EXIT_SUCCESS

    def test_run_check_with_strict(self, tmp_path: Path) -> None:
        """Run check command with strict flag."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = run_check(["--strict", str(dsl_file)])
        assert result == EXIT_SUCCESS


class TestRunDumpPython:
    """Test run_dump_python CLI entry point."""

    def test_run_dump_python(self, tmp_path: Path) -> None:
        """Run dump-python command."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = run_dump_python([str(dsl_file)])
        assert result == EXIT_SUCCESS

    def test_run_dump_python_with_output(self, tmp_path: Path) -> None:
        """Run dump-python command with output file."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)
        output_file = tmp_path / "output.py"

        result = run_dump_python(["-o", str(output_file), str(dsl_file)])
        assert result == EXIT_SUCCESS
        assert output_file.exists()

    def test_run_dump_python_no_comments(self, tmp_path: Path) -> None:
        """Run dump-python command without comments."""
        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = run_dump_python(["--no-comments", str(dsl_file)])
        assert result == EXIT_SUCCESS


# =============================================================================
# Main CLI Integration Tests
# =============================================================================


class TestMainCLIIntegration:
    """Test DSL commands via main CLI entry point."""

    def test_check_command_via_subprocess(self, tmp_path: Path) -> None:
        """Check command works via streetrace CLI."""
        import subprocess

        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = subprocess.run(  # noqa: S603
            ["poetry", "run", "streetrace", "check", str(dsl_file)],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == EXIT_SUCCESS

    def test_check_command_with_invalid_file(self, tmp_path: Path) -> None:
        """Check command returns error for invalid DSL."""
        import subprocess

        dsl_file = tmp_path / "invalid.sr"
        dsl_file.write_text(INVALID_DSL_SOURCE)

        result = subprocess.run(  # noqa: S603
            ["poetry", "run", "streetrace", "check", str(dsl_file)],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == EXIT_VALIDATION_ERRORS
        assert "error" in result.stdout.lower() or "error" in result.stderr.lower()

    def test_dump_python_command_via_subprocess(self, tmp_path: Path) -> None:
        """dump-python command works via streetrace CLI."""
        import subprocess

        dsl_file = tmp_path / "valid.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        result = subprocess.run(  # noqa: S603
            ["poetry", "run", "streetrace", "dump-python", str(dsl_file)],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == EXIT_SUCCESS
        assert "class" in result.stdout
        assert "DslAgentWorkflow" in result.stdout
