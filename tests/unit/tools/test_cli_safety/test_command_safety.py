"""Tests for command safety analysis in the CLI safety module."""

from unittest.mock import patch

from streetrace.tools.cli_safety import (
    SafetyCategory,
    _analyze_command_safety,
)


class TestCommandSafetyAnalysis:
    """Test scenarios for analyzing command safety."""

    def test_empty_command_is_risky(self):
        """Test that an empty command is considered risky."""
        result = _analyze_command_safety("", [])
        assert result == SafetyCategory.RISKY

    def test_safe_command_no_args_is_ambiguous(self):
        """Test that a safe command with no args is ambiguous."""
        result = _analyze_command_safety("ls", [])
        assert result == SafetyCategory.AMBIGUOUS

    def test_unsafe_command_no_args_is_risky(self):
        """Test that an unsafe command with no args is risky."""
        result = _analyze_command_safety("unknown_cmd", [])
        assert result == SafetyCategory.RISKY

    def test_explicitly_risky_command_no_args_is_risky(self):
        """Test that an explicitly risky command with no args is risky."""
        result = _analyze_command_safety("sudo", [])
        assert result == SafetyCategory.RISKY

    def test_explicitly_risky_command_with_args_is_risky(self):
        """Test that an explicitly risky command with args is risky."""
        result = _analyze_command_safety("sudo", ["ls"])
        assert result == SafetyCategory.RISKY

    def test_command_with_risky_argument_is_risky(self):
        """Test that a command with a risky path argument is risky."""
        result = _analyze_command_safety("ls", ["/etc/passwd"])
        assert result == SafetyCategory.RISKY

    def test_safe_command_with_flag_args(self):
        """Test safe command with flag arguments."""
        result = _analyze_command_safety("ls", ["-la"])
        assert result == SafetyCategory.AMBIGUOUS

    def test_safe_command_with_relative_path(self):
        """Test safe command with a relative path."""
        # Using a mocked path safety analysis to return consistent values
        with patch(
            "streetrace.tools.cli_safety._analyze_path_safety",
            return_value=(True, True),  # (is_relative, is_safe)
        ):
            result = _analyze_command_safety("cat", ["file.txt"])
            assert result == SafetyCategory.SAFE

    def test_safe_command_with_absolute_path(self):
        """Test safe command with an absolute path."""
        # Using a mocked path safety analysis to return consistent values
        with patch(
            "streetrace.tools.cli_safety._analyze_path_safety",
            return_value=(False, True),  # (is_relative, is_safe)
        ):
            result = _analyze_command_safety("cat", ["/etc/passwd"])
            assert result == SafetyCategory.RISKY

    def test_safe_command_with_unsafe_path(self):
        """Test safe command with an unsafe path (directory traversal)."""
        # Using a mocked path safety analysis to return consistent values
        with patch(
            "streetrace.tools.cli_safety._analyze_path_safety",
            return_value=(True, False),  # (is_relative, is_safe)
        ):
            result = _analyze_command_safety("cat", ["../file.txt"])
            assert result == SafetyCategory.RISKY

    def test_unsafe_command_with_safe_path(self):
        """Test unsafe command with a safe path."""
        # Using a mocked path safety analysis to return consistent values
        with patch(
            "streetrace.tools.cli_safety._analyze_path_safety",
            return_value=(True, True),  # (is_relative, is_safe)
        ):
            result = _analyze_command_safety("unknown_cmd", ["file.txt"])
            assert result == SafetyCategory.AMBIGUOUS

    def test_mixed_arguments(self):
        """Test command with a mix of flags and paths."""

        # Using a mocked path safety analysis for paths only (flags should be skipped)
        def mock_analyze_path(*_args, **_kwargs):
            return True, True  # (is_relative, is_safe)

        with patch(
            "streetrace.tools.cli_safety._analyze_path_safety",
            side_effect=mock_analyze_path,
        ):
            result = _analyze_command_safety("ls", ["-la", "folder/"])
            assert result == SafetyCategory.SAFE

    def test_path_detection_heuristic(self):
        """Test the heuristic that determines if arguments look like paths."""
        # Arguments that should look like paths
        for arg in ["file.py", "folder/file", "./file", "../file", "file.txt"]:
            with patch(
                "streetrace.tools.cli_safety._analyze_path_safety",
                return_value=(True, True),  # (is_relative, is_safe)
            ):
                result = _analyze_command_safety("cat", [arg])
                assert result == SafetyCategory.SAFE, f"Failed for {arg}"

        # Arguments that shouldn't look like paths
        for arg in ["word", "123", "-flag", "--option"]:
            result = _analyze_command_safety("echo", [arg])
            assert result == SafetyCategory.AMBIGUOUS, f"Failed for {arg}"
