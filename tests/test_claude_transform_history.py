"""
Unit tests for Claude's history transformation functions.
"""

import json
import unittest
import anthropic
from llm.claude.impl import Claude
from llm.claude.converter import ClaudeConverter, ContentBlockChunkWrapper
from llm.wrapper import History, ContentPartText, ContentPartToolCall, ContentPartToolResult, Role, ToolResult

_CLAUDE_HISTORY = [
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
                "content": "{\"result\": [\"file.py:10:def transform_history\"]}"
            }
        ]
    }
]

class TestClaudeHistory(unittest.TestCase):
    """Test cases for Claude's history transformation functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.claude = Claude()
        self.converter = ClaudeConverter()

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
        self.history.add_message(Role.USER, [
            ContentPartToolResult(
                id="tool-call-1",
                name="search_files",
                content={"result": ["file.py:10:def transform_history"]}
            )
        ])


    def test_transform_history(self):
        """Test transforming history from common format to Claude format."""
        # The Claude class now delegates to the converter's from_history method
        provider_history = self.claude.transform_history(self.history)
        actual_history = json.dumps(provider_history, indent=4)
        expected_history = json.dumps(_CLAUDE_HISTORY, indent=4)
        self.assertEqual(actual_history, expected_history)

    def test_update_history(self):
        """Test updating history from Claude format to common format."""
        # Create a new history with different context
        clean_history = History(context="This is new context information.")

        # The Claude class now delegates to the converter's to_history method
        self.claude.update_history(_CLAUDE_HISTORY, clean_history)

        # Transform the updated history back to provider format for comparison
        provider_history = self.claude.transform_history(clean_history)
        updated_history = json.dumps(provider_history, indent=4)

        # Context should be preserved from the clean_history
        self.assertEqual(clean_history.context, "This is new context information.")
        self.assertEqual(len(clean_history.conversation), 3)

        # Create expected history with the new context
        expected_history = _CLAUDE_HISTORY.copy()
        expected_history[0]["content"][0]["text"] = "This is new context information."
        self.assertEqual(updated_history, json.dumps(expected_history, indent=4))

    def test_from_content_part(self):
        """Test converting ContentParts to Claude format."""
        # Test text part
        text_part = ContentPartText(text = "Test text")
        claude_text = self.converter._from_content_part(text_part)
        self.assertEqual(claude_text.get('type'), 'text')
        self.assertEqual(claude_text.get('text'), "Test text")

        # Test tool call part
        tool_call = ContentPartToolCall(
            id="test-id",
            name="test_tool",
            arguments={"arg1": "value1"}
        )
        claude_tool_call = self.converter._from_content_part(tool_call)
        self.assertEqual(claude_tool_call['type'], 'tool_use')
        self.assertEqual(claude_tool_call['name'], "test_tool")
        self.assertEqual(claude_tool_call['input'], {"arg1": "value1"})

        # Test tool result part
        tool_result = ContentPartToolResult(
            id="test-id",
            name="test_tool",
            content={"result": "success"}
        )
        claude_tool_result = self.converter._from_content_part(tool_result)
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
        history.add_message(Role.USER, [ContentPartText(text = "Hello")])

        provider_history = self.claude.transform_history(history)

        # Check that there's no context message
        self.assertEqual(len(provider_history), 1)
        self.assertEqual(provider_history[0]['role'], 'user')
        self.assertEqual(provider_history[0]['content'][0]['text'], "Hello")

    def test_content_block_chunk_wrapper(self):
        """Test the ContentBlockChunkWrapper implementation."""
        # Test text block
        text_block = anthropic.types.TextBlock(
            type="text",
            text="Hello world"
        )
        wrapper = ContentBlockChunkWrapper(text_block)
        self.assertEqual(wrapper.get_text(), "Hello world")
        self.assertEqual(wrapper.get_tool_calls(), [])

        # Test tool use block
        tool_use_block = anthropic.types.ToolUseBlock(
            type="tool_use",
            id="tool-1",
            name="search_files",
            input={"pattern": "*.py"}
        )
        wrapper = ContentBlockChunkWrapper(tool_use_block)
        self.assertEqual(wrapper.get_text(), "")
        tool_calls = wrapper.get_tool_calls()
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].id, "tool-1")
        self.assertEqual(tool_calls[0].name, "search_files")
        self.assertEqual(tool_calls[0].arguments, {"pattern": "*.py"})

    def test_to_history_item_content_blocks(self):
        """Test converting content blocks to a provider-specific message."""
        # Create test chunks
        text_chunk = ContentBlockChunkWrapper(
            anthropic.types.TextBlock(
                type="text",
                text="Hello world"
            )
        )
        tool_chunk = ContentBlockChunkWrapper(
            anthropic.types.ToolUseBlock(
                type="tool_use",
                id="tool-1",
                name="search_files",
                input={"pattern": "*.py"}
            )
        )

        # Test with multiple chunks
        message = self.converter.to_history_item([text_chunk, tool_chunk])
        self.assertEqual(message['role'], 'assistant')
        self.assertEqual(len(message['content']), 2)
        self.assertEqual(message['content'][0]['type'], 'text')
        self.assertEqual(message['content'][0]['text'], 'Hello world')
        self.assertEqual(message['content'][1]['type'], 'tool_use')
        self.assertEqual(message['content'][1]['id'], 'tool-1')
        self.assertEqual(message['content'][1]['name'], 'search_files')
        self.assertEqual(message['content'][1]['input'], {'pattern': '*.py'})

    def test_to_history_item_tool_results(self):
        """Test converting tool results to a provider-specific message."""
        # Create a tool call and result
        tool_call = ContentPartToolCall(
            id="tool-1",
            name="search_files",
            arguments={"pattern": "*.py"}
        )
        tool_result = ToolResult(
            tool_call=tool_call,
            tool_result={"id": "foo", "name": "bar", "content": { "result": "file.py" }}
        )

        # Test with a tool result
        message = self.converter.to_history_item([tool_result])
        self.assertEqual(message['role'], 'user')
        self.assertEqual(len(message['content']), 1)
        self.assertEqual(message['content'][0]['type'], 'tool_result')
        self.assertEqual(message['content'][0]['tool_use_id'], 'tool-1')
        self.assertEqual(json.loads(message['content'][0]['content']), { "result": "file.py" })

        # Test with empty list
        message = self.converter.to_history_item([])
        self.assertIsNone(message)


if __name__ == '__main__':
    unittest.main()