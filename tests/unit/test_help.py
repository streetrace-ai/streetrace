"""Tests for help functionality."""

import subprocess
import sys


class TestHelpFunctionality:
    """Test help command functionality."""

    def test_help_long_form(self) -> None:
        """Test that --help shows help message and exits with code 0."""
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "streetrace.main", "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "usage: " in result.stdout
        assert "--help" in result.stdout
        assert "--version" in result.stdout
        assert "--model" in result.stdout
        assert "--path" in result.stdout
        assert "show this help message and exit" in result.stdout

    def test_help_short_form(self) -> None:
        """Test that -h shows help message and exits with code 0."""
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "streetrace.main", "-h"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "usage: " in result.stdout
        assert "--help" in result.stdout
        assert "--version" in result.stdout
        assert "--model" in result.stdout
        assert "--path" in result.stdout
        assert "show this help message and exit" in result.stdout

    def test_help_has_proper_format(self) -> None:
        """Test that help output has proper format with sections."""
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "streetrace.main", "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0

        # Check for proper sections
        assert "positional arguments:" in result.stdout
        assert "options:" in result.stdout

        # Check that usage line is present and formatted correctly
        assert result.stdout.startswith("usage: ")

        # Check that help doesn't have stderr output (clean execution)
        assert result.stderr == ""
