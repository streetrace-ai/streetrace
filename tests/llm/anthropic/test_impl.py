"""Unit tests for Anthropic AI Provider Implementation.

This module contains tests for the Anthropic implementation of the LLMAPI interface.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from streetrace.llm.anthropic.converter import AnthropicHistoryConverter
from streetrace.llm.anthropic.impl import Anthropic
from streetrace.llm.llmapi import RetriableError
from streetrace.llm.wrapper import (
    ContentPartText,
    History,
    Message,
    Role,
)


class TestAnthropicImpl(unittest.TestCase):
    """Tests for Anthropic implementation of LLMAPI."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch the anthropic imports
        self.anthropic_patcher = patch("streetrace.llm.anthropic.impl.anthropic")
        self.mock_anthropic = self.anthropic_patcher.start()

        # Create a mock client
        self.mock_client = MagicMock()
        self.mock_anthropic.Anthropic.return_value = self.mock_client

        # Make a proper RateLimitError
        self.mock_anthropic.RateLimitError = Exception

        # Mock the adapter
        self.mock_adapter = MagicMock(spec=AnthropicHistoryConverter)

        # Create the Anthropic instance with mocked dependencies
        self.anthropic = Anthropic(self.mock_adapter)

        # Mock environment variable
        self.env_patcher = patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-api-key"})
        self.env_patcher.start()

    def tearDown(self):
        """Tear down test fixtures."""
        self.anthropic_patcher.stop()
        self.env_patcher.stop()

    def test_initialize_client(self):
        """Test client initialization with API key."""
        # Call the method
        client = self.anthropic.initialize_client()

        # Verify the client was initialized with the API key
        self.mock_anthropic.Anthropic.assert_called_once_with(api_key="test-api-key")
        assert client == self.mock_client

    def test_initialize_client_missing_api_key(self):
        """Test client initialization fails without API key."""
        # Remove the API key from environment
        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError):
            self.anthropic.initialize_client()

    def test_transform_history(self):
        """Test transformation of history to Anthropic format."""
        # Mock the adapter's create_provider_history method
        expected_provider_history = [MagicMock(), MagicMock()]
        self.mock_adapter.create_provider_history.return_value = (
            expected_provider_history
        )

        # Create a history with messages
        history = History(
            system_message="You are a helpful assistant",
            context="This is context",
        )

        # Add a message
        history.add_user_message("Hello, Claude!")

        # Convert to provider history
        provider_history = self.anthropic.transform_history(history)

        # Verify the transformation
        assert provider_history == expected_provider_history
        self.mock_adapter.create_provider_history.assert_called_once_with(history)

    def test_append_history(self):
        """Test appending messages to provider history."""
        # Create provider history
        provider_history = []

        # Mock the adapter's to_provider_history_items method
        mock_items = [MagicMock(), MagicMock()]
        self.mock_adapter.to_provider_history_items.return_value = mock_items

        # Create messages to append
        messages = [
            Message(role=Role.USER, content=[ContentPartText(text="New message")]),
            Message(role=Role.MODEL, content=[ContentPartText(text="Model response")]),
        ]

        # Append to history
        self.anthropic.append_history(provider_history, messages)

        # Verify the adapter was called and items appended
        self.mock_adapter.to_provider_history_items.assert_called_once_with(messages)
        assert provider_history == mock_items

    def test_transform_tools(self):
        """Test transformation of tools to Anthropic format."""
        # Create tool definition in the common format
        tools = [
            {
                "function": {
                    "name": "search_files",
                    "description": "Search for files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "Pattern"},
                        },
                        "required": ["pattern"],
                    },
                },
            },
        ]

        # Transform to Anthropic format
        claude_tools = self.anthropic.transform_tools(tools)

        # Verify the transformation
        assert len(claude_tools) == 1
        assert claude_tools[0]["type"] == "custom"
        assert claude_tools[0]["name"] == "search_files"
        assert claude_tools[0]["description"] == "Search for files"
        assert claude_tools[0]["input_schema"] == tools[0]["function"]["parameters"]

    def test_pretty_print(self):
        """Test the pretty print formatting of content."""
        # Create mock content
        messages = [
            {"role": "user", "content": "Hello, world"},
            {"role": "assistant", "content": "Hello, how can I help?"},
        ]

        # Get pretty print output
        output = self.anthropic.pretty_print(messages)

        # Verify output contains expected information
        assert "Message 1:" in output
        assert "user" in output
        assert "Hello, world" in output
        assert "Message 2:" in output
        assert "assistant" in output
        assert "Hello, how can I help?" in output

    def test_manage_conversation_history_within_limits(self):
        """Test conversation history management when within token limits."""
        # Create mock messages (small enough to be within limits)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        # Call method with a large token limit
        result = self.anthropic.manage_conversation_history(messages, max_tokens=10000)

        # Verify no pruning occurred and result is True
        assert result is True
        assert len(messages) == 2  # Original count preserved

    def test_manage_conversation_history_exceeding_limits(self):
        """Test conversation history management when exceeding token limits."""
        # Create mock messages with lots of content to exceed token limits
        # Using patch to override the token estimation calculation
        with patch("streetrace.llm.anthropic.impl.sum") as mock_sum:
            # Mock the token estimation to return a large value first, and smaller after pruning
            mock_sum.side_effect = [1000000, 1000]  # Above limit, then below limit

            messages = [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello, Anthropic!"},
                {"role": "assistant", "content": "Hi there, how can I help you?"},
                {"role": "user", "content": "Tell me about Python"},
                {"role": "assistant", "content": "Python is a programming language..."},
                {"role": "user", "content": "What about JavaScript?"},
                {
                    "role": "assistant",
                    "content": "JavaScript is a web programming language...",
                },
            ]

            # Call method with a small token limit
            result = self.anthropic.manage_conversation_history(
                messages,
                max_tokens=100000,
            )

            # Verify pruning occurred and result is True
            assert result is True
            assert len(messages) < 7  # Should be pruned

    def test_generate(self):
        """Test generation method with tools."""
        # Mock the adapter's get_response_parts method
        expected_response_parts = [ContentPartText(text="Generated response")]
        self.mock_adapter.get_response_parts.return_value = expected_response_parts

        # Create messages and tools
        messages = [MagicMock()]
        claude_tools = [MagicMock()]

        # Mock messages.create response
        mock_response = MagicMock()
        self.mock_client.messages.create.return_value = mock_response

        # Call generate method
        response_parts = list(
            self.anthropic.generate(
                client=self.mock_client,
                model_name="anthropic-test-model",
                system_message="You are a helpful assistant",
                messages=messages,
                tools=claude_tools,
            ),
        )

        # Verify messages.create was called
        self.mock_client.messages.create.assert_called_once()
        call_args = self.mock_client.messages.create.call_args[1]
        assert call_args["model"] == "anthropic-test-model"
        assert call_args["system"] == "You are a helpful assistant"
        assert call_args["messages"] == messages
        assert call_args["tools"] == claude_tools

        # Verify response processing
        self.mock_adapter.get_response_parts.assert_called_once_with(mock_response)
        assert response_parts == expected_response_parts

    def test_generate_with_rate_limit_error(self) -> None:
        """Test that RateLimitError is converted to RetriableError."""
        # Create a properly formed RateLimitError
        mock_api_response = MagicMock()
        mock_api_response.status_code = 429
        mock_api_response.headers = {}
        mock_api_response.text = "Rate limit exceeded"

        rate_limit_error = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=mock_api_response,
            body={
                "error": {"message": "Rate limit exceeded", "type": "rate_limit_error"},
            },
        )

        # Configure the mock to raise RateLimitError
        self.mock_client.messages.create.side_effect = rate_limit_error

        # Call the generate method and expect RetriableError
        with pytest.raises(RetriableError) as exc_info:
            list(
                self.anthropic.generate(
                    client=self.mock_client,
                    model_name="test-model",
                    system_message="sys",
                    messages=[
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": "Hello"}],
                        },
                    ],
                    tools=[],
                ),
            )

        # Verify the RetriableError properties
        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.max_retries == 3
        assert exc_info.value.wait_seconds == 30

        # Assert that client.messages.create was called once
        self.mock_client.messages.create.assert_called_once()

    def test_generate_with_default_model(self):
        """Test generation with default model when none is specified."""
        # Mock the adapter's get_response_parts method
        self.mock_adapter.get_response_parts.return_value = [
            ContentPartText(text="Response"),
        ]

        # Mock messages.create response
        mock_response = MagicMock()
        self.mock_client.messages.create.return_value = mock_response

        # Call generate method without model_name
        list(
            self.anthropic.generate(
                client=self.mock_client,
                model_name=None,  # No model specified
                system_message="You are a helpful assistant",
                messages=[MagicMock()],
                tools=[],
            ),
        )

        # Verify default model was used
        call_args = self.mock_client.messages.create.call_args[1]
        assert (
            call_args["model"] == "claude-3-7-sonnet-20250219"
        )  # Default model in impl.py


if __name__ == "__main__":
    unittest.main()
