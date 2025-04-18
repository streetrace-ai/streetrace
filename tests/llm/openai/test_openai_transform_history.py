"""
Unit tests for OpenAI's history transformation functions.
"""

import json
import unittest
from unittest.mock import patch

from streetrace.llm.openai.impl import OpenAI
from streetrace.llm.wrapper import (
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Message,
    Role,
    ToolCallResult, # Added import
    ToolOutput,     # Added import
)


class TestOpenAIHistory(unittest.TestCase):
    """Test cases for OpenAI's history transformation functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a sample history object
        self.history = History(
            system_message="You are a helpful assistant.",
            context="This is some context information.",
        )

        # Add some messages to the history
        self.history.add_message(
            Role.USER, [ContentPartText(text="Hello, how are you?")]
        )
        self.history.add_message(
            Role.MODEL,
            [
                ContentPartText(text="I'm doing well, thank you for asking!"),
                ContentPartToolCall(
                    id="tool-call-1",
                    name="search_files",
                    arguments={
                        "pattern": "*.py",
                        "search_string": "def transform_history",
                    },
                ),
            ],
        )

        # Define the raw result data
        raw_result_data = {"result": ["file.py:10:def transform_history"]}

        # Create the ToolCallResult object - assume success for tool results
        tool_call_result = ToolCallResult.ok(
            output=raw_result_data # Use the .ok() factory method
        )

        # Add a message with the correctly structured tool result
        self.history.add_message(
            Role.TOOL, # OpenAI uses TOOL role for results
            [
                ContentPartToolResult(
                    id="tool-call-1",
                    name="search_files", # Name is optional for result, but keep for consistency
                    content=tool_call_result # Assign the ToolCallResult object
                )
            ],
        )

    @patch("streetrace.llm.openai.converter.chat") # Correct patch path
    def test_transform_history_structure(self, mock_chat):
        """
        Test the structural integrity of the history transformation.
        This test focuses on ensuring the correct structure is maintained
        without relying on exact implementation details of the OpenAI SDK.
        """
        # Create a mock implementation for the OpenAI provider
        openai_provider = OpenAI()

        # Expected provider history (adjust based on actual converter output)
        # The converter will likely structure this differently, e.g., tool result content
        # might be a simple string or JSON string depending on implementation.
        expected_provider_history = [
            {
                "role": "system",
                "content": "You are a helpful assistant.", # System message usually plain text
            },
            {
                "role": "user",
                "content": "This is some context information.", # Context as user message
            },
            {
                "role": "user",
                "content": "Hello, how are you?", # User message plain text
            },
            {
                "role": "assistant",
                "content": "I'm doing well, thank you for asking!", # Assistant text part
                "tool_calls": [
                    {
                        "id": "tool-call-1",
                        "type": "function", # OpenAI tool calls have type
                        "function": {
                            "name": "search_files",
                            "arguments": json.dumps( # Arguments are JSON strings
                                {
                                    "pattern": "*.py",
                                    "search_string": "def transform_history",
                                }
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "tool-call-1",
                # Content of tool result is typically a JSON string of the ToolCallResult output
                "content": json.dumps({
                    "type": "text",
                    "content": {"result": ["file.py:10:def transform_history"]}
                })
            },
        ]

        # Mock the adapter's from_history method
        with patch.object(
            openai_provider._adapter,
            "from_history",
            return_value=expected_provider_history,
        ) as mock_from_history:
            provider_history = openai_provider.transform_history(self.history)

            # Check that the adapter was called with the original history
            mock_from_history.assert_called_once_with(self.history)

            # Validate the structure matches what the mock returned
            self.assertEqual(provider_history, expected_provider_history)
            self.assertEqual(len(provider_history), 5)
            self.assertEqual(provider_history[0]["role"], "system")
            self.assertEqual(provider_history[1]["role"], "user") # Context message
            self.assertEqual(provider_history[2]["role"], "user") # User message
            self.assertEqual(provider_history[3]["role"], "assistant")
            self.assertEqual(provider_history[4]["role"], "tool")

            # Check content of messages (basic checks, relies on mocked return value)
            self.assertEqual(provider_history[0]["content"], "You are a helpful assistant.")
            self.assertEqual(provider_history[1]["content"], "This is some context information.")
            self.assertEqual(provider_history[2]["content"], "Hello, how are you?")
            self.assertEqual(provider_history[3]["content"], "I'm doing well, thank you for asking!")

            # Check tool call in assistant message
            self.assertEqual(provider_history[3]["tool_calls"][0]["id"], "tool-call-1")
            self.assertEqual(provider_history[3]["tool_calls"][0]["function"]["name"], "search_files")

            # Check tool result
            self.assertEqual(provider_history[4]["tool_call_id"], "tool-call-1")
            # Compare the content (assuming it's JSON string of the ToolOutput)
            expected_tool_output = {
                "type": "text",
                "content": {"result": ["file.py:10:def transform_history"]}
            }
            self.assertEqual(json.loads(provider_history[4]["content"]), expected_tool_output)


    @patch("streetrace.llm.openai.converter.chat") # Correct patch path
    def test_update_history_structure(self, mock_chat):
        """
        Test the update_history method's structural integrity.
        Focuses on conversion from provider format to common format.
        """
        openai_provider = OpenAI()

        # Provider history (matching the format expected by the converter)
        provider_history = [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": "This is some context information.",
            },
            {
                "role": "user",
                "content": "Hello, how are you?",
            },
            {
                "role": "assistant",
                "content": "I'm doing well, thank you for asking!",
                "tool_calls": [
                    {
                        "id": "tool-call-1",
                        "type": "function",
                        "function": {
                            "name": "search_files",
                            "arguments": json.dumps(
                                {
                                    "pattern": "*.py",
                                    "search_string": "def transform_history",
                                }
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "tool-call-1",
                "content": json.dumps({"result": ["file.py:10:def transform_history"]})
            },
        ]

        # Expected History.conversation after conversion (Context is handled separately)
        expected_conversation = [
            Message(
                role=Role.USER, content=[ContentPartText(text="Hello, how are you?")]
            ),
            Message(
                role=Role.MODEL,
                content=[
                    ContentPartText(text="I'm doing well, thank you for asking!"),
                    ContentPartToolCall(
                        id="tool-call-1",
                        name="search_files",
                        arguments={
                            "pattern": "*.py",
                            "search_string": "def transform_history",
                        },
                    ),
                ],
            ),
            Message(
                role=Role.TOOL,
                content=[
                    ContentPartToolResult(
                        id="tool-call-1",
                        name="search_files", # Name comes from the original call
                        content=ToolCallResult.ok(output={"result": ["file.py:10:def transform_history"]}) # Correct structure
                    )
                ],
            ),
        ]

        # Mock the adapter's to_history method
        with patch.object(
            openai_provider._adapter, "to_history", return_value=expected_conversation
        ) as mock_to_history:
            # Create a new history with a different context
            clean_history = History(context="New context info", system_message="Sys message")

            # Update the history
            openai_provider.update_history(provider_history, clean_history)

            # Verify the adapter was called correctly
            mock_to_history.assert_called_once_with(provider_history)

            # Check that the history object was updated as expected
            self.assertEqual(clean_history.context, "New context info") # Context preserved
            self.assertEqual(clean_history.system_message, "Sys message") # System msg preserved
            self.assertEqual(clean_history.conversation, expected_conversation)
            self.assertEqual(len(clean_history.conversation), 3)

            # Optional: More detailed checks on the conversation content if needed
            user_msg = clean_history.conversation[0]
            self.assertEqual(user_msg.role, Role.USER)
            self.assertEqual(user_msg.content[0].text, "Hello, how are you?")

            model_msg = clean_history.conversation[1]
            self.assertEqual(model_msg.role, Role.MODEL)
            self.assertEqual(model_msg.content[0].text, "I'm doing well, thank you for asking!")
            self.assertIsInstance(model_msg.content[1], ContentPartToolCall)
            self.assertEqual(model_msg.content[1].name, "search_files")

            tool_msg = clean_history.conversation[2]
            self.assertEqual(tool_msg.role, Role.TOOL)
            self.assertIsInstance(tool_msg.content[0], ContentPartToolResult)
            self.assertEqual(tool_msg.content[0].id, "tool-call-1")
            self.assertTrue(tool_msg.content[0].content.success)
            self.assertEqual(tool_msg.content[0].content.output.content, {"result": ["file.py:10:def transform_history"]})


    def test_transform_history_no_context(self):
        """Test transforming history without context."""
        # Create a history without context
        history = History(system_message="You are helpful.", context="")
        history.add_message(Role.USER, [ContentPartText(text="Hello")])

        openai_provider = OpenAI()

        # Expected provider history (no context user message)
        expected_provider_history = [
            {"role": "system", "content": "You are helpful."}, # System message
            {"role": "user", "content": "Hello"},           # User message
        ]

        # Mock the adapter's from_history method
        with patch.object(
            openai_provider._adapter,
            "from_history",
            return_value=expected_provider_history,
        ) as mock_from_history:
            provider_history = openai_provider.transform_history(history)

            # Verify the adapter was called
            mock_from_history.assert_called_once_with(history)

            # Check that the structure matches the mock return
            self.assertEqual(provider_history, expected_provider_history)
            self.assertEqual(len(provider_history), 2)
            self.assertEqual(provider_history[0]["role"], "system")
            self.assertEqual(provider_history[1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
