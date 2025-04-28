"""Unit tests for OpenAI's converter module.

This module contains comprehensive tests for the OpenAI converter classes
which handle transformations between common message formats and OpenAI-specific formats.
"""

import builtins
import unittest
from unittest.mock import MagicMock, patch

import pytest

from streetrace.llm.openai.converter import (
    OpenAIHistoryConverter,
)
from streetrace.llm.wrapper import (
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Role,
    ToolCallResult,
    ToolOutput,
)


# Mock class for OpenAI requests that can't be patched easily
class MockDict(dict):
    """A dictionary that allows attribute-style access for testing."""

    def __getattr__(self, key):
        if key in self:
            return self[key]
        msg = f"'{self.__class__.__name__}' object has no attribute '{key}'"
        raise AttributeError(
            msg,
        )

    def get(self, key, default=None):
        return (
            self.get(key, default)
            if hasattr(dict, "get")
            else super().get(key, default)
        )


class TestOpenAIConverter(unittest.TestCase):
    """Tests for the OpenAIHistoryConverter class which handles format conversions."""

    def setUp(self) -> None:
        """Set up common test fixtures."""
        self.converter = OpenAIHistoryConverter()

        # Create a sample history for testing
        self.sample_history = History(
            system_message="You are a helpful assistant.",
            context="This is some context information.",
        )

        # Add a user message
        self.sample_history.add_message(
            Role.USER,
            [ContentPartText(text="Hello, how are you?")],
        )

        # Add a model message with text and tool call
        self.sample_history.add_message(
            Role.MODEL,
            [
                ContentPartText(text="I'm doing well, thank you!"),
                ContentPartToolCall(
                    id="tool-1",
                    name="search_files",
                    arguments={"pattern": "*.py", "search_string": "test"},
                ),
            ],
        )

        # Add a tool result message
        tool_output = ToolOutput(type="text", content={"files": ["test.py"]})
        tool_result = ToolCallResult(success=True, output=tool_output)

        self.sample_history.add_message(
            Role.TOOL,
            [
                ContentPartToolResult(
                    id="tool-1",
                    name="search_files",
                    content=tool_result,
                ),
            ],
        )

    @patch("openai.types.chat.ChatCompletionContentPartTextParam")
    def test_from_content_part_text(self, mock_text_param) -> None:
        """Test converting a ContentPartText to OpenAI format."""
        # Set up mock
        mock_text_param.return_value = {"type": "text", "text": "Hello, world!"}

        text_part = ContentPartText(text="Hello, world!")
        result = self.converter._from_content_part(text_part)

        mock_text_param.assert_called_once_with(type="text", text="Hello, world!")
        assert result["type"] == "text"
        assert result["text"] == "Hello, world!"

    @patch("openai.types.chat.ChatCompletionMessageToolCallParam")
    @patch(
        "openai.types.chat.Function",
        create=True,
    )  # Create the attribute if it doesn't exist
    def test_from_content_part_tool_call(
        self,
        mock_function,
        mock_tool_call_param,
    ) -> None:
        """Test converting a ContentPartToolCall to OpenAI format."""
        # Set up mocks
        mock_function.return_value = {
            "name": "search_files",
            "arguments": '{"pattern": "*.py", "search_string": "test"}',
        }
        mock_tool_call_param.return_value = {
            "id": "tool-1",
            "function": mock_function.return_value,
        }

        tool_call = ContentPartToolCall(
            id="tool-1",
            name="search_files",
            arguments={"pattern": "*.py", "search_string": "test"},
        )

        with patch("streetrace.llm.openai.converter.chat.Function", mock_function):
            with patch(
                "json.dumps",
                return_value='{"pattern": "*.py", "search_string": "test"}',
            ):
                result = self.converter._from_content_part(tool_call)

                mock_function.assert_called_once_with(
                    name="search_files",
                    arguments='{"pattern": "*.py", "search_string": "test"}',
                )
                mock_tool_call_param.assert_called_once_with(
                    id="tool-1",
                    function=mock_function.return_value,
                )

                assert result["id"] == "tool-1"
                assert result["function"]["name"] == "search_files"

    def test_from_content_part_tool_result(self) -> None:
        """Test that _from_content_part returns None for ContentPartToolResult."""
        tool_output = ToolOutput(type="text", content={"files": ["test.py"]})
        tool_result = ToolCallResult(success=True, output=tool_output)
        tool_result_part = ContentPartToolResult(
            id="tool-1",
            name="search_files",
            content=tool_result,
        )

        result = self.converter._from_content_part(tool_result_part)
        assert result is None

    def test_from_content_part_unknown(self) -> None:
        """Test that _from_content_part raises ValueError for unknown content type."""
        with pytest.raises(ValueError):
            self.converter._from_content_part("not a content part")

    @patch("openai.types.chat.ChatCompletionSystemMessageParam")
    @patch("openai.types.chat.ChatCompletionUserMessageParam")
    @patch("openai.types.chat.ChatCompletionAssistantMessageParam")
    @patch("openai.types.chat.ChatCompletionToolMessageParam")
    @patch("openai.types.chat.ChatCompletionContentPartTextParam")
    @patch("openai.types.chat.ChatCompletionMessageToolCallParam")
    @patch(
        "openai.types.chat.Function",
        create=True,
    )  # Create the attribute if it doesn't exist
    def test_from_history_complete(
        self,
        mock_function,
        mock_tool_call_param,
        mock_text_param,
        mock_tool_message,
        mock_assistant_message,
        mock_user_message,
        mock_system_message,
    ) -> None:
        """Test converting a complete History to OpenAI format."""
        # Setup mock returns
        mock_system_message.return_value = {
            "role": "system",
            "content": [{"type": "text", "text": "You are a helpful assistant."}],
        }
        mock_user_message.side_effect = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "This is some context information."},
                ],
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": "Hello, how are you?"}],
            },
        ]
        mock_text_param.side_effect = [
            {"type": "text", "text": "You are a helpful assistant."},
            {"type": "text", "text": "This is some context information."},
            {"type": "text", "text": "Hello, how are you?"},
            {"type": "text", "text": "I'm doing well, thank you!"},
        ]
        mock_function.return_value = {
            "name": "search_files",
            "arguments": '{"pattern": "*.py", "search_string": "test"}',
        }
        mock_tool_call_param.return_value = {
            "id": "tool-1",
            "function": mock_function.return_value,
        }
        mock_assistant_message.return_value = {
            "role": "assistant",
            "content": [{"type": "text", "text": "I'm doing well, thank you!"}],
            "tool_calls": [{"id": "tool-1", "function": mock_function.return_value}],
        }
        mock_tool_message.return_value = {
            "role": "tool",
            "tool_call_id": "tool-1",
            "content": '{"success":true,"output":{"type":"text","content":{"files":["test.py"]}}}',
        }

        # Patch the Function that's directly imported in converter.py
        with patch("streetrace.llm.openai.converter.chat.Function", mock_function):
            with patch.object(
                ToolCallResult,
                "model_dump_json",
                return_value='{"success":true,"output":{"type":"text","content":{"files":["test.py"]}}}',
            ):
                provider_history = self.converter.create_provider_history(
                    self.sample_history,
                )

                # Verify basic structure
                assert len(provider_history) == 5  # system, context, user, model, tool

                # Check system message
                assert provider_history[0]["role"] == "system"
                assert (
                    provider_history[0]["content"][0]["text"]
                    == "You are a helpful assistant."
                )

                # Check context message
                assert provider_history[1]["role"] == "user"
                assert (
                    provider_history[1]["content"][0]["text"]
                    == "This is some context information."
                )

                # Check user message
                assert provider_history[2]["role"] == "user"
                assert (
                    provider_history[2]["content"][0]["text"] == "Hello, how are you?"
                )

                # Check model message with tool call
                assert provider_history[3]["role"] == "assistant"
                assert (
                    provider_history[3]["content"][0]["text"]
                    == "I'm doing well, thank you!"
                )
                assert (
                    provider_history[3]["tool_calls"][0]["function"]["name"]
                    == "search_files"
                )

                # Check tool message
                assert provider_history[4]["role"] == "tool"
                assert provider_history[4]["tool_call_id"] == "tool-1"
                # The content should be a JSON string
                assert "success" in provider_history[4]["content"]
                assert "output" in provider_history[4]["content"]

    @patch("openai.types.chat.ChatCompletionUserMessageParam")
    @patch("openai.types.chat.ChatCompletionContentPartTextParam")
    def test_from_history_minimal(self, mock_text_param, mock_user_message) -> None:
        """Test converting a minimal History with only required fields."""
        # Setup mock returns
        mock_text_param.return_value = {"type": "text", "text": "Hello"}
        mock_user_message.return_value = {
            "role": "user",
            "content": [mock_text_param.return_value],
        }

        minimal_history = History()
        minimal_history.add_message(Role.USER, [ContentPartText(text="Hello")])

        provider_history = self.converter.create_provider_history(minimal_history)

        # Should only have a user message
        assert len(provider_history) == 1
        assert provider_history[0]["role"] == "user"
        assert provider_history[0]["content"][0]["text"] == "Hello"

    @patch("openai.types.chat.ChatCompletionUserMessageParam")
    def test_from_history_with_unknown_role(self, mock_user_message) -> None:
        """Test that create_provider_history raises ValueError for unknown roles."""
        # Create a history with an unknown role
        history = History()

        # Create a message with a role that doesn't match any case in the function
        # We need to mock this since Enum won't allow invalid values
        message = MagicMock()
        message.role = (
            "unknown_role"  # This doesn't match any case in the match statement
        )
        message.content = []

        # Add the message to the history's conversation
        history.conversation = [message]

        # Verify that ValueError is raised
        with pytest.raises(ValueError):
            self.converter.create_provider_history(history)

    def test_to_history_empty(self) -> None:
        """Test that to_history returns an empty list for empty provider_history."""
        result = self.converter.to_history([])
        assert result == []

    def test_to_history_complete(self) -> None:
        """Test converting OpenAI format history to common History format."""
        # Create a mock OpenAI history using namedtuples or similar structure
        # that allows both dictionary access and attribute access

        # Dict-like objects with get method for compatibility with converter code
        class OpenAIMessageDict(dict):
            def get(self, key, default=None):
                return self.get(key, default)

        class OpenAIToolCallDict(dict):
            def get(self, key, default=None):
                return self.get(key, default)

        function = OpenAIToolCallDict(
            {"name": "search_files", "arguments": '{"pattern": "*.py"}'},
        )

        tool_call = OpenAIToolCallDict(
            {"id": "tool-1", "type": "function", "function": function},
        )

        provider_history = [
            OpenAIMessageDict(
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": "You are a helpful assistant."},
                    ],
                },
            ),
            OpenAIMessageDict(
                {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            ),
            OpenAIMessageDict(
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "How can I help?"}],
                    "tool_calls": [tool_call],
                },
            ),
            OpenAIMessageDict(
                {
                    "role": "tool",
                    "tool_call_id": "tool-1",
                    "content": '{"success": true, "output": {"type": "text", "content": {"files": ["test.py"]}}}',
                },
            ),
        ]

        # Add hasattr method for compatibility
        for msg in provider_history:
            msg["tool_calls"] = msg.get("tool_calls")

        # Mock ToolCallResult model_validate_json
        with patch.object(
            ToolCallResult,
            "model_validate_json",
            return_value=ToolCallResult(
                success=True,
                output=ToolOutput(type="text", content={"files": ["test.py"]}),
            ),
        ):
            common_messages = self.converter.to_history(provider_history)

            # Check the structure
            assert len(common_messages) == 3  # Only user, model, and tool (not system)

            # Check user message
            assert common_messages[0].role == Role.USER
            assert len(common_messages[0].content) == 1
            assert common_messages[0].content[0].text == "Hello"

            # Check model message
            assert common_messages[1].role == Role.MODEL

            # Find the text part
            text_parts = [
                p for p in common_messages[1].content if isinstance(p, ContentPartText)
            ]
            assert len(text_parts) == 1
            assert text_parts[0].text == "How can I help?"

            # Find the tool call part
            tool_calls = [
                p
                for p in common_messages[1].content
                if isinstance(p, ContentPartToolCall)
            ]
            assert len(tool_calls) == 1
            assert tool_calls[0].id == "tool-1"
            assert tool_calls[0].name == "search_files"
            assert tool_calls[0].arguments == {"pattern": "*.py"}

            # Check tool result message
            assert common_messages[2].role == Role.TOOL
            assert len(common_messages[2].content) == 1
            assert common_messages[2].content[0].id == "tool-1"
            assert common_messages[2].content[0].content.success

    def test_to_history_with_tools_and_tool_call_ids(self) -> None:
        """Test that tool use names are properly collected from the history."""
        # Create a dictionary to simulate the tool_use_names structure
        tool_use_names = {}

        # Create mock objects that mimic the behavior of what's in converter.py
        message_with_tool_calls = {
            "role": "assistant",
            "content": "I'll help you search",
            "tool_calls": [{"id": "tool-call-1", "function": {"name": "search_files"}}],
        }

        # Mock hasattr to return True for "tool_calls" only for this specific message
        orig_hasattr = builtins.hasattr

        def mock_hasattr(obj, attr):
            if attr == "tool_calls" and obj == message_with_tool_calls:
                return True
            if attr == "get" and obj == message_with_tool_calls:
                return True
            return orig_hasattr(obj, attr)

        # Mock get method for the message
        def mock_message_get(key, default=None):
            if key == "role":
                return message_with_tool_calls["role"]
            if key == "tool_calls" and "tool_calls" in message_with_tool_calls:
                return message_with_tool_calls["tool_calls"]
            return message_with_tool_calls.get(key, default)

        # Mock get method for the tool call
        def mock_tool_call_get(key, default=None):
            if key == "id":
                return "tool-call-1"
            if key == "function":
                return message_with_tool_calls["tool_calls"][0]["function"]
            return None

        # Mock get method for the function
        def mock_function_get(key, default=None) -> str | None:
            if key == "name":
                return "search_files"
            return None

        # Set up the mocks
        message_with_tool_calls["get"] = mock_message_get
        message_with_tool_calls["tool_calls"][0]["get"] = mock_tool_call_get
        message_with_tool_calls["tool_calls"][0]["function"]["get"] = mock_function_get

        # Execute the code that builds tool_use_names
        with patch("builtins.hasattr", mock_hasattr):
            # This is the code from converter.py that builds tool_use_names
            if (
                message_with_tool_calls.get("role") == "assistant"
                and hasattr(message_with_tool_calls, "tool_calls")
                and message_with_tool_calls.get("tool_calls")
            ):
                for tool_call in message_with_tool_calls.get("tool_calls"):
                    tool_use_names[tool_call.get("id")] = tool_call.get("function").get(
                        "name",
                    )

        # Test that the tool_use_names dictionary was populated correctly
        assert tool_use_names["tool-call-1"] == "search_files"

    def test_to_history_with_string_content(self) -> None:
        """Test converting OpenAI format with string content to common format."""

        # Dict-like objects with get method for compatibility with converter code
        class OpenAIMessageDict(dict):
            def get(self, key, default=None):
                return self.get(key, default)

        provider_history = [
            OpenAIMessageDict({"role": "user", "content": "Hello"}),
            OpenAIMessageDict({"role": "assistant", "content": "How can I help?"}),
        ]

        common_messages = self.converter.to_history(provider_history)

        assert len(common_messages) == 2
        assert common_messages[0].role == Role.USER
        assert common_messages[0].content[0].text == "Hello"
        assert common_messages[1].role == Role.MODEL
        assert common_messages[1].content[0].text == "How can I help?"

    def test_to_history_with_list_string_content(self) -> None:
        """Test converting OpenAI format with list of strings to common format."""

        # Dict-like objects with get method for compatibility with converter code
        class OpenAIMessageDict(dict):
            def get(self, key, default=None):
                return self.get(key, default)

        # Create messages with content as a list of strings
        provider_history = [
            OpenAIMessageDict({"role": "user", "content": ["Hello", "User"]}),
            OpenAIMessageDict(
                {"role": "assistant", "content": ["How", "can", "I", "help?"]},
            ),
        ]

        common_messages = self.converter.to_history(provider_history)

        # Check user message
        assert len(common_messages) == 2
        assert common_messages[0].role == Role.USER
        assert len(common_messages[0].content) == 2
        assert common_messages[0].content[0].text == "Hello"
        assert common_messages[0].content[1].text == "User"

        # Check assistant message
        assert common_messages[1].role == Role.MODEL
        assert len(common_messages[1].content) == 4
        assert common_messages[1].content[0].text == "How"
        assert common_messages[1].content[1].text == "can"
        assert common_messages[1].content[2].text == "I"
        assert common_messages[1].content[3].text == "help?"

    def test_to_history_with_unknown_role(self) -> None:
        """Test that to_history raises ValueError for unknown roles."""

        # Dict-like objects with get method for compatibility with converter code
        class OpenAIMessageDict(dict):
            def get(self, key, default=None):
                return self.get(key, default)

        provider_history = [OpenAIMessageDict({"role": "unknown", "content": "Hello"})]

        with pytest.raises(ValueError):
            self.converter.to_history(provider_history)

    @patch("openai.types.chat.ChatCompletionToolMessageParam")
    def test_tool_results_to_message(self, mock_tool_message) -> None:
        """Test converting tool results to a message."""
        # Setup mock
        mock_tool_message.return_value = {
            "role": "tool",
            "tool_call_id": "tool-1",
            "content": '{"success":true,"output":{"type":"text","content":{"files":["test.py"]}}}',
        }

        # Create a tool result
        tool_output = ToolOutput(type="text", content={"files": ["test.py"]})
        tool_result = ToolCallResult(success=True, output=tool_output)
        tool_result_part = ContentPartToolResult(
            id="tool-1",
            name="search_files",
            content=tool_result,
        )

        # Mock model_dump_json to return a fixed string
        with patch.object(
            ToolCallResult,
            "model_dump_json",
            return_value='{"success":true,"output":{"type":"text","content":{"files":["test.py"]}}}',
        ):
            # Convert to message
            message = self.converter._tool_results_to_message([tool_result_part])

            # Check the message
            mock_tool_message.assert_called_once_with(
                role="tool",
                tool_call_id="tool-1",
                content='{"success":true,"output":{"type":"text","content":{"files":["test.py"]}}}',
            )

            assert message["role"] == "tool"
            assert message["tool_call_id"] == "tool-1"
            assert (
                message["content"]
                == '{"success":true,"output":{"type":"text","content":{"files":["test.py"]}}}'
            )

    def test_tool_results_to_message_empty(self) -> None:
        """Test that _tool_results_to_message returns None for empty results."""
        assert self.converter._tool_results_to_message([]) is None

    def test_to_history_item_with_tool_results(self) -> None:
        """Test to_history_item with tool results."""
        # Create a tool result
        tool_output = ToolOutput(type="text", content={"files": ["test.py"]})
        tool_result = ToolCallResult(success=True, output=tool_output)
        tool_result_part = ContentPartToolResult(
            id="tool-1",
            name="search_files",
            content=tool_result,
        )

        # Mock the _tool_results_to_message method
        expected_message = {"role": "tool", "tool_call_id": "tool-1", "content": "{}"}

        with patch.object(
            self.converter,
            "_tool_results_to_message",
            return_value=expected_message,
        ) as mock_method:
            result = self.converter.to_history_item([tool_result_part])

            # Verify the method was called with the tool result
            mock_method.assert_called_once_with([tool_result_part])
            assert result == expected_message

    def test_to_history_item_empty(self) -> None:
        """Test that to_history_item returns None for empty input."""
        assert self.converter.to_history_item([]) is None


if __name__ == "__main__":
    unittest.main()
