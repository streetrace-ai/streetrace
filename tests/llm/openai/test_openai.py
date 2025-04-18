import unittest
from unittest.mock import MagicMock, patch

from streetrace.llm.openai.impl import (
    initialize_client,
    manage_conversation_history,
    transform_tools,
)


class TestOpenAI(unittest.TestCase):
    """Test cases for the OpenAI integration."""

    def test_transform_tools(self):
        """Test the transformation of tools from common format to OpenAI format."""
        # Sample tool in common format
        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
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
            }
        ]

        # Transform to OpenAI format
        openai_tools = transform_tools(tools)

        # Verify the transformation
        self.assertEqual(len(openai_tools), 1)
        self.assertEqual(openai_tools[0]["type"], "function")
        self.assertEqual(openai_tools[0]["function"]["name"], "test_tool")
        self.assertEqual(openai_tools[0]["function"]["description"], "A test tool")
        self.assertEqual(openai_tools[0]["function"]["parameters"]["type"], "object")
        self.assertEqual(
            len(openai_tools[0]["function"]["parameters"]["properties"]), 2
        )
        self.assertEqual(
            openai_tools[0]["function"]["parameters"]["required"], ["param1"]
        )

    def test_manage_conversation_history_within_limits(self):
        """Test that conversation history management leaves messages intact when within limits."""
        conversation_history = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User message 1"},
            {"role": "assistant", "content": "Assistant message 1"},
        ]

        # The estimated token count will be well below the limit
        result = manage_conversation_history(conversation_history, max_tokens=100000)

        # Verify that the history is unchanged and the function returns True
        self.assertTrue(result)
        self.assertEqual(len(conversation_history), 3)
        self.assertEqual(conversation_history[0]["content"], "System message")
        self.assertEqual(conversation_history[1]["content"], "User message 1")
        self.assertEqual(conversation_history[2]["content"], "Assistant message 1")

    def test_manage_conversation_history_pruning(self):
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

        # The estimated token count will exceed the limit due to the large message
        result = manage_conversation_history(conversation_history, max_tokens=100)

        # Verify that the history is pruned and the function returns True
        self.assertTrue(result)
        self.assertLess(len(conversation_history), 5)  # Should have fewer items now
        self.assertEqual(
            conversation_history[0]["content"], "System message"
        )  # System message should be preserved

    @patch("os.environ.get")
    def test_initialize_client_missing_api_key(self, mock_get):
        """Test that initialize_client raises an error when API key is missing."""
        mock_get.return_value = None

        with self.assertRaises(ValueError) as context:
            initialize_client()

        self.assertIn(
            "OPENAI_API_KEY environment variable not set", str(context.exception)
        )

    @patch("os.environ.get")
    @patch("openai_client.OpenAI")
    def test_initialize_client_with_api_key(self, mock_openai, mock_get):
        """Test that initialize_client creates a client when API key is present."""
        mock_get.side_effect = lambda key, default=None: {
            "OPENAI_API_KEY": "test_api_key",
            "OPENAI_API_BASE": None,
        }.get(key, default)

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        client = initialize_client()

        self.assertEqual(client, mock_client)
        mock_openai.assert_called_once_with(api_key="test_api_key")

    @patch("os.environ.get")
    @patch("openai_client.OpenAI")
    def test_initialize_client_with_custom_base_url(self, mock_openai, mock_get):
        """Test that initialize_client uses custom base URL when provided."""
        mock_get.side_effect = lambda key, default=None: {
            "OPENAI_API_KEY": "test_api_key",
            "OPENAI_API_BASE": "https://custom-openai-endpoint.com",
        }.get(key, default)

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        client = initialize_client()

        self.assertEqual(client, mock_client)
        mock_openai.assert_called_once_with(
            api_key="test_api_key", base_url="https://custom-openai-endpoint.com"
        )


if __name__ == "__main__":
    unittest.main()
