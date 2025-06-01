"""Test fixtures for CLI safety module tests."""
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_logger():
    """Fixture providing a mock logger."""
    with patch("streetrace.tools.cli_safety.logger") as mock_log:
        yield mock_log


@pytest.fixture
def mock_bashlex_parse():
    """Fixture providing a mock for the bashlex.parse function."""
    with patch("bashlex.parse") as mock_parse:
        yield mock_parse


@pytest.fixture
def simple_bashlex_node():
    """Fixture providing a simple bashlex AST node for a command."""
    # Create a simplified mock of a bashlex node structure
    class MockWord:
        def __init__(self, word_text):
            self.kind = "word"
            self.word = word_text

    class MockCommand:
        def __init__(self, command, args=None):
            self.kind = "command"
            self.parts = [MockWord(command)]
            if args:
                for arg in args:
                    self.parts.append(MockWord(arg))

    return MockCommand


@pytest.fixture
def complex_bashlex_node():
    """Fixture providing a complex bashlex AST node with nested commands."""
    # Create a more complex mock of a bashlex node structure with pipes/lists
    class MockWord:
        def __init__(self, word_text):
            self.kind = "word"
            self.word = word_text

    class MockOperator:
        def __init__(self, operator_text):
            self.kind = "operator"
            self.op = operator_text

    class MockCommand:
        def __init__(self, command, args=None):
            self.kind = "command"
            self.parts = [MockWord(command)]
            if args:
                for arg in args:
                    self.parts.append(MockWord(arg))

    class MockPipeline:
        def __init__(self, commands):
            self.kind = "pipeline"
            self.parts = []
            for i, cmd in enumerate(commands):
                self.parts.append(cmd)
                if i < len(commands) - 1:
                    self.parts.append(MockOperator("|"))

    return MockPipeline
