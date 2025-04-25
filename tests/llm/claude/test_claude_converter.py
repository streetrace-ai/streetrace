"""Unit tests for the Claude data conversion module (src/streetrace/llm/claude/converter.py).

Ensures accurate conversion between common format and Claude API format.
"""

import json
import unittest

import anthropic
import pytest
from pydantic import ValidationError

from streetrace.llm.claude.converter import (
    AnthropicHistoryConverter,
)
from streetrace.llm.wrapper import (
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Message,
    Role,
    ToolCallResult,
    ToolOutput,
)


# Dummy ContentPart for testing error handling
class DummyContentPart:
    pass


class TestClaudeConverter(unittest.TestCase):
    """Tests for the AnthropicHistoryConverter class."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.converter = AnthropicHistoryConverter()

    # --- _from_content_part tests ---

    def test_from_content_part_text(self) -> None:
        """Test converting ContentPartText to Claude TextBlockParam."""
        part = ContentPartText(text="Hello Text")
        expected = anthropic.types.TextBlockParam(type="text", text="Hello Text")
        result = self.converter._from_content_part(part)
        assert result == expected

    def test_from_content_part_tool_call(self) -> None:
        """Test converting ContentPartToolCall to Claude ToolUseBlockParam."""
        part = ContentPartToolCall(id="t1", name="tool", arguments={"a": 1})
        expected = anthropic.types.ToolUseBlockParam(
            type="tool_use",
            id="t1",
            name="tool",
            input={"a": 1},
        )
        result = self.converter._from_content_part(part)
        assert result == expected

    def test_from_content_part_tool_call_non_dict_args(self) -> None:
        """Test converting ContentPartToolCall with non-dict args (should become empty dict)."""
        part = ContentPartToolCall.model_construct(
            id="t1.1",
            name="tool",
            arguments="not_a_dict",
        )
        expected = anthropic.types.ToolUseBlockParam(
            type="tool_use",
            id="t1.1",
            name="tool",
            input={},  # Expect empty dict output
        )
        result = self.converter._from_content_part(part)
        assert result == expected

    def test_from_content_part_tool_result(self) -> None:
        """Test converting ContentPartToolResult to Claude ToolResultBlockParam."""
        tool_output = ToolOutput(type="text", content="Success")
        content = ToolCallResult(output=tool_output, success=True, failure=False)
        part = ContentPartToolResult(id="t1", name="tool", content=content)
        expected_content_json = content.model_dump_json(exclude_none=True)
        expected_block = anthropic.types.ToolResultBlockParam(
            type="tool_result",
            tool_use_id="t1",
            content=expected_content_json,
        )
        result_block = self.converter._from_content_part(part)
        assert result_block == expected_block
        assert result_block["content"] == expected_content_json  # type: ignore
        deserialized = json.loads(result_block["content"])  # type: ignore
        assert deserialized["success"]
        assert not deserialized["failure"]
        assert deserialized.get("error") is None
        assert deserialized["output"] == {"type": "text", "content": "Success"}

    def test_from_content_part_unknown(self) -> None:
        """Test converting an unknown ContentPart type raises ValueError."""
        part = DummyContentPart()  # Use the dummy class instance
        with pytest.raises(ValueError, match="Unknown content part type encountered"):
            self.converter._from_content_part(part)  # type: ignore

    # --- _to_content_part tests ---

    def test_to_content_part_text(self) -> None:
        """Test converting Claude text block dict to ContentPartText."""
        claude_part_dict = {"type": "text", "text": "Claude Text"}
        expected = ContentPartText(text="Claude Text")
        result = self.converter._to_content_part(claude_part_dict, {})
        assert result == expected

    def test_to_content_part_tool_use(self) -> None:
        """Test converting Claude tool_use block dict to ContentPartToolCall."""
        claude_part_dict = {
            "type": "tool_use",
            "id": "t2",
            "name": "claude_tool",
            "input": {"b": 2},
        }
        expected = ContentPartToolCall(id="t2", name="claude_tool", arguments={"b": 2})
        result = self.converter._to_content_part(claude_part_dict, {})
        assert result == expected

    def test_to_content_part_tool_result(self) -> None:
        """Test converting Claude tool_result block dict to ContentPartToolResult."""
        tool_output = ToolOutput(type="text", content="Data")
        content = ToolCallResult(output=tool_output, success=False, failure=True)
        claude_part_dict = {
            "type": "tool_result",
            "tool_use_id": "t3",
            "content": content.model_dump_json(exclude_none=True),
        }
        tool_use_names = {"t3": "original_tool_name"}
        expected = ContentPartToolResult(
            id="t3",
            name="original_tool_name",
            content=content,
        )
        result = self.converter._to_content_part(claude_part_dict, tool_use_names)
        assert result == expected
        assert not result.content.success
        assert result.content.failure

    def test_to_content_part_tool_result_unknown_name(self) -> None:
        """Test converting tool_result block dict with unknown tool_use_id."""
        tool_output = ToolOutput(type="text", content="Data")
        content = ToolCallResult(output=tool_output, success=True, failure=False)
        claude_part_dict = {
            "type": "tool_result",
            "tool_use_id": "t4_unknown",
            "content": content.model_dump_json(exclude_none=True),
        }
        tool_use_names = {"t3": "original_tool_name"}
        expected = ContentPartToolResult(
            id="t4_unknown",
            name="unknown_tool_name",
            content=content,
        )
        result = self.converter._to_content_part(claude_part_dict, tool_use_names)
        assert result == expected
        assert result.content.success
        assert not result.content.failure

    def test_to_content_part_tool_result_invalid_json_content(self) -> None:
        """Test converting tool_result with invalid JSON content (hits except block)."""
        claude_part_dict = {
            "type": "tool_result",
            "tool_use_id": "t_invalid_json",
            "content": "{not valid json",
        }
        tool_use_names = {"t_invalid_json": "some_tool"}
        result = self.converter._to_content_part(claude_part_dict, tool_use_names)
        assert isinstance(result, ContentPartToolResult)
        assert result.id == "t_invalid_json"
        assert result.name == "some_tool"
        assert isinstance(result.content.output, ToolOutput)
        assert result.content.output.type == "text"
        assert "Error parsing result" in result.content.output.content
        assert not result.content.success
        assert result.content.failure

    def test_to_content_part_tool_result_validation_error_content(self) -> None:
        """Test converting tool_result with valid JSON but invalid ToolCallResult structure (hits except block)."""
        invalid_tool_call_result_json = json.dumps(
            {"output": {"type": "text", "content": "Missing flags"}},
        )
        claude_part_dict = {
            "type": "tool_result",
            "tool_use_id": "t_validation_err",
            "content": invalid_tool_call_result_json,
        }
        tool_use_names = {"t_validation_err": "another_tool"}
        result = self.converter._to_content_part(claude_part_dict, tool_use_names)
        assert isinstance(result, ContentPartToolResult)
        assert result.id == "t_validation_err"
        assert result.name == "another_tool"
        assert isinstance(result.content.output, ToolOutput)
        assert result.content.output.type == "text"
        assert "Error parsing result" in result.content.output.content
        assert not result.content.success
        assert result.content.failure

    def test_to_content_part_tool_result_non_string_content(self) -> None:
        """Test converting tool_result with non-string content (should be serialized)."""
        tool_output = ToolOutput(type="text", content="Dict Data")
        content = ToolCallResult(output=tool_output, success=True, failure=False)
        content_dict = content.model_dump()
        claude_part_dict = {
            "type": "tool_result",
            "tool_use_id": "t_dict",
            "content": content_dict,
        }
        tool_use_names = {"t_dict": "dict_tool"}
        expected_content = ToolCallResult.model_validate(content_dict)
        expected = ContentPartToolResult(
            id="t_dict",
            name="dict_tool",
            content=expected_content,
        )
        result = self.converter._to_content_part(claude_part_dict, tool_use_names)
        assert result == expected
        assert result.content.success
        assert not result.content.failure

    def test_to_content_part_unknown_type(self) -> None:
        """Test converting an unknown Claude block type dict raises ValueError."""
        claude_part_dict = {"type": "future_block", "data": "abc"}
        with pytest.raises(ValueError, match="Unknown Claude content type encountered"):
            self.converter._to_content_part(claude_part_dict, {})

    def test_to_content_part_non_dict_input(self) -> None:
        """Test passing non-dict input to _to_content_part raises ValueError."""
        with pytest.raises(ValueError, match="Expected a dict for Claude content part"):
            self.converter._to_content_part("not_a_dict", {})  # type: ignore

    # --- create_provider_history tests ---

    def test_from_history_basic(self) -> None:
        """Test converting basic History (user, model messages)."""
        history = History(
            conversation=[
                Message(role=Role.USER, content=[ContentPartText(text="User prompt")]),
                Message(role=Role.MODEL, content=[ContentPartText(text="Model reply")]),
            ],
        )
        result = self.converter.create_provider_history(history)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_from_history_with_context(self) -> None:
        """Test converting History with context."""
        history = History(
            context="This is global context.",
            conversation=[
                Message(role=Role.USER, content=[ContentPartText(text="User prompt")]),
            ],
        )
        result = self.converter.create_provider_history(history)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"][0]["text"] == "This is global context."
        assert result[1]["role"] == "user"
        assert result[1]["content"][0]["text"] == "User prompt"

    def test_from_history_with_tool_calls_and_results(self) -> None:
        """Test converting History with tool calls and results."""
        tool_output = ToolOutput(type="text", content="Result data")
        tool_result_content = ToolCallResult(
            output=tool_output,
            success=True,
            failure=False,
        )
        history = History(
            conversation=[
                Message(role=Role.USER, content=[ContentPartText(text="Use the tool")]),
                Message(
                    role=Role.MODEL,
                    content=[
                        ContentPartToolCall(
                            id="t5", name="my_tool", arguments={"p": 1},
                        ),
                    ],
                ),
                Message(
                    role=Role.TOOL,
                    content=[
                        ContentPartToolResult(
                            id="t5",
                            name="my_tool",
                            content=tool_result_content,
                        ),
                    ],
                ),
            ],
        )
        result = self.converter.create_provider_history(history)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"
        assert result[2]["content"][0]["type"] == "tool_result"
        self.assertEqual(
            json.loads(result[2]["content"][0]["content"]),  # type: ignore
            tool_result_content.model_dump(exclude_none=True),
        )

    def test_from_history_with_invalid_content_part(self) -> None:
        """Test converting History with an invalid content part (should be skipped)."""
        # Construct messages, bypassing validation for the invalid one
        message_user1 = Message(
            role=Role.USER,
            content=[ContentPartText(text="Good part")],
        )
        message_invalid = Message.model_construct(
            role=Role.MODEL,
            content=[DummyContentPart()],
        )  # Invalid part
        message_user2 = Message(
            role=Role.USER,
            content=[ContentPartText(text="Another good part")],
        )

        history = History(conversation=[message_user1, message_invalid, message_user2])
        result = self.converter.create_provider_history(history)

        # Converter's _from_content_part raises ValueError for DummyContentPart,
        # so the invalid part is skipped. The message with only invalid parts
        # results in empty claude_content and is not added to provider_history.
        assert len(result) == 2  # Only messages with valid parts remain
        assert result[0]["role"] == "user"
        assert result[0]["content"][0]["text"] == "Good part"
        assert result[1]["role"] == "user"
        assert result[1]["content"][0]["text"] == "Another good part"

    def test_from_history_empty_conversation(self) -> None:
        """Test converting History with empty conversation."""
        history = History(context="Only context", conversation=[])
        result = self.converter.create_provider_history(history)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"][0]["text"] == "Only context"

    def test_from_history_empty_content_message(self) -> None:
        """Test converting History with a message having empty content."""
        history = History(
            conversation=[
                Message(role=Role.USER, content=[ContentPartText(text="Hi")]),
                Message(role=Role.MODEL, content=[]),
                Message(role=Role.USER, content=[ContentPartText(text="Still there?")]),
            ],
        )
        result = self.converter.create_provider_history(history)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "user"

    def test_from_history_unsupported_role(self) -> None:
        """Test converting History with an unsupported role (should be skipped)."""
        try:
            message_user = Message(
                role=Role.USER,
                content=[ContentPartText(text="User")],
            )
            message_weird = Message.model_construct(
                role="weird_role",
                content=[ContentPartText(text="Weird")],
            )
            message_model = Message(
                role=Role.MODEL,
                content=[ContentPartText(text="Model")],
            )
            history = History(conversation=[message_user, message_weird, message_model])
        except ValidationError:
            self.skipTest(
                "Skipping test: Pydantic validation prevents constructing message with invalid role.",
            )
            return
        result = self.converter.create_provider_history(history)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    # --- to_history tests ---

    def test_to_history_basic(self) -> None:
        """Test converting basic Claude history (user, assistant) dicts."""
        claude_history = [
            {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hello"}]},
        ]
        result = self.converter.to_history(claude_history)
        assert len(result) == 2
        assert result[0].role == Role.USER
        assert result[1].role == Role.MODEL

    def test_to_history_includes_first_user_message(self) -> None:
        """Test converting Claude history includes the first user message."""
        claude_history = [
            {"role": "user", "content": [{"type": "text", "text": "Possible Context"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Okay"}]},
            {
                "role": "user",
                "content": [{"type": "text", "text": "Actual User Prompt"}],
            },
        ]
        result = self.converter.to_history(claude_history)
        assert len(result) == 3
        assert result[0].role == Role.USER
        assert result[1].role == Role.MODEL
        assert result[2].role == Role.USER

    def test_to_history_with_tools(self) -> None:
        """Test converting Claude history dicts with tool use and results."""
        tool_output = ToolOutput(type="text", content="Tool Done")
        tool_result_content = ToolCallResult(
            output=tool_output,
            success=True,
            failure=False,
        )
        tool_result_content_json = tool_result_content.model_dump_json(
            exclude_none=True,
        )
        claude_history = [
            {"role": "user", "content": [{"type": "text", "text": "Use tool"}]},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t6",
                        "name": "do_stuff",
                        "input": {"x": 1},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t6",
                        "content": tool_result_content_json,
                    },
                ],
            },
        ]
        result = self.converter.to_history(claude_history)
        assert len(result) == 3
        assert result[0].role == Role.USER
        assert result[1].role == Role.MODEL
        assert isinstance(result[1].content[0], ContentPartToolCall)
        assert result[2].role == Role.USER
        assert isinstance(result[2].content[0], ContentPartToolResult)
        assert result[2].content[0].content == tool_result_content
        assert result[2].content[0].content.success
        assert not result[2].content[0].content.failure

    def test_to_history_empty(self) -> None:
        """Test converting an empty Claude history list."""
        result = self.converter.to_history([])
        assert result == []

    def test_to_history_invalid_message_format(self) -> None:
        """Test converting Claude history with various invalid message formats."""
        claude_history = [
            {"role": "user", "content": [{"type": "text", "text": "Good"}]},  # Valid
            "not_a_dict",  # Invalid item (skipped)
            {"role": "unknown_role", "content": []},  # Invalid role (skipped)
            {
                "role": "assistant",
                "content": "not_a_list",
            },  # Invalid content format (message added with empty content)
            {
                "role": "user",
                "content": [{"type": "invalid_type"}],
            },  # Invalid content part type (part skipped, message added with empty content)
            {
                "role": "user",
                "content": ["not_a_dict_part"],
            },  # Invalid content part format (part skipped, message added with empty content)
        ]
        result = self.converter.to_history(claude_history)
        # Expected: Good User, Empty Assistant, Empty User, Empty User
        assert len(result) == 4
        assert result[0].role == Role.USER
        assert result[0].content[0].text == "Good"  # type: ignore
        assert result[1].role == Role.MODEL
        assert result[1].content == []
        assert result[2].role == Role.USER
        assert result[2].content == []
        assert result[3].role == Role.USER
        assert result[3].content == []

    # --- to_history_item tests ---

    def test_to_history_item_from_tool_results(self) -> None:
        """Test converting ContentPartToolResults to a MessageParam dict."""
        tool_output1 = ToolOutput(type="text", content="res1")
        tool_output2 = ToolOutput(type="text", content="res2")
        results = [
            ContentPartToolResult(
                id="t8",
                name="tool",
                content=ToolCallResult(
                    output=tool_output1,
                    success=True,
                    failure=False,
                ),
            ),
            ContentPartToolResult(
                id="t9",
                name="tool2",
                content=ToolCallResult(
                    output=tool_output2,
                    success=True,
                    failure=False,
                ),
            ),
        ]
        result = self.converter.to_history_item(results)
        expected_message = anthropic.types.MessageParam(
            role="user",
            content=[
                anthropic.types.ToolResultBlockParam(
                    type="tool_result",
                    tool_use_id="t8",
                    content=results[0].content.model_dump_json(exclude_none=True),
                ),
                anthropic.types.ToolResultBlockParam(
                    type="tool_result",
                    tool_use_id="t9",
                    content=results[1].content.model_dump_json(exclude_none=True),
                ),
            ],
        )
        assert result == expected_message

    def test_to_history_item_empty_list(self) -> None:
        """Test converting an empty list returns None."""
        result = self.converter.to_history_item([])
        assert result is None

    def test_to_history_item_unsupported_type(self) -> None:
        """Test converting a list with an unsupported type raises TypeError."""
        with pytest.raises(TypeError):
            self.converter.to_history_item(["just_a_string"])  # type: ignore

    # --- _content_blocks_to_message tests (internal helper) ---

    def test_content_blocks_to_message_empty(self) -> None:
        """Test internal conversion with empty chunk list returns None."""
        result = self.converter._content_blocks_to_message([])
        assert result is None

    # --- _tool_results_to_message tests (internal helper) ---

    def test_tool_results_to_message(self) -> None:
        """Test internal conversion from tool results to user message dict."""
        tool_output = ToolOutput(type="text", content="r")
        results = [
            ContentPartToolResult(
                id="t11",
                name="t",
                content=ToolCallResult(output=tool_output, success=True, failure=False),
            ),
        ]
        result = self.converter._tool_results_to_message(results)
        expected = anthropic.types.MessageParam(
            role="user",
            content=[
                anthropic.types.ToolResultBlockParam(
                    type="tool_result",
                    tool_use_id="t11",
                    content=results[0].content.model_dump_json(exclude_none=True),
                ),
            ],
        )
        assert result == expected

    def test_tool_results_to_message_empty(self) -> None:
        """Test internal conversion with empty results list returns None."""
        result = self.converter._tool_results_to_message([])
        assert result is None


if __name__ == "__main__":
    unittest.main()
