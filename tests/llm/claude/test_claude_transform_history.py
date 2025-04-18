"""
Unit tests for Claude's history transformation functions.
"""

import json
import unittest

import anthropic

from streetrace.llm.claude.converter import ClaudeConverter, ContentBlockChunkWrapper
from streetrace.llm.claude.impl import Claude
from streetrace.llm.wrapper import (
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Role,
    ToolCallResult,
    ToolOutput,
)

# Define expected structure for ToolCallResult content in _CLAUDE_HISTORY
_EXPECTED_TOOL_RESULT_CONTENT_DICT = {
    "success": True,
    "output": {
        "type": "text",
        "content": {"result": ["file.py:10:def transform_history"]}
    }
}

_CLAUDE_HISTORY = [
    {
        "role": "user",
        "content": [{"type": "text", "text": "This is some context information."}],
    },
    {"role": "user", "content": [{"type": "text", "text": "Hello, how are you?"}]},
    {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "I'm doing well, thank you for asking!"},
            {
                "type": "tool_use",
                "id": "tool-call-1",
                "name": "search_files",
                "input": {"pattern": "*.py", "search_string": "def transform_history"},
            },
        ],
    },
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "tool-call-1",
                # Store the content as a dictionary now, not JSON string, for easier comparison
                "content": _EXPECTED_TOOL_RESULT_CONTENT_DICT,
            }
        ],
    },
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

        # Create the ToolCallResult object
        tool_call_result = ToolCallResult.ok(
            output=raw_result_data # Use the .ok() factory method
        )

        # Add a message with the correctly structured tool result
        self.history.add_message(
            # Claude expects tool results in USER role, matching _CLAUDE_HISTORY
            Role.USER,
            [
                ContentPartToolResult(
                    id="tool-call-1",
                    name="search_files",
                    content=tool_call_result # Assign the ToolCallResult object
                )
            ],
        )

    def test_transform_history(self):
        """Test transforming history from common format to Claude format."""
        provider_history = self.claude.transform_history(self.history)

        # Compare directly with the expected structure
        # Make sure the structure including the nested dict for tool result content matches
        expected_data = _CLAUDE_HISTORY
        actual_data = json.loads(json.dumps(provider_history)) # Ensure clean comparison

        # Need to parse the JSON string *within* the actual data for the tool result
        if len(actual_data) > 3 and actual_data[3]['content'] and actual_data[3]['content'][0]['type'] == 'tool_result':
             actual_data[3]['content'][0]['content'] = json.loads(actual_data[3]['content'][0]['content'])

        self.maxDiff = None # Show full diff on failure
        self.assertEqual(actual_data, expected_data)

    def test_update_history(self):
        """Test updating history from Claude format to common format."""
        # Create a new history with different context
        clean_history = History(context="This is new context information.")

        # Prepare the provider history (use the constant which now has dict content)
        test_provider_history = json.loads(json.dumps(_CLAUDE_HISTORY))
        # Convert the dict content back to JSON string as the update_history expects it
        if len(test_provider_history) > 3 and test_provider_history[3]['content'][0]['type'] == 'tool_result':
            test_provider_history[3]['content'][0]['content'] = json.dumps(test_provider_history[3]['content'][0]['content'])

        # Update the history
        self.claude.update_history(test_provider_history, clean_history)

        # Assertions:
        # 1. Context should be preserved in the cleaned history
        self.assertEqual(clean_history.context, "This is new context information.")
        # 2. The conversation should have the correct number of messages
        #    (Context from provider_history should be ignored if clean_history has context)
        #    Expected: USER, MODEL, USER(Tool Result)
        self.assertEqual(len(clean_history.conversation), 3)
        # 3. Check roles
        self.assertEqual(clean_history.conversation[0].role, Role.USER)
        self.assertEqual(clean_history.conversation[1].role, Role.MODEL)
        self.assertEqual(clean_history.conversation[2].role, Role.USER) # Tool results land in USER role
        # 4. Check specific content (e.g., tool result content)
        tool_result_part = clean_history.conversation[2].content[0]
        self.assertIsInstance(tool_result_part, ContentPartToolResult)
        self.assertEqual(tool_result_part.content.output.content['result'][0], "file.py:10:def transform_history")


    def test_from_content_part(self):
        """Test converting ContentParts to Claude format."""
        # Test text part
        text_part = ContentPartText(text="Test text")
        claude_text = self.converter._from_content_part(text_part)
        self.assertEqual(claude_text.get("type"), "text")
        self.assertEqual(claude_text.get("text"), "Test text")

        # Test tool call part
        tool_call = ContentPartToolCall(
            id="test-id", name="test_tool", arguments={"arg1": "value1"}
        )
        claude_tool_call = self.converter._from_content_part(tool_call)
        self.assertEqual(claude_tool_call["type"], "tool_use")
        self.assertEqual(claude_tool_call["name"], "test_tool")
        self.assertEqual(claude_tool_call["input"], {"arg1": "value1"})

        # Test tool result part (with correct ToolCallResult structure)
        tool_result_content = ToolCallResult.ok(output={"result": "success"})
        tool_result = ContentPartToolResult(
            id="test-id", name="test_tool", content=tool_result_content
        )
        claude_tool_result = self.converter._from_content_part(tool_result)
        self.assertEqual(claude_tool_result["type"], "tool_result")
        self.assertEqual(claude_tool_result["tool_use_id"], "test-id")

        # Claude expects the content as a JSON string - compare dicts after loading
        expected_content_dict = tool_result_content.model_dump(exclude_unset=True)
        actual_content_dict = json.loads(claude_tool_result["content"])
        self.assertEqual(actual_content_dict, expected_content_dict)


    def test_transform_history_no_context(self):
        """Test transforming history without context."""
        # Create a history without context
        history = History(system_message="You are a helpful assistant.", context="")
        history.add_message(Role.USER, [ContentPartText(text="Hello")])

        provider_history = self.claude.transform_history(history)

        # Check that there's no context message
        self.assertEqual(len(provider_history), 1)
        self.assertEqual(provider_history[0]["role"], "user")
        self.assertEqual(provider_history[0]["content"][0]["text"], "Hello")

    def test_content_block_chunk_wrapper(self):
        """Test the ContentBlockChunkWrapper implementation."""
        # Test text block
        text_block = anthropic.types.TextBlock(type="text", text="Hello world")
        wrapper = ContentBlockChunkWrapper(text_block)
        self.assertEqual(wrapper.get_text(), "Hello world")
        self.assertEqual(wrapper.get_tool_calls(), [])

        # Test tool use block
        tool_use_block = anthropic.types.ToolUseBlock(
            type="tool_use", id="tool-1", name="search_files", input={"pattern": "*.py"}
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
            anthropic.types.TextBlock(type="text", text="Hello world")
        )
        tool_chunk = ContentBlockChunkWrapper(
            anthropic.types.ToolUseBlock(
                type="tool_use",
                id="tool-1",
                name="search_files",
                input={"pattern": "*.py"},
            )
        )

        # Test with multiple chunks
        message = self.converter.to_history_item([text_chunk, tool_chunk])
        self.assertEqual(message["role"], "assistant")
        self.assertEqual(len(message["content"]), 2)
        self.assertEqual(message["content"][0]["type"], "text")
        self.assertEqual(message["content"][0]["text"], "Hello world")
        self.assertEqual(message["content"][1]["type"], "tool_use")
        self.assertEqual(message["content"][1]["id"], "tool-1")
        self.assertEqual(message["content"][1]["name"], "search_files")
        self.assertEqual(message["content"][1]["input"], {"pattern": "*.py"})

    def test_to_history_item_tool_results(self):
        """Test converting tool results to a provider-specific message."""
        # Create a correctly structured tool result
        tool_call_result = ToolCallResult.ok(output={"result": "file.py"})
        tool_result_part = ContentPartToolResult(
            id="tool-1", name="search_files", content=tool_call_result
        )

        # Test with a tool result part
        message = self.converter.to_history_item([tool_result_part])
        self.assertEqual(message["role"], "user") # Tool results are from USER role for Claude
        self.assertEqual(len(message["content"]), 1)
        self.assertEqual(message["content"][0]["type"], "tool_result")
        self.assertEqual(message["content"][0]["tool_use_id"], "tool-1")
        # Compare the JSON string representation by loading both
        expected_content_dict = tool_call_result.model_dump(exclude_unset=True)
        actual_content_dict = json.loads(message["content"][0]["content"])
        self.assertEqual(actual_content_dict, expected_content_dict)

        # Test with empty list
        message = self.converter.to_history_item([])
        self.assertIsNone(message)


if __name__ == "__main__":
    unittest.main()
