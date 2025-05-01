"""Unit tests for Ollama AI Provider Implementation.

This module contains tests for the Ollama implementation of the LLMAPI interface.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

import pytest

from streetrace.llm.ollama.converter import OllamaHistoryConverter
from streetrace.llm.ollama.impl import MAX_TOKENS, MODEL_NAME, Ollama
from streetrace.llm.wrapper import (
    ContentPartText,
    History,
    Message,
    Role,
)


class TestOllamaImpl(unittest.TestCase):
    """Tests for Ollama implementation of LLMAPI."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch the ollama module
        self.ollama_patcher = patch("streetrace.llm.ollama.impl.ollama")
        self.mock_ollama = self.ollama_patcher.start()

        # Create a mock client
        self.mock_client = MagicMock()
        self.mock_ollama.Client.return_value = self.mock_client

        # Mock the adapter
        self.mock_adapter = MagicMock(spec=OllamaHistoryConverter)

        # Create the Ollama instance with mocked dependencies
        self.ollama = Ollama(self.mock_adapter)

        # Set default environment variables
        self.env_patcher = patch.dict(
            os.environ,
            {"OLLAMA_API_URL": "http://localhost:11434"},
        )
        self.env_patcher.start()

        # Patch the isinstance check to avoid the type error
        self.isinstance_patcher = patch("streetrace.llm.ollama.impl.isinstance")
        self.mock_isinstance = self.isinstance_patcher.start()
        # Default behavior is to return False for ChatResponse check
        self.mock_isinstance.return_value = False

    def tearDown(self):
        """Tear down test fixtures."""
        self.ollama_patcher.stop()
        self.env_patcher.stop()
        self.isinstance_patcher.stop()

    def test_initialize_client(self):
        """Test client initialization with default URL."""
        # Call the method
        client = self.ollama.initialize_client()

        # Verify the client was initialized with the correct URL
        self.mock_ollama.Client.assert_called_once_with(host="http://localhost:11434")
        assert client == self.mock_client

    def test_initialize_client_custom_url(self):
        """Test client initialization with custom URL."""
        # Set custom URL in environment
        with patch.dict(os.environ, {"OLLAMA_API_URL": "http://custom:8000"}):
            # Call the method
            client = self.ollama.initialize_client()

            # Verify the client was initialized with the custom URL
            self.mock_ollama.Client.assert_called_once_with(host="http://custom:8000")
            assert client == self.mock_client

    def test_transform_history(self):
        """Test transformation of history to Ollama format."""
        # Mock the adapter's create_provider_history method
        expected_provider_history = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ]
        self.mock_adapter.create_provider_history.return_value = (
            expected_provider_history
        )

        # Create a history with messages
        history = History(
            system_message="You are a helpful assistant",
            context="Context information",
        )

        # Add a message
        history.add_message(Role.USER, [ContentPartText(text="Hello")])

        # Convert to provider history
        provider_history = self.ollama.transform_history(history)

        # Verify the transformation
        assert provider_history == expected_provider_history
        self.mock_adapter.create_provider_history.assert_called_once_with(history)

    def test_append_history(self):
        """Test appending messages to provider history."""
        # Create provider history
        provider_history = []

        # Mock the adapter's to_provider_history_items method
        mock_items = [
            {"role": "user", "content": "New message"},
            {"role": "assistant", "content": "Model response"},
        ]
        self.mock_adapter.to_provider_history_items.return_value = mock_items

        # Create messages to append
        messages = [
            Message(role=Role.USER, content=[ContentPartText(text="New message")]),
            Message(role=Role.MODEL, content=[ContentPartText(text="Model response")]),
        ]

        # Append to history
        self.ollama.append_history(provider_history, messages)

        # Verify the adapter was called and items appended
        self.mock_adapter.to_provider_history_items.assert_called_once_with(messages)
        assert provider_history == mock_items

    def test_transform_tools(self):
        """Test transformation of tools to Ollama format."""
        # Create tool definition
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

        # Call the method
        result = self.ollama.transform_tools(tools)

        # Verify the result (Ollama uses the same format as OpenAI)
        assert result == tools

    def test_pretty_print(self):
        """Test the pretty print formatting of content."""
        # Create messages in Ollama format
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello, how are you?"},
            {
                "role": "assistant",
                "content": "I'm doing well!",
                "tool_calls": [{"function": {"name": "search_files"}}],
            },
            {"role": "tool", "function": {"name": "search_files", "arguments": "{}"}},
        ]

        # Get pretty print output
        output = self.ollama.pretty_print(messages)

        # Verify output contains expected information
        assert "Message 1:" in output
        assert "system: You are a helpful assistant" in output
        assert "Message 2:" in output
        assert "user: Hello, how are you?" in output
        assert "Message 3:" in output
        assert "assistant: I'm doing well!" in output
        assert "Message 4:" in output
        assert "tool: search_files" in output

    def test_manage_conversation_history_within_limits(self):
        """Test conversation history management when within token limits."""
        # Create mock messages that are within limits
        # (simulating small messages with estimated tokens well within MAX_TOKENS)
        messages = [{"role": "system", "content": "You are a helpful assistant"}]
        for i in range(5):
            messages.append({"role": "user", "content": f"Short message {i}"})
            messages.append({"role": "assistant", "content": f"Short reply {i}"})

        # Call method
        result = self.ollama.manage_conversation_history(
            messages,
            max_tokens=MAX_TOKENS,
        )

        # Verify no pruning occurred and result is True
        assert result is True
        assert (
            len(messages) == 11
        )  # Original count preserved (1 system + 5*2 exchanges)

    def test_manage_conversation_history_exceeding_limits(self):
        """Test conversation history management when exceeding token limits."""
        # Create a large set of messages to force pruning
        messages = [{"role": "system", "content": "You are a helpful assistant"}]

        # Make large content
        long_content = "x" * (MAX_TOKENS * 4)  # Ensure it exceeds the token limit

        # Add to messages
        messages.extend(
            [{"role": "user", "content": f"{long_content} {i}"} for i in range(10)],
        )

        # Keep track of original message count
        original_count = len(messages)

        # Call method with logger patched to avoid actual logging
        with patch("streetrace.llm.ollama.impl.logger"):
            self.ollama.manage_conversation_history(
                messages,
                max_tokens=MAX_TOKENS,
            )

        # Verify that pruning occurred
        assert len(messages) < original_count
        # The first message (system) should be preserved
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"

    def test_manage_conversation_history_error_handling(self):
        """Test error handling in conversation history management."""
        # Create a situation that will cause an exception
        with patch("streetrace.llm.ollama.impl.logger") as mock_logging:
            # Use a mocked list that raises an exception when accessed
            mock_messages = MagicMock()
            mock_messages.__len__.return_value = 5
            mock_messages.__iter__.side_effect = Exception("Test exception")

            # Call method
            result = self.ollama.manage_conversation_history(
                mock_messages,
                max_tokens=MAX_TOKENS,
            )

            # Verify that an exception was logged and method returned False
            assert result is False
            mock_logging.exception.assert_called_once()

    def test_generate_with_single_response(self):
        """Test generation with a single response (non-streaming)."""
        # Set up mock to indicate we have a ChatResponse
        self.mock_isinstance.return_value = True

        # Mock response parts
        expected_response_parts = [ContentPartText(text="Generated response")]
        self.mock_adapter.get_response_parts.return_value = expected_response_parts

        # Create messages and tools
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello, assistant"},
        ]
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

        # Mock chat response
        mock_response = MagicMock()
        self.mock_client.chat.return_value = mock_response

        # Call generate method
        response_parts = list(
            self.ollama.generate(
                client=self.mock_client,
                model_name="llama3:8b",
                system_message="You are a helpful assistant",
                messages=messages,
                tools=tools,
            ),
        )

        # Verify chat was called with correct arguments
        self.mock_client.chat.assert_called_once_with(
            model="llama3:8b",
            messages=messages,
            tools=tools,
            stream=False,
        )

        # Verify response was processed correctly
        self.mock_isinstance.assert_called_once()
        self.mock_adapter.get_response_parts.assert_called_once_with(mock_response)
        assert response_parts == expected_response_parts

    def test_generate_with_streaming(self):
        """Test generation with streaming responses."""
        # Set up mock to indicate we don't have a ChatResponse (i.e., we have a stream)
        self.mock_isinstance.return_value = False

        # Create mock stream responses
        stream_item1 = MagicMock()
        stream_item2 = MagicMock()
        mock_stream = [stream_item1, stream_item2]
        self.mock_client.chat.return_value = mock_stream

        # Set up response parts for each stream item
        self.mock_adapter.get_response_parts.side_effect = [
            [ContentPartText(text="First part")],
            [ContentPartText(text="Second part")],
        ]

        # Create messages and tools
        messages = [{"role": "user", "content": "Hello"}]
        tools = []

        # Call generate method
        response_parts = list(
            self.ollama.generate(
                client=self.mock_client,
                model_name="llama3:8b",
                system_message="You are a helpful assistant",
                messages=messages,
                tools=tools,
            ),
        )

        # Verify chat was called
        self.mock_client.chat.assert_called_once()

        # Verify response parts were collected from both stream items
        assert len(response_parts) == 2
        assert response_parts[0].text == "First part"
        assert response_parts[1].text == "Second part"
        assert self.mock_adapter.get_response_parts.call_count == 2

    def test_generate_with_default_model(self):
        """Test generation with default model when no model name provided."""
        # Mock response parts
        self.mock_adapter.get_response_parts.return_value = [
            ContentPartText(text="Response"),
        ]

        # Create messages and empty tools
        messages = [{"role": "user", "content": "Hello"}]
        tools = []

        # Mock chat response
        mock_response = MagicMock()
        self.mock_client.chat.return_value = mock_response

        # Call generate with no model name
        list(
            self.ollama.generate(
                client=self.mock_client,
                model_name=None,
                system_message="You are a helpful assistant",
                messages=messages,
                tools=tools,
            ),
        )

        # Verify default model was used
        self.mock_client.chat.assert_called_once_with(
            model=MODEL_NAME,  # Should use the default model
            messages=messages,
            tools=tools,
            stream=False,
        )

    def test_generate_with_retries(self):
        """Test generation with retries on failure."""
        # Mock the adapter's get_response_parts method
        self.mock_adapter.get_response_parts.return_value = [
            ContentPartText(text="Response"),
        ]

        # Create messages and empty tools
        messages = [{"role": "user", "content": "Hello"}]
        tools = []

        # Mock chat to fail twice then succeed
        self.mock_client.chat.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            MagicMock(),  # Success on third try
        ]

        # Call generate method with patched logging
        with patch("streetrace.llm.ollama.impl.logger") as mock_logging:
            list(
                self.ollama.generate(
                    client=self.mock_client,
                    model_name="llama3:8b",
                    system_message="You are a helpful assistant",
                    messages=messages,
                    tools=tools,
                ),
            )

            # Verify chat was called 3 times
            assert self.mock_client.chat.call_count == 3

            # Verify warnings were logged for the retries
            assert mock_logging.warning.call_count == 2

    def test_generate_max_retries_exceeded(self):
        """Test generation when max retries are exceeded."""
        # Create messages and empty tools
        messages = [{"role": "user", "content": "Hello"}]
        tools = []

        # Mock chat to always fail
        self.mock_client.chat.side_effect = Exception("Persistent failure")

        # Call generate method and expect an exception
        with patch("streetrace.llm.ollama.impl.logger") as mock_logging:
            with pytest.raises(Exception, match="Persistent failure"):
                list(
                    self.ollama.generate(
                        client=self.mock_client,
                        model_name="llama3:8b",
                        system_message="You are a helpful assistant",
                        messages=messages,
                        tools=tools,
                    ),
                )

            # Verify chat was called max_retries times (3)
            assert self.mock_client.chat.call_count == 3

            # Verify an exception was logged
            mock_logging.exception.assert_called_once()


if __name__ == "__main__":
    unittest.main()
