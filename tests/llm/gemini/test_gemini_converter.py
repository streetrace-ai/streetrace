import unittest

import pytest
from google.genai import types

from streetrace.llm.gemini.converter import GeminiHistoryConverter
from streetrace.llm.wrapper import (
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Message,
    Role,  # Import Role Enum
    ToolCallResult,
    ToolOutput,  # Import ToolOutput model
)


class TestGeminiConverter(unittest.TestCase):
    """Tests for the GeminiHistoryConverter class."""

    def setUp(self) -> None:
        """Set up the GeminiHistoryConverter instance for tests."""
        self.converter = GeminiHistoryConverter()

    # --- Test _from_content_part ---

    def test_from_content_part_text(self) -> None:
        """Test converting ContentPartText to Gemini Part."""
        part = ContentPartText(text="Hello")
        gemini_part = self.converter._from_content_part(part)
        assert gemini_part.text == "Hello"
        assert gemini_part.function_call is None
        assert gemini_part.function_response is None

    def test_from_content_part_tool_call(self) -> None:
        """Test converting ContentPartToolCall to Gemini Part."""
        part = ContentPartToolCall(
            id="call_1",
            name="test_func",
            arguments={"arg1": "val1"},
        )
        gemini_part = self.converter._from_content_part(part)
        assert gemini_part.function_call.name == "test_func"
        assert gemini_part.function_call.args == {"arg1": "val1"}
        assert gemini_part.text is None
        assert gemini_part.function_response is None

    def test_from_content_part_tool_result_ok(self) -> None:
        """Test converting a successful ContentPartToolResult to Gemini Part."""
        result = ToolCallResult.ok(
            output=ToolOutput(type="text", content="Tool output"),
        )
        part = ContentPartToolResult(id="call_1", name="test_func", content=result)
        gemini_part = self.converter._from_content_part(part)
        expected_response = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "Tool output"},
            "display_output": None,
        }
        assert gemini_part.function_response.name == "test_func"
        assert gemini_part.function_response.response == expected_response
        assert gemini_part.text is None
        assert gemini_part.function_call is None

    def test_from_content_part_tool_result_error(self) -> None:
        """Test converting a failed ContentPartToolResult to Gemini Part."""
        result = ToolCallResult.error(output="Tool error")  # Will wrap in ToolOutput
        part = ContentPartToolResult(id="call_err", name="test_func", content=result)
        gemini_part = self.converter._from_content_part(part)
        expected_response = {
            "success": None,
            "failure": True,
            "output": {"type": "text", "content": "Tool error"},
            "display_output": None,
        }
        assert gemini_part.function_response.name == "test_func"
        assert gemini_part.function_response.response == expected_response
        assert gemini_part.text is None
        assert gemini_part.function_call is None

    def test_from_content_part_unknown(self) -> None:
        """Test converting an unknown ContentPart type."""

        class UnknownPart:
            pass

        part = UnknownPart()
        with pytest.raises(
            ValueError, match="Unknown content type encountered .*UnknownPart",
        ):
            self.converter._from_content_part(part)

    # --- Test _to_content_part ---

    def test_to_content_part_text(self) -> None:
        """Test converting Gemini Part (text) to ContentPartText."""
        gemini_part = types.Part(text="Hello")
        common_part = self.converter._to_content_part(gemini_part)
        assert isinstance(common_part, ContentPartText)
        assert common_part.text == "Hello"

    def test_to_content_part_tool_call(self) -> None:
        """Test converting Gemini Part (function call) to ContentPartToolCall."""
        func_call = types.FunctionCall(
            name="test_func",
            args={"arg1": "val1"},
            id="call_1",
        )
        gemini_part = types.Part(function_call=func_call)
        common_part = self.converter._to_content_part(gemini_part)
        assert isinstance(common_part, ContentPartToolCall)
        assert common_part.id == "call_1"
        assert common_part.name == "test_func"
        assert common_part.arguments == {"arg1": "val1"}

    def test_to_content_part_tool_response_ok(self) -> None:
        """Test converting Gemini Part (function response) for success."""
        gemini_response_dict = {
            "success": True,
            "output": {"type": "text", "content": "Success"},
        }
        func_response = types.FunctionResponse(
            name="test_func",
            response=gemini_response_dict,
            id="resp_1",
        )
        gemini_part = types.Part(function_response=func_response)
        common_part = self.converter._to_content_part(gemini_part)

        assert isinstance(common_part, ContentPartToolResult)
        assert common_part.id == "resp_1"
        assert common_part.name == "test_func"
        assert common_part.content.success
        assert common_part.content.failure is None
        assert isinstance(common_part.content.output, ToolOutput)
        assert common_part.content.output.type == "text"
        assert common_part.content.output.content == "Success"
        assert common_part.content.display_output is None

    def test_to_content_part_tool_response_error(self) -> None:
        """Test converting Gemini Part (function response) for failure."""
        gemini_response_dict = {
            "failure": True,
            "output": {"type": "text", "content": "An error occurred"},
        }
        func_response = types.FunctionResponse(
            name="test_func",
            response=gemini_response_dict,
            id="resp_err",
        )
        gemini_part = types.Part(function_response=func_response)
        common_part = self.converter._to_content_part(gemini_part)

        assert isinstance(common_part, ContentPartToolResult)
        assert common_part.id == "resp_err"
        assert common_part.name == "test_func"
        assert common_part.content.failure
        assert common_part.content.success is None
        assert isinstance(common_part.content.output, ToolOutput)
        assert common_part.content.output.type == "text"
        assert common_part.content.output.content == "An error occurred"
        assert common_part.content.display_output is None

    def test_to_content_part_tool_response_validation_error(self) -> None:
        """Test conversion failure if response doesn't match ToolCallResult model."""
        func_response = types.FunctionResponse(
            name="test_func",
            response={"invalid_key": "value"},
            id="resp_1",
        )
        gemini_part = types.Part(function_response=func_response)
        # Fix: Expect ValueError from manual parsing
        with pytest.raises(
            ValueError, match="ToolCallResult\\s+output\\s+Field required",
        ):
            self.converter._to_content_part(gemini_part)

    def test_to_content_part_unknown(self) -> None:
        """Test converting an unknown Gemini Part type."""
        gemini_part = types.Part()
        with pytest.raises(ValueError, match="Unknown content type encountered"):
            self.converter._to_content_part(gemini_part)

    # --- Test create_provider_history ---

    def test_from_history_empty(self) -> None:
        """Test converting an empty History object."""
        history = History(context=None, conversation=[])
        provider_history = self.converter.create_provider_history(history)
        assert provider_history == []

    def test_from_history_with_context(self) -> None:
        """Test converting History with context."""
        history = History(context="System prompt", conversation=[])
        provider_history = self.converter.create_provider_history(history)
        assert len(provider_history) == 1
        assert provider_history[0].role == "user"
        assert len(provider_history[0].parts) == 1
        assert provider_history[0].parts[0].text == "System prompt"

    def test_from_history_with_conversation(self) -> None:
        """Test converting History with a conversation."""
        tool_result_ok = ToolCallResult.ok(
            output=ToolOutput(type="text", content="Result"),
        )
        history = History(
            context="System prompt",
            conversation=[
                Message(role=Role.USER, content=[ContentPartText(text="User query")]),
                Message(
                    role=Role.MODEL,
                    content=[
                        ContentPartText(text="Model response"),
                        ContentPartToolCall(id="c1", name="func", arguments={"a": 1}),
                    ],
                ),
                Message(
                    role=Role.TOOL,
                    content=[
                        ContentPartToolResult(
                            id="c1",
                            name="func",
                            content=tool_result_ok,
                        ),
                    ],
                ),
            ],
        )
        provider_history = self.converter.create_provider_history(history)
        assert len(provider_history) == 4

        assert provider_history[0].role == "user"
        assert provider_history[1].role == "user"
        assert provider_history[2].role == "model"
        assert provider_history[3].role == "tool"

        tool_response_part = provider_history[3].parts[0]
        assert tool_response_part.function_response.name == "func"
        expected_response_dict = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "Result"},
            "display_output": None,
        }
        assert tool_response_part.function_response.response == expected_response_dict

    # --- Test to_history ---

    def test_to_history_empty(self) -> None:
        """Test converting an empty provider history."""
        provider_history = []
        common_history = self.converter.to_history(provider_history)
        assert common_history == []

    def test_to_history_with_context(self) -> None:
        """Test converting provider history including a leading context message."""
        # This test now assumes the converter *does not* skip context messages
        provider_history = [
            types.Content(
                role="user",
                parts=[types.Part(text="System prompt")],
            ),  # Context
            types.Content(role="user", parts=[types.Part(text="Real user message")]),
        ]
        common_history = self.converter.to_history(provider_history)
        # Fix: Expect 2 messages since context skipping was removed
        assert len(common_history) == 2
        # Check first message (originally context)
        assert common_history[0].role == Role.USER
        assert isinstance(common_history[0].content[0], ContentPartText)
        assert common_history[0].content[0].text == "System prompt"
        # Check second message
        assert common_history[1].role == Role.USER
        assert isinstance(common_history[1].content[0], ContentPartText)
        assert common_history[1].content[0].text == "Real user message"

    def test_to_history_no_context(self) -> None:
        """Test converting provider history without leading context."""
        func_call = types.FunctionCall(name="f1", args={}, id="c1")
        # Simulate Gemini response as serialized ToolCallResult
        gemini_response_dict = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "ok"},
            "display_output": None,
        }
        func_resp = types.FunctionResponse(
            name="f1",
            response=gemini_response_dict,
            id="c1",
        )
        provider_history = [
            types.Content(role="user", parts=[types.Part(text="User query")]),
            types.Content(role="model", parts=[types.Part(function_call=func_call)]),
            types.Content(role="tool", parts=[types.Part(function_response=func_resp)]),
        ]
        common_history = self.converter.to_history(provider_history)
        assert len(common_history) == 3

        assert common_history[0].role == Role.USER
        assert common_history[1].role == Role.MODEL

        tool_msg_content = common_history[2].content[0]
        assert common_history[2].role == Role.TOOL
        assert isinstance(tool_msg_content, ContentPartToolResult)
        assert tool_msg_content.name == "f1"
        assert tool_msg_content.id == "c1"
        assert tool_msg_content.content.success
        assert tool_msg_content.content.failure is None
        assert isinstance(tool_msg_content.content.output, ToolOutput)
        assert tool_msg_content.content.output.type == "text"
        assert tool_msg_content.content.output.content == "ok"

    # --- Test to_history_item ---

    def test_to_history_item_empty(self) -> None:
        """Test converting an empty list to a history item."""
        item = self.converter.to_history_item([])
        assert item is None

    def test_to_history_item_from_tool_results(self) -> None:
        """Test converting a list of ContentPartToolResult."""
        result1 = ToolCallResult.ok(output=ToolOutput(type="text", content="Res1"))
        result2 = ToolCallResult.error(output="Err2")  # Error implies failure
        results = [
            ContentPartToolResult(id="c1", name="f1", content=result1),
            ContentPartToolResult(id="c2", name="f2", content=result2),
        ]
        item = self.converter.to_history_item(results)
        assert item is not None
        assert item.role == "tool"
        assert len(item.parts) == 2

        part1 = item.parts[0]
        assert part1.function_response.name == "f1"
        expected_resp1 = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "Res1"},
            "display_output": None,
        }
        assert part1.function_response.response == expected_resp1

        part2 = item.parts[1]
        assert part2.function_response.name == "f2"
        expected_resp2 = {
            "success": None,
            "failure": True,
            "output": {"type": "text", "content": "Err2"},
            "display_output": None,
        }
        assert part2.function_response.response == expected_resp2

    # --- Test _content_blocks_to_message ---

    def test_content_blocks_to_message_empty(self) -> None:
        """Test _content_blocks_to_message with empty list."""
        item = self.converter._content_blocks_to_message([])
        # Fix: Expect None for empty input based on implementation change
        assert item is None

    # --- Test _tool_results_to_message ---

    def test_tool_results_to_message_empty(self) -> None:
        """Test _tool_results_to_message with empty list."""
        item = self.converter._tool_results_to_message([])
        assert item is None

    def test_tool_results_to_message_single(self) -> None:
        """Test _tool_results_to_message with a single result."""
        result = ToolCallResult.ok(output=ToolOutput(type="text", content="R1"))
        results = [ContentPartToolResult(id="c1", name="f1", content=result)]
        item = self.converter._tool_results_to_message(results)

        assert item.role == "tool"
        assert len(item.parts) == 1
        assert item.parts[0].function_response.name == "f1"
        expected_resp = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "R1"},
            "display_output": None,
        }
        assert item.parts[0].function_response.response == expected_resp


if __name__ == "__main__":
    unittest.main()
