"""
Unit tests for Claude's history transformation functions.
"""

import json
import unittest
from llm.claude import Claude, _from_part
from llm.wrapper import History, ContentPartText, ContentPartToolCall, ContentPartToolResult

_CLAUDE_HISTORY = """[
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "This is some context information."
            }
        ]
    },
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Hello, how are you?"
            }
        ]
    },
    {
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "I'm doing well, thank you for asking!"
            },
            {
                "type": "tool_use",
                "id": "tool-call-1",
                "name": "search_files",
                "input": {
                    "pattern": "*.py",
                    "search_string": "def transform_history"
                }
            }
        ]
    },
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "tool-call-1",
                "content": "{\\"result\\": [\\"file.py:10:def transform_history\\"]}"
            }
        ]
    }
]"""

class TestClaudeHistory(unittest.TestCase):
    """Test cases for Claude's history transformation functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.claude = Claude()

        # Create a sample history object
        self.history = History(
            system_message="You are a helpful assistant.",
            context="This is some context information."
        )

        # Add some messages to the history
        self.history.add_message("user", [ContentPartText("Hello, how are you?")])
        self.history.add_message("assistant", [
            ContentPartText("I'm doing well, thank you for asking!"),
            ContentPartToolCall(
                id="tool-call-1",
                name="search_files",
                arguments={"pattern": "*.py", "search_string": "def transform_history"}
            )
        ])

        # Add a message with a tool result
        self.history.add_message("user", [
            ContentPartToolResult(
                id="tool-call-1",
                name="search_files",
                content={"result": ["file.py:10:def transform_history"]}
            )
        ])


    def test_transform_history(self):
        """Test transforming history from common format to Claude format."""
        provider_history = self.claude.transform_history(self.history)
        actual_history = json.dumps(provider_history, indent=4)
        self.assertEqual(actual_history, _CLAUDE_HISTORY)

    def test_update_history(self):
        """Test transforming history from common format to Claude format."""
        clean_history = History(None, "This is new context information.")
        self.claude.update_history(json.loads(_CLAUDE_HISTORY), clean_history)
        provider_history = self.claude.transform_history(clean_history)
        updated_history = json.dumps(provider_history, indent=4)

        self.assertEqual(clean_history.context, "This is new context information.")
        self.assertEqual(len(clean_history.conversation), 3)
        new_history = _CLAUDE_HISTORY.replace("This is some context information.", "This is new context information.")
        self.assertEqual(updated_history, new_history)

    def test_from_part(self):
        """Test converting ContentParts to Claude format."""
        # Test text part
        text_part = ContentPartText("Test text")
        claude_text = _from_part(text_part)
        self.assertEqual(claude_text.get('type'), 'text')
        self.assertEqual(claude_text.get('text'), "Test text")

        # Test tool call part
        tool_call = ContentPartToolCall(
            id="test-id",
            name="test_tool",
            arguments={"arg1": "value1"}
        )
        claude_tool_call = _from_part(tool_call)
        self.assertEqual(claude_tool_call['type'], 'tool_use')
        self.assertEqual(claude_tool_call['name'], "test_tool")
        self.assertEqual(claude_tool_call['input'], {"arg1": "value1"})

        # Test tool result part
        tool_result = ContentPartToolResult(
            id="test-id",
            name="test_tool",
            content={"result": "success"}
        )
        claude_tool_result = _from_part(tool_result)
        self.assertEqual(claude_tool_result['type'], 'tool_result')
        self.assertEqual(claude_tool_result['tool_use_id'], "test-id")
        self.assertEqual(claude_tool_result['content'], "{\"result\": \"success\"}")

    def test_transform_history_no_context(self):
        """Test transforming history without context."""
        # Create a history without context
        history = History(
            system_message="You are a helpful assistant.",
            context=""
        )
        history.add_message("user", [ContentPartText("Hello")])

        provider_history = self.claude.transform_history(history)

        # Check that there's no context message
        self.assertEqual(len(provider_history), 1)
        self.assertEqual(provider_history[0]['role'], 'user')
        self.assertEqual(provider_history[0]['content'][0]['text'], "Hello")


if __name__ == '__main__':
    unittest.main()