"""Unit tests for Ollama history converter.

This module contains tests for the OllamaHistoryConverter class that converts
between Streetrace history and Ollama-specific formats.
"""

import unittest
from unittest.mock import MagicMock

from streetrace.llm.ollama.converter import _ROLES, OllamaHistoryConverter
from streetrace.llm.wrapper import (
    ContentPartFinishReason,
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Role,
    ToolCallResult,
    ToolOutput,
)


class TestOllamaHistoryConverter(unittest.TestCase):
    """Tests for OllamaHistoryConverter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.converter = OllamaHistoryConverter()

    def test_basic_conversion_text_messages(self):
        """Test conversion of simple text messages for all role types."""
        # Create a history with messages from different roles
        history = History(
            system_message="You are a helpful assistant",
            context="This is contextual information",
        )

        # Add a user message
        history.add_message(Role.USER, [ContentPartText(text="Hello, how are you?")])

        # Add a model response
        history.add_message(
            Role.MODEL,
            [ContentPartText(text="I'm doing well, thank you for asking!")],
        )

        # Convert to provider history
        provider_history = self.converter.create_provider_history(history)

        # Verify the conversion output
        assert len(provider_history) == 4  # system, context, user, model
        assert provider_history[0]["role"] == "system"
        assert provider_history[0]["content"] == "You are a helpful assistant"
        assert provider_history[1]["role"] == "user"
        assert provider_history[1]["content"] == "This is contextual information"
        assert provider_history[2]["role"] == "user"
        assert provider_history[2]["content"] == "Hello, how are you?"
        assert provider_history[3]["role"] == "assistant"
        assert provider_history[3]["content"] == "I'm doing well, thank you for asking!"

    def test_empty_history(self):
        """Test conversion of an empty History object."""
        history = History()
        provider_history = self.converter.create_provider_history(history)

        # Should return an empty list
        assert provider_history == []

    def test_system_message_only(self):
        """Test conversion of a History with only a system message."""
        history = History(system_message="You are a helpful assistant")
        provider_history = self.converter.create_provider_history(history)

        # Should include the system message
        assert len(provider_history) == 1
        assert provider_history[0]["role"] == "system"
        assert provider_history[0]["content"] == "You are a helpful assistant"

    def test_context_message_only(self):
        """Test conversion of a History with only a context message."""
        history = History(context="This is contextual information")
        provider_history = self.converter.create_provider_history(history)

        # Should include the context message as user role
        assert len(provider_history) == 1
        assert provider_history[0]["role"] == "user"
        assert provider_history[0]["content"] == "This is contextual information"

    def test_complex_content_types(self):
        """Test conversion of messages with multiple content types."""
        history = History()

        # Add a message with a tool call
        history.add_message(
            Role.USER,
            [
                ContentPartText(text="I need to search for something"),
                ContentPartToolCall(
                    id="search-1",
                    name="search_files",
                    arguments={"pattern": "*.py", "search_string": "def test"},
                ),
            ],
        )

        # Add a message with a tool result
        history.add_message(
            Role.TOOL,
            [
                ContentPartToolResult(
                    id="search-1-result",
                    name="search_files",
                    content=ToolCallResult.ok(
                        output=ToolOutput(
                            type="text",
                            content="Found 5 files matching the pattern",
                        ),
                    ),
                ),
            ],
        )

        # Convert to provider history
        provider_history = self.converter.create_provider_history(history)

        # Verify the conversion output
        assert len(provider_history) == 2
        # First message should have the text and tool call
        assert provider_history[0]["role"] == "user"
        assert provider_history[0]["content"] == "I need to search for something"
        # Verify the tool call was included
        assert provider_history[0]["tool_calls"] != []
        assert (
            provider_history[0]["tool_calls"][0]["function"]["name"] == "search_files"
        )
        assert provider_history[0]["tool_calls"][0]["function"]["arguments"] == {
            "pattern": "*.py",
            "search_string": "def test",
        }

        # Second message should be the tool role with the result
        assert provider_history[1]["role"] == "tool"
        # Should include the serialized tool result
        assert "content" in provider_history[1]
        assert "search_files" in provider_history[1]["content"]

    def test_response_parsing_text(self):
        """Test parsing a simple text response from Ollama."""
        # Create a mock Ollama response with text content
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "This is a response from Ollama"
        mock_message.tool_calls = []
        mock_response.message = mock_message

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content
        assert len(response_parts) == 2  # Text and FinishReason
        assert response_parts[0].text == "This is a response from Ollama"
        assert isinstance(response_parts[1], ContentPartFinishReason)
        assert response_parts[1].finish_reason == "done"

    def test_empty_response(self):
        """Test handling of empty responses."""
        # Create a mock empty Ollama response
        mock_response = MagicMock()
        mock_response.message = None

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify empty result
        assert len(response_parts) == 0

    def test_response_parsing_with_tool_calls(self):
        """Test parsing a response containing a tool call."""
        # Create a mock Ollama response with a tool call
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = ""  # No text content

        # Create a tool call
        tool_call = MagicMock()
        function = MagicMock()
        function.name = "search_files"
        function.arguments = {"pattern": "*.py", "search_string": "def test"}
        tool_call.function = function

        mock_message.tool_calls = [tool_call]
        mock_response.message = mock_message

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content
        assert len(response_parts) == 2  # Tool call and finish reason
        assert isinstance(response_parts[0], ContentPartToolCall)
        assert response_parts[0].name == "search_files"
        assert response_parts[0].arguments == {
            "pattern": "*.py",
            "search_string": "def test",
        }
        assert isinstance(response_parts[1], ContentPartFinishReason)

    def test_response_with_text_and_tool_calls(self):
        """Test parsing a response with both text and tool calls."""
        # Create a mock Ollama response with text and a tool call
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "I'll search for Python files"

        # Create a tool call
        tool_call = MagicMock()
        function = MagicMock()
        function.name = "search_files"
        function.arguments = {"pattern": "*.py", "search_string": "def test"}
        tool_call.function = function

        mock_message.tool_calls = [tool_call]
        mock_response.message = mock_message

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content
        assert len(response_parts) == 3  # Text, tool call, and finish reason
        assert isinstance(response_parts[0], ContentPartText)
        assert response_parts[0].text == "I'll search for Python files"
        assert isinstance(response_parts[1], ContentPartToolCall)
        assert response_parts[1].name == "search_files"
        assert isinstance(response_parts[2], ContentPartFinishReason)

    def test_invalid_role_conversion(self):
        """Test that an error is raised for invalid roles."""
        # Create a non-existent role (this will be caught by type checking in real code)
        invalid_role = "INVALID_ROLE"

        # Verify that a ValueError is raised when attempting to convert
        with self.assertRaises(ValueError):
            list(
                self.converter.create_history_messages(
                    invalid_role,  # type: ignore
                    [ContentPartText(text="Test content")],
                ),
            )

    def test_roles_mapping(self):
        """Test that all roles are properly mapped."""
        # Test that all expected roles have mappings
        assert _ROLES[Role.SYSTEM] == "system"
        assert _ROLES[Role.CONTEXT] == "user"
        assert _ROLES[Role.USER] == "user"
        assert _ROLES[Role.MODEL] == "assistant"
        assert _ROLES[Role.TOOL] == "tool"

        # Test that all roles are mapped
        for role in Role:
            assert role in _ROLES, f"Role {role} missing from _ROLES mapping"


if __name__ == "__main__":
    unittest.main()
