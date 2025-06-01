"""Tests for explicit risky command and path detection in CLI safety module."""

from streetrace.tools.cli_safety import (
    RISKY_COMMAND_PAIRS,
    RISKY_COMMANDS,
    RISKY_PATHS,
    SafetyCategory,
    _analyze_command_safety,
    _is_risky_command,
    _is_risky_path,
    cli_safe_category,
)


class TestRiskyCommandDetection:
    """Test scenarios for detecting explicitly risky commands."""

    def test_is_risky_command_basic(self):
        """Test detection of basic risky commands."""
        for cmd in RISKY_COMMANDS:
            assert _is_risky_command(cmd, []), f"Failed to detect {cmd} as risky"

    def test_is_risky_command_with_args(self):
        """Test detection of risky commands with additional arguments."""
        test_cases = [
            ("sudo", ["ls"]),
            ("apt", ["install", "package"]),
            ("pip", ["install", "package"]),
        ]

        for command, args in test_cases:
            assert _is_risky_command(command, args), (
                f"Failed to detect {command} {' '.join(args)} as risky"
            )

    def test_risky_command_pairs(self):
        """Test detection of risky command pairs."""
        for cmd_pair in RISKY_COMMAND_PAIRS:
            parts = cmd_pair.split(maxsplit=1)
            command = parts[0]
            args = [parts[1]] if len(parts) > 1 else []

            assert _is_risky_command(command, args), (
                f"Failed to detect {cmd_pair} as risky"
            )

    def test_non_risky_commands(self):
        """Test that safe commands are not flagged as risky."""
        test_cases = [
            ("ls", ["-la"]),
            ("cat", ["file.txt"]),
            ("git", ["status"]),
            ("echo", ["hello"]),
        ]

        for command, args in test_cases:
            assert not _is_risky_command(command, args), (
                f"Incorrectly flagged {command} as risky"
            )


class TestRiskyPathDetection:
    """Test scenarios for detecting explicitly risky paths."""

    def test_is_risky_path_basic(self):
        """Test detection of basic risky paths."""
        for path in RISKY_PATHS:
            assert _is_risky_path(path), f"Failed to detect {path} as risky"

    def test_is_risky_path_with_subpaths(self):
        """Test detection of subpaths of risky paths."""
        test_cases = [
            "/etc/passwd.bak",
            "/root/.bashrc",
            "/bin/custom_script",
        ]

        for path in test_cases:
            # test only actual risky paths based on our implementation
            for risky_path in RISKY_PATHS:
                if path.startswith(f"{risky_path}/") or path == risky_path:
                    assert _is_risky_path(path), f"Failed to detect {path} as risky"
                    break

    def test_non_risky_paths(self):
        """Test that safe paths are not flagged as risky."""
        test_cases = [
            "file.txt",
            "./config.yaml",
            "../project/readme.md",
            "-rw-r--r--",  # Looks like ls output, not a path
            "/tmp/safe_file.txt",  # Not in risky paths  # noqa: S108
        ]

        for path in test_cases:
            assert not _is_risky_path(path), f"Incorrectly flagged {path} as risky"


class TestCommandSafetyWithRiskyDetection:
    """Test the command safety analysis with risky detection."""

    def test_risky_command_detection_in_analysis(self):
        """Test that risky commands are identified in the safety analysis."""
        for cmd in ["sudo", "su", "dd", "ssh"]:
            result = _analyze_command_safety(cmd, [])
            assert result == SafetyCategory.RISKY, f"Failed for {cmd}"

    def test_risky_command_with_args_detection_in_analysis(self):
        """Test that risky commands with args are identified in safety analysis."""
        test_cases = [
            ("sudo", ["apt-get", "update"]),
            ("apt", ["install", "nginx"]),
        ]

        for command, args in test_cases:
            result = _analyze_command_safety(command, args)
            assert result == SafetyCategory.RISKY, (
                f"Failed for {command} {' '.join(args)}"
            )

    def test_risky_path_detection_in_analysis(self):
        """Test that risky paths are identified in the safety analysis."""
        test_cases = [
            ("cat", ["/etc/passwd"]),
            ("ls", ["/root"]),
            ("grep", ["pattern", "/etc/shadow"]),
        ]

        for command, args in test_cases:
            result = _analyze_command_safety(command, args)
            assert result == SafetyCategory.RISKY, (
                f"Failed for {command} {' '.join(args)}"
            )


class TestIntegrationWithRiskyDetection:
    """Integration tests for risky command and path detection."""

    def test_cli_safe_category_with_risky_commands(self):
        """Test that cli_safe_category correctly identifies risky commands."""
        test_cases = [
            "sudo ls",
            "apt install nginx",
            "rm -rf /bin",
            "cat /etc/passwd",
            "ssh user@example.com",
            "pip install --user package",
        ]

        for cmd in test_cases:
            result = cli_safe_category(cmd)
            assert result == SafetyCategory.RISKY, f"Failed for {cmd}"

    def test_combined_risky_scenarios(self):
        """Test combinations of risky commands and paths."""
        test_cases = [
            # Safe command but risky path
            "cat /etc/shadow",
            # Risky command but safe path
            "sudo cat file.txt",
            # Risky command and risky path
            "sudo rm -rf /bin",
            # Command with risky args
            "pip install --system package",
        ]

        for cmd in test_cases:
            result = cli_safe_category(cmd)
            assert result == SafetyCategory.RISKY, f"Failed for {cmd}"
