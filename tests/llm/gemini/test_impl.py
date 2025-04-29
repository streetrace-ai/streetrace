"""Unit tests for Gemini AI Provider Implementation.

This module contains tests for the Gemini implementation of the LLMAPI interface.
"""

import os
import unittest
from unittest.mock import MagicMock, patch, call

from streetrace.llm.gemini.impl import Gemini, ProviderHistory
from streetrace.llm.wrapper import (
    ContentPart,
    ContentPartText,
    ContentPartToolCall,
    History,
    Message,
    Role,
)


class TestGeminiImpl(unittest.TestCase):
    """Tests for Gemini implementation of LLMAPI."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch the google.genai imports
        self.genai_patcher = patch('streetrace.llm.gemini.impl.genai')
        self.mock_genai = self.genai_patcher.start()

        # Create a mock client
        self.mock_client = MagicMock()
        self.mock_genai.Client.return_value = self.mock_client

        # Create the Gemini instance with mocked dependencies
        self.gemini = Gemini()

        # Mock the adapter
        self.mock_adapter = MagicMock()
        self.gemini._adapter = self.mock_adapter

        # Mock environment variable
        self.env_patcher = patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key"})
        self.env_patcher.start()

    def tearDown(self):
        """Tear down test fixtures."""
        self.genai_patcher.stop()
        self.env_patcher.stop()

    def test_initialize_client(self):
        """Test client initialization with API key."""
        # Call the method
        client = self.gemini.initialize_client()

        # Verify the client was initialized with the API key
        self.mock_genai.Client.assert_called_once_with(api_key="test-api-key")
        assert client == self.mock_client

    def test_initialize_client_missing_api_key(self):
        """Test client initialization fails without API key."""
        # Remove the API key from environment
        with patch.dict(os.environ, {}, clear=True):
            # Verify exception is raised
            with self.assertRaises(ValueError):
                self.gemini.initialize_client()

    def test_transform_history(self):
        """Test transformation of history to Gemini format."""
        # Mock the adapter's create_provider_history method
        expected_provider_history = [MagicMock(), MagicMock()]
        self.mock_adapter.create_provider_history.return_value = expected_provider_history

        # Create a history with messages
        history = History(
            system_message="You are a helpful assistant",
            context="This is context",
        )

        # Add a message
        history.add_message(
            Role.USER,
            [ContentPartText(text="Hello, Gemini")]
        )

        # Convert to provider history
        provider_history = self.gemini.transform_history(history)

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
            Message(
                role=Role.USER,
                content=[ContentPartText(text="New message")]
            ),
            Message(
                role=Role.MODEL,
                content=[ContentPartText(text="Model response")]
            ),
        ]

        # Append to history
        self.gemini.append_history(provider_history, messages)

        # Verify the adapter was called and items appended
        self.mock_adapter.to_provider_history_items.assert_called_once_with(messages)
        assert provider_history == mock_items

    def test_transform_tools(self):
        """Test transformation of tools to Gemini format."""
        # Set up the Gemini types to return mock objects
        self.mock_genai.types.Schema.return_value = MagicMock()
        self.mock_genai.types.FunctionDeclaration.return_value = MagicMock()

        # Need to patch the transform_tools method itself to verify the result
        original_transform = self.gemini.transform_tools

        # Create tool definition
        tools = [
            {
                "function": {
                    "name": "search_files",
                    "description": "Search for files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "Pattern"}
                        },
                        "required": ["pattern"]
                    }
                }
            }
        ]

        # Test that the method doesn't raise exceptions
        try:
            result = original_transform(tools)
            # Just verify it returns a list with one item
            assert isinstance(result, list)
            assert len(result) == 1
        except Exception as e:
            self.fail(f"transform_tools raised an unexpected exception: {e}")

    def test_pretty_print(self):
        """Test the pretty print formatting of content."""
        # Create mock content
        mock_part = MagicMock()
        mock_part.__dict__ = {"text": "Hello, world"}

        mock_content = MagicMock()
        mock_content.role = "user"
        mock_content.parts = [mock_part]

        contents = [mock_content]

        # Get pretty print output
        output = self.gemini.pretty_print(contents)

        # Verify output contains expected information
        assert "Content 1:" in output
        assert "user" in output
        assert "Hello, world" in output

    def test_manage_conversation_history_within_limits(self):
        """Test conversation history management when within token limits."""
        # Setup mock client and token count
        mock_count_tokens = MagicMock()
        mock_count_tokens.total_tokens = 1000  # Below limit
        self.mock_client.models.count_tokens.return_value = mock_count_tokens

        # Create mock messages
        messages = [MagicMock() for _ in range(5)]

        # Call method
        result = self.gemini.manage_conversation_history(messages, max_tokens=2000)

        # Verify no pruning occurred and result is True
        assert result is True
        assert len(messages) == 5  # Original count preserved

    def test_manage_conversation_history_exceeding_limits(self):
        """Test conversation history management when exceeding token limits."""
        # Setup mock client and token counts
        mock_count_tokens1 = MagicMock()
        mock_count_tokens1.total_tokens = 3000  # Above limit

        mock_count_tokens2 = MagicMock()
        mock_count_tokens2.total_tokens = 1500  # Below limit

        self.mock_client.models.count_tokens.side_effect = [
            mock_count_tokens1, mock_count_tokens2
        ]

        # Create mock messages (more than 3 to trigger pruning)
        messages = [MagicMock() for _ in range(10)]

        # Call method
        result = self.gemini.manage_conversation_history(messages, max_tokens=2000)

        # Verify pruning occurred and result is True
        assert result is True
        assert len(messages) < 10  # Should be pruned

    # @patch('google.genai.types.AutomaticFunctionCallingConfig')
    # @patch('google.genai.types.FunctionCallingConfig')
    # @patch('google.genai.types.FunctionCallingConfigMode')
    # @patch('google.genai.types.DynamicRetrievalConfigMode')
    def test_generate(self):
        """Test generation method with tools."""
        # Mock the adapter's get_response_parts method
        expected_response_parts = [ContentPartText(text="Generated response")]
        self.mock_adapter.get_response_parts.return_value = expected_response_parts

        # Mock the types module with simpler approach
        mock_generate_config = MagicMock()
        self.mock_genai.types.GenerateContentConfig.return_value = mock_generate_config
        mock_generate_config.return_value = mock_generate_config

        # Create messages and tools
        messages = [MagicMock()]
        gemini_tools = [MagicMock()]

        # Mock generate_content response
        mock_response = MagicMock()
        self.mock_client.models.generate_content.return_value = mock_response

        # Call generate method
        response_parts = list(self.gemini.generate(
            client=self.mock_client,
            model_name="gemini-test-model",
            system_message="You are a helpful assistant",
            messages=messages,
            tools=gemini_tools,
        ))

        # Verify generate_content was called
        self.mock_client.models.generate_content.assert_called_once()
        call_args = self.mock_client.models.generate_content.call_args
        assert call_args[1]["model"] == "gemini-test-model"
        assert call_args[1]["contents"] == messages

        # Verify response processing
        self.mock_adapter.get_response_parts.assert_called_once_with(mock_response)
        assert response_parts == expected_response_parts


if __name__ == "__main__":
    unittest.main()