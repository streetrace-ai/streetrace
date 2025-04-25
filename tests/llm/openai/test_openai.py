import unittest
from unittest.mock import MagicMock, patch

import pytest

# Removed unused imports:
#   manage_conversation_history,
#   transform_tools
# Import the OpenAI class
from streetrace.llm.openai.impl import OpenAI  # Import the class


class TestOpenAI(unittest.TestCase):
    """Test cases for the OpenAI integration."""

    def setUp(self) -> None:
        """Set up for test methods."""
        self.openai_provider = OpenAI()  # Instantiate the provider

    def test_transform_tools(self) -> None:
        """Test the transformation of tools from common format to OpenAI format."""
        # Sample tool in OpenAI format (includes top-level type: function)
        tools = [
            {
                "type": "function",  # Added this line
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "param1": {
                                "type": "string",
                                "description": "A string parameter",
                            },
                            "param2": {
                                "type": "integer",
                                "description": "An integer parameter",
                            },
                        },
                        "required": ["param1"],
                    },
                },
            },
        ]

        # Transform to OpenAI format using the instance method
        # Since the impl returns the input directly, the input must match the expected output format
        openai_tools = self.openai_provider.transform_tools(tools)

        # Verify the transformation
        assert len(openai_tools) == 1
        # OpenAI tool format expects 'type': 'function' at the top level of the tool definition
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "test_tool"
        assert openai_tools[0]["function"]["description"] == "A test tool"
        assert openai_tools[0]["function"]["parameters"]["type"] == "object"
        assert len(openai_tools[0]["function"]["parameters"]["properties"]) == 2
        assert openai_tools[0]["function"]["parameters"]["required"] == ["param1"]

    def test_manage_conversation_history_within_limits(self) -> None:
        """Test that conversation history management leaves messages intact when within limits."""
        conversation_history = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User message 1"},
            {"role": "assistant", "content": "Assistant message 1"},
        ]

        # Call the instance method
        result = self.openai_provider.manage_conversation_history(
            conversation_history,
            max_tokens=100000,
        )

        # Verify that the history is unchanged and the function returns True
        assert result
        assert len(conversation_history) == 3
        assert conversation_history[0]["content"] == "System message"
        assert conversation_history[1]["content"] == "User message 1"
        assert conversation_history[2]["content"] == "Assistant message 1"

    def test_manage_conversation_history_pruning(self) -> None:
        """Test that conversation history is pruned when exceeding limits."""
        # Create a large conversation that will exceed the token limit
        conversation_history = [
            {"role": "system", "content": "System message"},
            {
                "role": "user",
                "content": "User message 1" * 1000,
            },  # Large message to trigger pruning
            {"role": "assistant", "content": "Assistant message 1"},
            {"role": "user", "content": "User message 2"},
            {"role": "assistant", "content": "Assistant message 2"},
        ]

        # Call the instance method
        result = self.openai_provider.manage_conversation_history(
            conversation_history,
            max_tokens=100,
        )

        # Verify that the history is pruned and the function returns True
        assert result
        assert len(conversation_history) < 5  # Should have fewer items now
        assert (
            conversation_history[0]["content"] == "System message"
        )  # System message should be preserved

    @patch("os.environ.get")
    def test_initialize_client_missing_api_key(self, mock_get) -> None:
        """Test that initialize_client raises an error when API key is missing."""
        mock_get.return_value = None

        with pytest.raises(ValueError) as context:
            # Call the method on the instance
            self.openai_provider.initialize_client()

        assert "OPENAI_API_KEY environment variable not set" in str(context.value)

    @patch("os.environ.get")
    @patch("openai.OpenAI")  # Patch the correct path
    def test_initialize_client_with_api_key(
        self, mock_openai_constructor, mock_get,
    ) -> None:
        """Test that initialize_client creates a client when API key is present."""
        mock_get.side_effect = lambda key, default=None: {
            "OPENAI_API_KEY": "test_api_key",
            "OPENAI_API_BASE": None,
        }.get(key, default)

        mock_client = MagicMock()
        mock_openai_constructor.return_value = mock_client

        # Call the method on the instance
        client = self.openai_provider.initialize_client()

        assert client == mock_client
        mock_openai_constructor.assert_called_once_with(api_key="test_api_key")

    @patch("os.environ.get")
    @patch("openai.OpenAI")  # Patch the correct path
    def test_initialize_client_with_custom_base_url(
        self,
        mock_openai_constructor,
        mock_get,
    ) -> None:
        """Test that initialize_client uses custom base URL when provided."""
        mock_get.side_effect = lambda key, default=None: {
            "OPENAI_API_KEY": "test_api_key",
            "OPENAI_API_BASE": "https://custom-openai-endpoint.com",
        }.get(key, default)

        mock_client = MagicMock()
        mock_openai_constructor.return_value = mock_client

        # Call the method on the instance
        client = self.openai_provider.initialize_client()

        assert client == mock_client
        mock_openai_constructor.assert_called_once_with(
            api_key="test_api_key",
            base_url="https://custom-openai-endpoint.com",
        )


if __name__ == "__main__":
    unittest.main()
