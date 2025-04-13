"""
Unit tests for the Claude data conversion module.
"""

import unittest
import json
import anthropic
from llm.claude_converter import ClaudeConverter, ContentBlockChunkWrapper
from llm.wrapper import (ContentPartText, ContentPartToolCall,
                       ContentPartToolResult, History, Message, Role)


class TestClaudeConverter(unittest.TestCase):
    """Tests for the ClaudeConverter class."""

    def test_common_part_to_claude_text(self):
        """Test converting ContentPartText to Claude text block."""
        # Arrange
        text_part = ContentPartText(text = "Hello, world!")

        # Act
        result = ClaudeConverter.common_part_to_claude(text_part)

        # Assert
        self.assertEqual(result["type"], "text")
        self.assertEqual(result["text"], "Hello, world!")

    def test_common_part_to_claude_tool_call(self):
        """Test converting ContentPartToolCall to Claude tool use block."""
        # Arrange
        tool_call = ContentPartToolCall("tool1", "search_files", {"pattern": "*.py"})

        # Act
        result = ClaudeConverter.common_part_to_claude(tool_call)

        # Assert
        self.assertEqual(result["type"], "tool_use")
        self.assertEqual(result["id"], "tool1")
        self.assertEqual(result["name"], "search_files")
        self.assertEqual(result["input"], {"pattern": "*.py"})

    def test_common_part_to_claude_tool_result(self):
        """Test converting ContentPartToolResult to Claude tool result block."""
        # Arrange
        tool_result = ContentPartToolResult(
            "tool1",
            "search_files",
            {"files": ["file1.py", "file2.py"]}
        )

        # Act
        result = ClaudeConverter.common_part_to_claude(tool_result)

        # Assert
        self.assertEqual(result["type"], "tool_result")
        self.assertEqual(result["tool_use_id"], "tool1")
        self.assertEqual(json.loads(result["content"]), {"files": ["file1.py", "file2.py"]})

    def test_claude_part_to_common_text(self):
        """Test converting Claude text block to ContentPartText."""
        # Arrange
        claude_part = {"type": "text", "text": "Hello, world!"}
        tool_use_names = {}

        # Act
        result = ClaudeConverter.claude_part_to_common(claude_part, tool_use_names)

        # Assert
        self.assertIsInstance(result, ContentPartText)
        self.assertEqual(result.text, "Hello, world!")

    def test_claude_part_to_common_tool_use(self):
        """Test converting Claude tool use block to ContentPartToolCall."""
        # Arrange
        claude_part = {
            "type": "tool_use",
            "id": "tool1",
            "name": "search_files",
            "input": {"pattern": "*.py"}
        }
        tool_use_names = {}

        # Act
        result = ClaudeConverter.claude_part_to_common(claude_part, tool_use_names)

        # Assert
        self.assertIsInstance(result, ContentPartToolCall)
        self.assertEqual(result.id, "tool1")
        self.assertEqual(result.name, "search_files")
        self.assertEqual(result.arguments, {"pattern": "*.py"})

    def test_claude_part_to_common_tool_result(self):
        """Test converting Claude tool result block to ContentPartToolResult."""
        # Arrange
        claude_part = {
            "type": "tool_result",
            "tool_use_id": "tool1",
            "content": json.dumps({"files": ["file1.py", "file2.py"]})
        }
        tool_use_names = {"tool1": "search_files"}

        # Act
        result = ClaudeConverter.claude_part_to_common(claude_part, tool_use_names)

        # Assert
        self.assertIsInstance(result, ContentPartToolResult)
        self.assertEqual(result.id, "tool1")
        self.assertEqual(result.name, "search_files")
        self.assertEqual(result.content, {"files": ["file1.py", "file2.py"]})

    def test_common_to_claude_history(self):
        """Test converting common History to Claude history."""
        # Arrange
        history = History(
            system_message="You are a helpful assistant.",
            context="This is some context.",
            conversation=[
                Message(role = Role.USER, content = [ContentPartText(text = "Hello")]),
                Message(role = Role.MODEL, content = [ContentPartText(text = "Hi there!")])
            ]
        )

        # Act
        result = ClaudeConverter.common_to_claude_history(history)

        # Assert
        self.assertEqual(len(result), 3)  # context + 2 messages
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"][0]["text"], "This is some context.")
        self.assertEqual(result[1]["role"], "user")
        self.assertEqual(result[1]["content"][0]["text"], "Hello")
        self.assertEqual(result[2]["role"], "assistant")
        self.assertEqual(result[2]["content"][0]["text"], "Hi there!")

    def test_claude_to_common_history(self):
        """Test converting Claude history to common Message list."""
        # Arrange
        claude_history = [
            {"role": "user", "content": [{"type": "text", "text": "This is context."}]},
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi there!"}]}
        ]

        # Act
        result = ClaudeConverter.claude_to_common_history(claude_history)

        # Assert
        self.assertEqual(len(result), 2)  # Skipping context
        self.assertEqual(result[0].role, "user")
        self.assertEqual(result[0].content[0].text, "Hello")
        self.assertEqual(result[1].role, "assistant")
        self.assertEqual(result[1].content[0].text, "Hi there!")

    def test_create_assistant_message(self):
        """Test creating an assistant message from content chunks."""
        # Arrange
        # Mock ContentBlockChunkWrapper with text
        text_chunk = ContentBlockChunkWrapper(
            anthropic.types.TextBlock(
                type="text",
                text="Hello, world!"
            )
        )

        # Mock ContentBlockChunkWrapper with tool call
        tool_chunk = ContentBlockChunkWrapper(
            anthropic.types.ToolUseBlock(
                type="tool_use",
                id="tool1",
                name="search_files",
                input={"pattern": "*.py"}
            )
        )

        chunks = [text_chunk, tool_chunk]

        # Act
        result = ClaudeConverter.create_assistant_message(chunks)

        # Assert
        self.assertEqual(result["role"], "assistant")
        self.assertEqual(len(result["content"]), 2)
        self.assertEqual(result["content"][0]["type"], "text")
        self.assertEqual(result["content"][0]["text"], "Hello, world!")
        self.assertEqual(result["content"][1]["type"], "tool_use")
        self.assertEqual(result["content"][1]["id"], "tool1")
        self.assertEqual(result["content"][1]["name"], "search_files")
        self.assertEqual(result["content"][1]["input"], {"pattern": "*.py"})


if __name__ == "__main__":
    unittest.main()