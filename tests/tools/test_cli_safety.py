"""Tests for the CLI safety module."""

from streetrace.tools.cli_safety import (
    SafetyCategory,
    _analyze_command_safety,
    _analyze_path_safety,
    _parse_command,
    cli_safe_category,
)


class TestCliSafety:
    """Test suite for CLI safety functions."""

    def test_parse_command_string(self):
        """Test parsing a command string."""
        result = _parse_command("ls -la")
        assert result == [("ls", ["-la"])]

    def test_parse_command_list(self):
        """Test parsing a command from a list."""
        result = _parse_command(["ls", "-la"])
        assert result == [("ls", ["-la"])]

    def test_parse_complex_command(self):
        """Test parsing a more complex command with pipes."""
        result = _parse_command("grep -r 'pattern' . | sort")
        # Should capture both the grep and sort commands
        assert len(result) == 2
        assert result[0][0] == "grep"
        assert result[1][0] == "sort"

    def test_analyze_path_safety_relative(self):
        """Test analyzing a simple relative path."""
        is_relative, is_safe = _analyze_path_safety("./file.txt")
        assert is_relative is True
        assert is_safe is True

    def test_analyze_path_safety_absolute(self):
        """Test analyzing an absolute path."""
        is_relative, is_safe = _analyze_path_safety("/etc/passwd")
        assert is_relative is False
        assert is_safe is False

    def test_analyze_path_safety_traversal(self):
        """Test analyzing a path with directory traversal."""
        is_relative, is_safe = _analyze_path_safety("../../etc/passwd")
        assert is_relative is True
        assert is_safe is False  # Not safe due to traversal

    def test_analyze_command_safety_safe(self):
        """Test analyzing a safe command."""
        result = _analyze_command_safety("ls", ["-la", "./src"])
        assert result == SafetyCategory.SAFE

    def test_analyze_command_safety_ambiguous(self):
        """Test analyzing an ambiguous command."""
        result = _analyze_command_safety("custom_script", ["--option"])
        assert result == SafetyCategory.AMBIGUOUS

    def test_analyze_command_safety_risky(self):
        """Test analyzing a risky command."""
        result = _analyze_command_safety("rm", ["-rf", "/"])
        assert result == SafetyCategory.RISKY

    def test_cli_safe_category_safe(self):
        """Test the main cli_safe_category function with a safe command."""
        result = cli_safe_category("ls -la ./src")
        assert result == SafetyCategory.SAFE

    def test_cli_safe_category_ambiguous(self):
        """Test the main cli_safe_category function with an ambiguous command."""
        result = cli_safe_category("unknown_tool --help")
        assert result == SafetyCategory.AMBIGUOUS

    def test_cli_safe_category_risky(self):
        """Test the main cli_safe_category function with a risky command."""
        result = cli_safe_category("rm -rf /etc")
        assert result == SafetyCategory.RISKY

    def test_cli_safe_category_multiple_commands(self):
        """Test the main cli_safe_category function with multiple commands."""
        # If any command is risky, the result should be risky
        result = cli_safe_category("ls -la && rm -rf /")
        assert result == SafetyCategory.RISKY

    def test_cli_safe_category_with_path_traversal(self):
        """Test the main cli_safe_category function with path traversal."""
        result = cli_safe_category("cat ../../etc/passwd")
        assert result == SafetyCategory.RISKY

    def test_cli_safe_category_with_flags(self):
        """Test the main cli_safe_category function with command flags."""
        result = cli_safe_category("grep -r --include='*.py' 'pattern' .")
        assert result == SafetyCategory.SAFE

    def test_cli_safe_category_parent_folder(self):
        """Test analyzing a safe command."""
        result = cli_safe_category("cat ../README.md")
        assert result == SafetyCategory.RISKY

    def test_cli_safe_category_parent_escape(self):
        """Test analyzing a safe command."""
        result = cli_safe_category("cat srd/../../README.md")
        assert result == SafetyCategory.RISKY

    def test_cli_safe_category_rm_file_1(self):
        """Test analyzing a safe command."""
        result = cli_safe_category("rm ./README.md")
        assert result == SafetyCategory.SAFE

    def test_cli_safe_category_rm_file_2(self):
        """Test analyzing a safe command."""
        result = cli_safe_category("rm README.md")
        assert result == SafetyCategory.SAFE

    def test_cli_safe_category_rm_in_parent_folder(self):
        """Test analyzing a safe command."""
        result = cli_safe_category("rm ../README.md")
        assert result == SafetyCategory.RISKY
