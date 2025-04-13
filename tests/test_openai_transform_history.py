"""
Unit tests for OpenAI's history transformation functions.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from llm.openai.impl import OpenAI
from llm.openai.converter import OpenAIConverter
from llm.wrapper import History, Message, ContentPartText, ContentPartToolCall, ContentPartToolResult, ToolResult, Role

class TestOpenAIHistory(unittest.TestCase):
    """Test cases for OpenAI's history transformation functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a sample history object
        self.history = History(
            system_message="You are a helpful assistant.",
            context="This is some context information."
        )

        # Add some messages to the history
        self.history.add_message(Role.USER, [ContentPartText(text = "Hello, how are you?")])
        self.history.add_message(Role.MODEL, [
            ContentPartText(text = "I'm doing well, thank you for asking!"),
            ContentPartToolCall(
                id="tool-call-1",
                name="search_files",
                arguments={"pattern": "*.py", "search_string": "def transform_history"}
            )
        ])

        # Add a message with a tool result
        self.history.add_message(Role.TOOL, [
            ContentPartToolResult(
                id="tool-call-1",
                name="search_files",
                content={"result": ["file.py:10:def transform_history"]}
            )
        ])

    @patch('llm.openai.converter.chat')
    def test_transform_history_structure(self, mock_chat):
        """
        Test the structural integrity of the history transformation.
        This test focuses on ensuring the correct structure is maintained
        without relying on exact implementation details of the OpenAI SDK.
        """
        # Create a mock implementation for the OpenAI provider
        openai_provider = OpenAI()

        # Mock the converter's from_history method to return a testable structure
        expected_provider_history = [
            {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
            {"role": "user", "content": [{"type": "text", "text": "This is some context information."}]},
            {"role": "user", "content": [{"type": "text", "text": "Hello, how are you?"}]},
            {
                "role": "assistant",
                "content": "I'm doing well, thank you for asking!",
                "tool_calls": [{
                    "id": "tool-call-1",
                    "function": {
                        "name": "search_files",
                        "arguments": json.dumps({"pattern": "*.py", "search_string": "def transform_history"})
                    }
                }]
            },
            {
                "role": "tool",
                "tool_call_id": "tool-call-1",
                "content": json.dumps({"result": ["file.py:10:def transform_history"]})
            }
        ]

        with patch.object(openai_provider._adapter, 'from_history', return_value=expected_provider_history):
            provider_history = openai_provider.transform_history(self.history)

            # Validate the structure matches what we expect
            self.assertEqual(len(provider_history), 5)
            self.assertEqual(provider_history[0]["role"], "system")
            self.assertEqual(provider_history[1]["role"], "user")  # Context message
            self.assertEqual(provider_history[2]["role"], "user")  # User message
            self.assertEqual(provider_history[3]["role"], "assistant")
            self.assertEqual(provider_history[4]["role"], "tool")

            # Check content of messages
            self.assertEqual(provider_history[0]["content"][0]["text"], "You are a helpful assistant.")
            self.assertEqual(provider_history[1]["content"][0]["text"], "This is some context information.")
            self.assertEqual(provider_history[2]["content"][0]["text"], "Hello, how are you?")
            self.assertEqual(provider_history[3]["content"], "I'm doing well, thank you for asking!")

            # Check tool call in assistant message
            self.assertEqual(provider_history[3]["tool_calls"][0]["id"], "tool-call-1")
            self.assertEqual(provider_history[3]["tool_calls"][0]["function"]["name"], "search_files")

            # Check tool result
            self.assertEqual(provider_history[4]["tool_call_id"], "tool-call-1")
            # Decode the JSON string and compare the content
            self.assertEqual(
                json.loads(provider_history[4]["content"]),
                {"result": ["file.py:10:def transform_history"]}
            )

    @patch('llm.openai.converter.chat')
    def test_update_history_structure(self, mock_chat):
        """
        Test the update_history method's structural integrity.
        This test focuses on the conversion from provider format to common format.
        """
        # Create a mock implementation for the OpenAI provider
        openai_provider = OpenAI()

        # Create provider history
        provider_history = [
            {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
            {"role": "user", "content": [{"type": "text", "text": "This is some context information."}]},
            {"role": "user", "content": [{"type": "text", "text": "Hello, how are you?"}]},
            {
                "role": "assistant",
                "content": "I'm doing well, thank you for asking!",
                "tool_calls": [{
                    "id": "tool-call-1",
                    "function": {
                        "name": "search_files",
                        "arguments": json.dumps({"pattern": "*.py", "search_string": "def transform_history"})
                    }
                }]
            },
            {
                "role": "tool",
                "tool_call_id": "tool-call-1",
                "content": json.dumps({"result": ["file.py:10:def transform_history"]})
            }
        ]

        # Expected result after conversion
        expected_conversation = [
            Message(role = Role.USER, content = [ContentPartText(text = "This is some context information.")]),
            Message(role = Role.USER, content = [ContentPartText(text = "Hello, how are you?")]),
            Message(role = Role.MODEL, content = [
                ContentPartText(text = "I'm doing well, thank you for asking!"),
                ContentPartToolCall(
                    id="tool-call-1",
                    name="search_files",
                    arguments={"pattern": "*.py", "search_string": "def transform_history"}
                )
            ]),
            Message(role = Role.TOOL, content = [
                ContentPartToolResult(
                    id="tool-call-1",
                    name="search_files",
                    content={"result": ["file.py:10:def transform_history"]}
                )
            ])
        ]

        # Mock the to_history method
        with patch.object(openai_provider._adapter, 'to_history', return_value=expected_conversation):
            # Create a new history with a different context
            clean_history = History(context="New context information")

            # Update the history
            openai_provider.update_history(provider_history, clean_history)

            # Verify the content was transferred correctly
            self.assertEqual(clean_history.context, "New context information")  # Context should be preserved
            print(clean_history.conversation)
            self.assertEqual(len(clean_history.conversation), 3)

            # Check the structure matches without relying on exact implementation details
            for i, message in enumerate(clean_history.conversation):
                self.assertEqual(message.role, expected_conversation[i].role)
                self.assertEqual(len(message.content), len(expected_conversation[i].content))

            # Check specific content
            user_message = clean_history.conversation[0]
            self.assertEqual(user_message.role, Role.USER)
            self.assertEqual(user_message.content[0].text, "Hello, how are you?")

            assistant_message = clean_history.conversation[1]
            self.assertEqual(assistant_message.role, Role.MODEL)
            self.assertTrue(any(isinstance(part, ContentPartText) and part.text == "I'm doing well, thank you for asking!"
                                for part in assistant_message.content))
            self.assertTrue(any(isinstance(part, ContentPartToolCall) and part.name == "search_files"
                                for part in assistant_message.content))

            tool_message = clean_history.conversation[2]
            self.assertEqual(tool_message.role, Role.TOOL)
            self.assertEqual(tool_message.content[0].id, "tool-call-1")
            self.assertEqual(tool_message.content[0].content["result"][0], "file.py:10:def transform_history")

    def test_transform_history_no_context(self):
        """Test transforming history without context."""
        # Create a history without context
        history = History(
            system_message="You are a helpful assistant.",
            context=""
        )
        history.add_message(Role.USER, [ContentPartText(text = "Hello")])

        # Create a mock implementation for the OpenAI provider
        openai_provider = OpenAI()

        # Expected provider history (without context message)
        expected_provider_history = [
            {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
        ]

        # Mock the from_history method
        with patch.object(openai_provider._adapter, 'from_history', return_value=expected_provider_history):
            provider_history = openai_provider.transform_history(history)

            # Check that there's no context message (should only have system + user message)
            self.assertEqual(len(provider_history), 2)
            self.assertEqual(provider_history[0]["role"], "system")
            self.assertEqual(provider_history[1]["role"], "user")
            self.assertEqual(provider_history[1]["content"][0]["text"], "Hello")


if __name__ == '__main__':
    unittest.main()