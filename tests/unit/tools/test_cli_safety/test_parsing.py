"""Tests for CLI command parsing functionality in the safety module."""

from unittest.mock import patch

from streetrace.tools.cli_safety import _extract_commands_from_node, _parse_command


class TestCommandParsing:
    """Test scenarios for parsing CLI commands."""

    def test_parse_simple_string_command(self):
        """Test parsing a simple string command."""
        result = _parse_command("ls -la")
        assert result == [("ls", ["-la"])]

    def test_parse_simple_list_command(self):
        """Test parsing a simple list command."""
        result = _parse_command(["ls", "-la"])
        assert result == [("ls", ["-la"])]

    def test_parse_complex_command(self):
        """Test parsing a command with multiple arguments."""
        result = _parse_command("git commit -m 'test message'")
        # Actual parsing might produce different results based on bashlex behavior,
        # but the first command should be 'git' with args containing '-m' and some form
        # of the message
        assert len(result) == 1
        assert result[0][0] == "git"
        assert "-m" in result[0][1]

    def test_parse_piped_commands(self):
        """Test parsing commands with pipes."""
        result = _parse_command("ls -la | grep test")
        # Should extract both commands
        assert len(result) == 2
        assert result[0][0] == "ls"
        assert result[1][0] == "grep"

    def test_parse_chained_commands(self):
        """Test parsing commands with semicolons."""
        result = _parse_command("cd test; ls -la")
        # Should extract both commands
        assert len(result) == 2
        assert result[0][0] == "cd"
        assert result[1][0] == "ls"

    def test_parse_empty_command(self):
        """Test parsing an empty command."""
        result = _parse_command("")
        assert result == []

    def test_parse_command_with_bashlex_failure(self):
        """Test parsing when bashlex fails."""
        with patch("bashlex.parse", side_effect=Exception("Test exception")):
            # String input fallback
            result = _parse_command("ls -la")
            assert result == [("ls", ["-la"])]

            # List input fallback
            result = _parse_command(["ls", "-la"])
            assert result == [("ls", ["-la"])]

    def test_extract_commands_empty_node(self):
        """Test extraction with a node that has no parts."""

        # Create a mock node that has no parts or kind
        class MockNode:
            pass

        mock_node = MockNode()
        parsed_commands = []
        _extract_commands_from_node(mock_node, parsed_commands)
        assert parsed_commands == []

    def test_extract_commands_basic_node(self):
        """Test extraction with a basic command node."""

        # Create a mock node that resembles a simple command
        class MockPart:
            def __init__(self, kind, word=None):
                self.kind = kind
                if word:
                    self.word = word

        class MockNode:
            def __init__(self):
                self.kind = "command"
                self.parts = [
                    MockPart("word", "ls"),
                    MockPart("word", "-la"),
                ]

        mock_node = MockNode()
        parsed_commands = []
        _extract_commands_from_node(mock_node, parsed_commands)
        assert parsed_commands == [("ls", ["-la"])]

    def test_extract_commands_complex_node(self):
        """Test extraction with a node that has nested parts."""

        # Create a more complex mock node structure
        class MockPart:
            def __init__(self, kind, word=None, nested_parts=None):
                self.kind = kind
                if word:
                    self.word = word
                if nested_parts:
                    self.parts = nested_parts

        class MockNode:
            def __init__(self, kind=None, parts=None):
                if kind:
                    self.kind = kind
                if parts:
                    self.parts = parts

        # Main node with a nested command
        nested_command = MockNode(
            kind="command",
            parts=[
                MockPart("word", "grep"),
                MockPart("word", "test"),
            ],
        )

        main_command = MockNode(
            kind="command",
            parts=[
                MockPart("word", "ls"),
                MockPart("word", "-la"),
                MockPart("operator", nested_parts=[nested_command]),
            ],
        )

        parsed_commands = []
        _extract_commands_from_node(main_command, parsed_commands)

        # Should have extracted both commands - but don't enforce order as it's
        # implementation-dependent
        assert len(parsed_commands) == 2
        assert sorted(parsed_commands) == sorted([("ls", ["-la"]), ("grep", ["test"])])
