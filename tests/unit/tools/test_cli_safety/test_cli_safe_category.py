"""Tests for the cli_safe_category function in the CLI safety module."""

from collections.abc import Callable
from contextlib import contextmanager
from unittest.mock import patch

from streetrace.tools.cli_safety import (
    SafetyCategory,
    cli_safe_category,
)


class TestCliSafeCategory:
    """Test scenarios for the cli_safe_category function."""

    @contextmanager
    def patch_analyze_command_safety(
        self,
        parsed_command: list[tuple[str, list[str]]],
        safety: SafetyCategory | Callable[[str, list[str]], SafetyCategory],
    ):
        """Test that analyze_command_safety is called for each command."""
        if isinstance(safety, SafetyCategory):
            with (
                patch(
                    "streetrace.tools.cli_safety._parse_command",
                    return_value=parsed_command,
                ),
                patch(
                    "streetrace.tools.cli_safety._analyze_command_safety",
                    return_value=safety,
                ),
            ):
                yield
        elif callable(safety):
            # If safety is a callable, we patch it to return the expected value
            with (
                patch(
                    "streetrace.tools.cli_safety._parse_command",
                    return_value=parsed_command,
                ),
                patch(
                    "streetrace.tools.cli_safety._analyze_command_safety",
                    side_effect=safety,
                ),
            ):
                yield
        else:
            msg = "Safety must be a SafetyCategory or callable"
            raise TypeError(msg)

    def test_empty_input(self):
        """Test that empty input is considered risky."""
        result = cli_safe_category("")
        assert result == SafetyCategory.RISKY

    def test_no_commands_parsed(self):
        """Test behavior when no commands are parsed."""
        with patch("streetrace.tools.cli_safety._parse_command", return_value=[]):
            result = cli_safe_category("some command")
            assert result == SafetyCategory.RISKY

    def test_single_safe_command(self):
        """Test with a single safe command."""
        with self.patch_analyze_command_safety(
            [("ls", ["-la"])],
            SafetyCategory.SAFE,
        ):
            result = cli_safe_category("ls -la")
            assert result == SafetyCategory.SAFE

    def test_single_ambiguous_command(self):
        """Test with a single ambiguous command."""
        with self.patch_analyze_command_safety(
            [("custom_command", ["arg"])],
            SafetyCategory.AMBIGUOUS,
        ):
            result = cli_safe_category("custom_command arg")
            assert result == SafetyCategory.AMBIGUOUS

    def test_single_risky_command(self):
        """Test with a single risky command."""
        with self.patch_analyze_command_safety(
            [("rm", ["-rf", "/"])],
            SafetyCategory.RISKY,
        ):
            result = cli_safe_category("rm -rf /")
            assert result == SafetyCategory.RISKY

    def test_multiple_commands_all_safe(self):
        """Test with multiple safe commands."""
        with self.patch_analyze_command_safety(
            [("ls", ["-la"]), ("grep", ["pattern"])],
            SafetyCategory.SAFE,
        ):
            result = cli_safe_category("ls -la | grep pattern")
            assert result == SafetyCategory.SAFE

    def test_multiple_commands_mixed_safety(self):
        """Test with multiple commands of different safety levels."""

        # Mock to return different values based on input
        def mock_analyze(cmd, _args):
            if cmd == "ls":
                return SafetyCategory.SAFE
            return SafetyCategory.RISKY

        with self.patch_analyze_command_safety(
            [("ls", ["-la"]), ("rm", ["-rf", "/"])],
            mock_analyze,
        ):
            result = cli_safe_category("ls -la && rm -rf /")
            # Most restrictive category should be returned
            assert result == SafetyCategory.RISKY

    def test_list_input(self):
        """Test with list input instead of string."""
        with self.patch_analyze_command_safety(
            [("echo", ["test"])],
            SafetyCategory.SAFE,
        ):
            result = cli_safe_category(["echo", "test"])
            assert result == SafetyCategory.SAFE

    def test_integration_with_real_functions(self):
        """Test integration between parse and analyze without mocking."""
        # Safe command
        result = cli_safe_category("ls -la")
        assert result == SafetyCategory.AMBIGUOUS

        # Risky command
        result = cli_safe_category("cat /etc/passwd")
        assert result == SafetyCategory.RISKY

        # Command with directory traversal
        result = cli_safe_category("cat ../../secrets.txt")
        assert result == SafetyCategory.RISKY
