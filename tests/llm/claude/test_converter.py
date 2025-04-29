"""Unit tests for Claude history converter.

This module contains tests for the AnthropicHistoryConverter class that converts
between Streetrace history and Claude-specific formats.
"""

import unittest
from unittest.mock import MagicMock

from streetrace.llm.claude.converter import AnthropicHistoryConverter
from streetrace.llm.wrapper import (
    ContentPartFinishReason,
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    ContentPartUsage,
    History,
    Role,
    ToolCallResult,
    ToolOutput,
)


class TestAnthropicHistoryConverter(unittest.TestCase):
    """Tests for AnthropicHistoryConverter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.converter = AnthropicHistoryConverter()

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
            Role.MODEL, [ContentPartText(text="I'm doing well, thank you for asking!")],
        )

        # Convert to provider history
        provider_history = self.converter.create_provider_history(history)

        # Verify the conversion output - system message is filtered out
        assert len(provider_history) == 3  # context, user and model messages

        # Check message roles and content
        assert provider_history[0]["role"] == "user"  # Context converted to user
        assert provider_history[1]["role"] == "user"
        assert provider_history[2]["role"] == "assistant"

        # Verify content
        assert provider_history[0]["content"][0]["type"] == "text"
        assert (
            provider_history[0]["content"][0]["text"]
            == "This is contextual information"
        )
        assert provider_history[1]["content"][0]["text"] == "Hello, how are you?"
        assert (
            provider_history[2]["content"][0]["text"]
            == "I'm doing well, thank you for asking!"
        )

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

        # Should return an empty list as system messages are not added directly in Claude
        assert provider_history == []

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
                    id="search-1",
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
        assert len(provider_history) == 2  # User and tool messages

        # Check the user message with tool call
        assert provider_history[0]["role"] == "user"
        assert len(provider_history[0]["content"]) == 2
        assert provider_history[0]["content"][0]["type"] == "text"
        assert provider_history[0]["content"][1]["type"] == "tool_use"
        assert provider_history[0]["content"][1]["name"] == "search_files"
        assert provider_history[0]["content"][1]["input"]["pattern"] == "*.py"

        # Check the tool result message (sent as user in Claude)
        assert provider_history[1]["role"] == "user"
        assert len(provider_history[1]["content"]) == 1
        assert provider_history[1]["content"][0]["type"] == "tool_result"
        assert provider_history[1]["content"][0]["tool_use_id"] == "search-1"
        assert "Found 5 files" in provider_history[1]["content"][0]["content"]

    def test_response_parsing_text(self):
        """Test parsing a simple text response from Claude."""
        # Create a mock Claude response with text content
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="This is a response from Claude"),
        ]
        mock_response.stop_reason = "end_turn"
        input_tokens = 10
        output_tokens = 5
        mock_response.usage = MagicMock(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content
        expect_response_parts_count = 3  # Text, Usage, FinishReason
        assert len(response_parts) == expect_response_parts_count
        assert isinstance(response_parts[0], ContentPartText)
        assert response_parts[0].text == "This is a response from Claude"
        assert isinstance(response_parts[1], ContentPartUsage)
        assert response_parts[1].prompt_tokens == input_tokens
        assert response_parts[1].response_tokens == output_tokens
        assert isinstance(response_parts[2], ContentPartFinishReason)
        assert response_parts[2].finish_reason == "end_turn"

    def test_empty_response(self):
        """Test handling of empty responses."""
        # Create a mock empty Claude response
        mock_response = MagicMock()
        mock_response.content = []  # Empty content

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify empty result
        assert len(response_parts) == 0

    def test_response_parsing_with_tool_call(self):
        """Test parsing a response containing a tool call."""
        # Create a mock Claude response with a tool call
        mock_response = MagicMock()
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.id = "tool-123"
        mock_tool_use.name = "search_files"
        mock_tool_use.input = {"pattern": "*.py", "search_string": "test"}

        mock_response.content = [mock_tool_use]
        mock_response.stop_reason = "tool_use"
        mock_response.usage = MagicMock(
            input_tokens=15,
            output_tokens=8,
        )

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify that the tool call was parsed correctly
        assert len(response_parts) == 3  # Tool call, usage, finish reason
        assert isinstance(response_parts[0], ContentPartToolCall)
        assert response_parts[0].name == "search_files"
        assert response_parts[0].arguments["pattern"] == "*.py"
        assert response_parts[0].arguments["search_string"] == "test"
        assert response_parts[0].id == "tool-123"
        assert isinstance(response_parts[1], ContentPartUsage)
        assert isinstance(response_parts[2], ContentPartFinishReason)

    def test_mixed_content_response(self):
        """Test parsing a response with mixed content types."""
        # Create a mock Claude response with text and tool_use
        mock_response = MagicMock()
        mock_text = MagicMock()
        mock_text.type = "text"
        mock_text.text = "Let me search for that file"

        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.id = "tool-mixed"
        mock_tool_use.name = "search_files"
        mock_tool_use.input = {"pattern": "*.py", "search_string": "test"}

        mock_response.content = [mock_text, mock_tool_use]
        mock_response.stop_reason = "tool_use"
        mock_response.usage = MagicMock(
            input_tokens=20,
            output_tokens=15,
        )

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify multiple content parts were parsed correctly
        assert len(response_parts) == 4  # Text, Tool call, Usage, Finish reason
        assert isinstance(response_parts[0], ContentPartText)
        assert response_parts[0].text == "Let me search for that file"
        assert isinstance(response_parts[1], ContentPartToolCall)
        assert response_parts[1].name == "search_files"
        assert isinstance(response_parts[2], ContentPartUsage)
        assert isinstance(response_parts[3], ContentPartFinishReason)

    def test_response_parsing_partial_usage_metadata(self):
        """Test parsing a response with partial usage metadata."""
        # Create a mock Claude response with partial usage data
        mock_response = MagicMock()
        mock_text = MagicMock()
        mock_text.type = "text"
        mock_text.text = "Response with partial usage data"

        mock_response.content = [mock_text]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 20
        mock_response.usage.output_tokens = None  # Missing output tokens

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content with default values for missing metrics
        assert len(response_parts) == 3  # Text, Usage, FinishReason
        assert response_parts[0].text == "Response with partial usage data"
        assert response_parts[1].prompt_tokens == 20
        assert response_parts[1].response_tokens == 0  # Default to 0 when None
        assert response_parts[2].finish_reason == "end_turn"

    def test_response_no_usage_no_stop_reason(self):
        """Test parsing a response with no usage metadata and no stop reason."""
        # Create a mock Claude response without usage and stop reason
        mock_response = MagicMock()
        mock_text = MagicMock()
        mock_text.type = "text"
        mock_text.text = "Simple response"

        mock_response.content = [mock_text]
        mock_response.usage = None
        mock_response.stop_reason = None

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content (should only include text)
        assert len(response_parts) == 1  # Text only
        assert response_parts[0].text == "Simple response"


if __name__ == "__main__":
    unittest.main()
