"""Tests for the Ollama Data Conversion Module."""

# No direct ollama import needed if we test based on dicts
# import ollama

import pytest
from pydantic import ValidationError

from streetrace.llm.ollama.converter import (
    OllamaHistoryConverter,
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


@pytest.fixture
def converter():
    """Provides an OllamaHistoryConverter instance for tests."""
    return OllamaHistoryConverter()


# --- Tests for OllamaHistoryConverter.create_provider_history ---


def test_from_history_empty(converter) -> None:
    """Test converting an empty history."""
    history = History(system_message=None, context=None, conversation=[])
    ollama_history = converter.create_provider_history(history)
    assert ollama_history == []


def test_from_history_system_message_only(converter) -> None:
    """Test converting history with only a system message."""
    history = History(system_message="Be helpful", context=None, conversation=[])
    ollama_history = converter.create_provider_history(history)
    assert ollama_history == [{"role": "system", "content": "Be helpful"}]


def test_from_history_context_only(converter) -> None:
    """Test converting history with only context."""
    history = History(system_message=None, context="File content here", conversation=[])
    ollama_history = converter.create_provider_history(history)
    # Context becomes the first user message
    assert ollama_history == [{"role": "user", "content": "File content here"}]


def test_from_history_system_and_context(converter) -> None:
    """Test converting history with system message and context."""
    history = History(
        system_message="Be helpful",
        context="File content here",
        conversation=[],
    )
    ollama_history = converter.create_provider_history(history)
    assert ollama_history == [
        {"role": "system", "content": "Be helpful"},
        {"role": "user", "content": "File content here"},  # Context follows system
    ]


def test_from_history_user_message(converter) -> None:
    """Test converting history with a user message."""
    history = History(
        conversation=[Message(role=Role.USER, content=[ContentPartText(text="Hello")])],
    )
    ollama_history = converter.create_provider_history(history)
    assert ollama_history == [{"role": "user", "content": "Hello"}]


def test_from_history_user_message_multiple_parts(converter) -> None:
    """Test converting history with a user message with multiple text parts."""
    history = History(
        conversation=[
            Message(
                role=Role.USER,
                content=[
                    ContentPartText(text="Part 1."),
                    ContentPartText(text=" Part 2."),
                ],
            ),
        ],
    )
    ollama_history = converter.create_provider_history(history)
    assert ollama_history == [{"role": "user", "content": "Part 1. Part 2."}]


def test_from_history_model_message_text_only(converter) -> None:
    """Test converting history with a model message (text only)."""
    history = History(
        conversation=[
            Message(role=Role.MODEL, content=[ContentPartText(text="Hi there")]),
        ],
    )
    ollama_history = converter.create_provider_history(history)
    assert ollama_history == [{"role": "assistant", "content": "Hi there"}]


def test_from_history_model_message_tool_call_only_dict_args(converter) -> None:
    """Test converting history with a model message (tool call only, dict args)."""
    history = History(
        conversation=[
            Message(
                role=Role.MODEL,
                content=[
                    ContentPartToolCall(
                        id="call_abc",
                        name="search_web",
                        arguments={"query": "ollama"},
                    ),
                ],
            ),
        ],
    )
    ollama_history = converter.create_provider_history(history)
    expected_ollama_message = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_abc",
                "function": {
                    "name": "search_web",
                    "arguments": '{"query": "ollama"}',  # Expect stringified JSON
                },
            },
        ],
    }
    assert ollama_history == [expected_ollama_message]


def test_from_history_model_message_tool_call_only_str_args(converter) -> None:
    """Test converting history with a model message (tool call only, string args)."""
    with pytest.raises(
        ValidationError,
        match="ContentPartToolCall\\s+arguments\\s+Input should be a valid dictionary",
    ):
        ContentPartToolCall(id="call_xyz", name="run_code", arguments='print("hello")')


def test_from_history_model_message_text_and_tool_call(converter) -> None:
    """Test converting history with a model message (text and tool call)."""
    history = History(
        conversation=[
            Message(
                role=Role.MODEL,
                content=[
                    ContentPartText(text="Okay, searching..."),
                    ContentPartToolCall(
                        id="call_def",
                        name="search_web",
                        arguments={"query": "python"},
                    ),
                ],
            ),
        ],
    )
    ollama_history = converter.create_provider_history(history)
    expected_ollama_message = {
        "role": "assistant",
        "content": "Okay, searching...",
        "tool_calls": [
            {
                "id": "call_def",
                "function": {
                    "name": "search_web",
                    "arguments": '{"query": "python"}',  # Expect stringified
                },
            },
        ],
    }
    assert ollama_history == [expected_ollama_message]


def test_from_history_tool_message(converter) -> None:
    """Test converting history with a tool message."""
    tool_result = ToolCallResult(
        success=True,
        output=ToolOutput(type="text", content="Python is a programming language."),
    )
    history = History(
        conversation=[
            Message(
                role=Role.TOOL,
                content=[
                    ContentPartToolResult(
                        id="call_def",
                        name="search_web",
                        content=tool_result,
                    ),
                ],
            ),
        ],
    )
    ollama_history = converter.create_provider_history(history)
    # Use model_dump_json to get the expected JSON string, excluding None fields
    expected_content_json = tool_result.model_dump_json(exclude_none=True)
    expected_ollama_message = {
        "role": "tool",
        "tool_call_id": "call_def",
        "name": "search_web",
        "content": expected_content_json,
    }
    assert ollama_history == [expected_ollama_message]


def test_from_history_complex_conversation(converter) -> None:
    """Test converting a more complex conversation flow."""
    tool_result_content = ToolCallResult(
        success=True,
        output=ToolOutput(type="text", content="Found in converter.py"),
    )
    history = History(
        system_message="You are a helpful AI.",
        context="Consider the file `main.py`.",
        conversation=[
            Message(
                role=Role.USER,
                content=[ContentPartText(text="Search for 'ollama'")],
            ),
            Message(
                role=Role.MODEL,
                content=[
                    ContentPartText(text="Okay."),
                    ContentPartToolCall(
                        id="call_1",
                        name="search_files",
                        arguments={"pattern": "*.py", "query": "ollama"},
                    ),
                ],
            ),
            Message(
                role=Role.TOOL,
                content=[
                    ContentPartToolResult(
                        id="call_1",
                        name="search_files",
                        content=tool_result_content,
                    ),
                ],
            ),
            Message(role=Role.USER, content=[ContentPartText(text="Thanks!")]),
        ],
    )
    ollama_history = converter.create_provider_history(history)
    expected_tool_content_json = tool_result_content.model_dump_json(exclude_none=True)
    assert ollama_history == [
        {"role": "system", "content": "You are a helpful AI."},
        {"role": "user", "content": "Consider the file `main.py`."},
        {"role": "user", "content": "Search for 'ollama'"},
        {
            "role": "assistant",
            "content": "Okay.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "search_files",
                        "arguments": '{"pattern": "*.py", "query": "ollama"}',
                    },
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "search_files",
            "content": expected_tool_content_json,
        },
        {"role": "user", "content": "Thanks!"},
    ]


# --- Tests for OllamaHistoryConverter.to_history ---


def test_to_history_empty(converter) -> None:
    """Test converting an empty Ollama history."""
    assert converter.to_history([]) == []


def test_to_history_system_skipped_context_processed(converter) -> None:
    """Test system message is skipped, context (first user message) is processed."""
    ollama_history = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Context prompt"},  # This IS processed
        {"role": "user", "content": "Actual user message"},
    ]
    common_messages = converter.to_history(ollama_history)
    assert len(common_messages) == 2  # Context + Actual user msg
    assert common_messages[0] == Message(
        role=Role.USER,
        content=[ContentPartText(text="Context prompt")],
    )
    assert common_messages[1] == Message(
        role=Role.USER,
        content=[ContentPartText(text="Actual user message")],
    )


def test_to_history_system_only_skipped(converter) -> None:
    """Test that only system message is skipped."""
    ollama_history = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Actual user message"},
    ]
    common_messages = converter.to_history(ollama_history)
    assert len(common_messages) == 1
    assert common_messages[0] == Message(
        role=Role.USER,
        content=[ContentPartText(text="Actual user message")],
    )


def test_to_history_context_only_processed(converter) -> None:
    """Test context (first user message) is processed when no system message."""
    ollama_history = [
        # No system message
        {"role": "user", "content": "Context prompt"},
        {"role": "user", "content": "Actual user message"},
    ]
    common_messages = converter.to_history(ollama_history)
    assert len(common_messages) == 2
    assert common_messages[0] == Message(
        role=Role.USER,
        content=[ContentPartText(text="Context prompt")],
    )
    assert common_messages[1] == Message(
        role=Role.USER,
        content=[ContentPartText(text="Actual user message")],
    )


def test_to_history_user_message(converter) -> None:
    """Test converting an Ollama user message."""
    ollama_history = [{"role": "user", "content": "Hello AI"}]
    common_messages = converter.to_history(ollama_history)
    assert common_messages == [
        Message(role=Role.USER, content=[ContentPartText(text="Hello AI")]),
    ]


def test_to_history_user_message_non_string_content_ignored(converter) -> None:
    """Test user message with non-string content is ignored."""
    ollama_history = [{"role": "user", "content": {"not": "string"}}]
    with pytest.raises(
        ValueError,
        match="ContentPartText\\s+text\\s+Input should be a valid string",
    ):
        converter.to_history(ollama_history)


def test_to_history_assistant_text_only(converter) -> None:
    """Test converting an Ollama assistant message with only text."""
    ollama_history = [{"role": "assistant", "content": "Hello User"}]
    common_messages = converter.to_history(ollama_history)
    assert common_messages == [
        Message(role=Role.MODEL, content=[ContentPartText(text="Hello User")]),
    ]


def test_to_history_assistant_non_string_text_content_ignored(converter) -> None:
    """Test assistant message with non-string text content is ignored."""
    ollama_history = [{"role": "assistant", "content": ["list", "content"]}]
    with pytest.raises(
        ValueError,
        match="ContentPartText\\s+text\\s+Input should be a valid string",
    ):
        converter.to_history(ollama_history)


def test_to_history_assistant_tool_calls_only(converter) -> None:
    """Test converting an Ollama assistant message with only tool calls."""
    ollama_history = [
        {
            "role": "assistant",
            "content": None,  # Explicitly None
            "tool_calls": [
                {
                    "id": "call_xyz",
                    "function": {"name": "get_time", "arguments": "{}"},
                },
                {
                    "id": "call_abc",
                    "function": {
                        "name": "get_date",
                        "arguments": {"format": "YYYY-MM-DD"},
                    },
                },
            ],
        },
    ]
    common_messages = converter.to_history(ollama_history)
    assert common_messages == [
        Message(
            role=Role.MODEL,
            content=[
                ContentPartToolCall(
                    id="call_xyz",
                    name="get_time",
                    arguments={},
                ),  # Parsed JSON
                ContentPartToolCall(
                    id="call_abc",
                    name="get_date",
                    arguments={"format": "YYYY-MM-DD"},
                ),  # Kept dict
            ],
        ),
    ]


def test_to_history_assistant_tool_calls_invalid_formats(converter) -> None:
    """Test converting assistant message with invalid tool call structures."""
    test_cases = [
        {"role": "assistant", "tool_calls": "not a list"},
        {"role": "assistant", "tool_calls": ["not a dict"]},
        {"role": "assistant", "tool_calls": [{"id": "1"}]},  # Missing function
        {"role": "assistant", "tool_calls": [{"id": "1", "function": "not a dict"}]},
    ]
    for ollama_msg in test_cases:
        with pytest.raises(Exception):
            converter.to_history(ollama_msg)


def test_to_history_assistant_text_and_tool_calls(converter) -> None:
    """Test converting an Ollama assistant message with text and tool calls."""
    ollama_history = [
        {
            "role": "assistant",
            "content": "Getting time...",
            "tool_calls": [
                {
                    "id": "call_lmn",
                    "function": {"name": "get_time", "arguments": "{}"},
                },
            ],
        },
    ]
    common_messages = converter.to_history(ollama_history)
    assert common_messages == [
        Message(
            role=Role.MODEL,
            content=[
                ContentPartText(text="Getting time..."),
                ContentPartToolCall(
                    id="call_lmn",
                    name="get_time",
                    arguments={},
                ),  # Parsed
            ],
        ),
    ]


def test_to_history_assistant_tool_calls_malformed_json_args(converter) -> None:
    """Test converting an Ollama assistant message with malformed json args."""
    ollama_history = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_malformed",
                    "function": {
                        "name": "some_func",
                        "arguments": '{"key": "value",',  # Malformed
                    },
                },
            ],
        },
    ]
    with pytest.raises(
        ValidationError,
        match="ContentPartToolCall\\s+arguments\\s+Input should be a valid dictionary",
    ):
        converter.to_history(ollama_history)


def test_to_history_tool_message(converter) -> None:
    """Test converting a valid Ollama tool message."""
    tool_content_json = (
        '{"success": true, "output": {"type": "text", "content": "10:30 AM"}}'
    )
    ollama_history = [
        {
            "role": "tool",
            "tool_call_id": "call_lmn",
            "name": "get_time",  # Name present in tool message
            "content": tool_content_json,
        },
    ]
    common_messages = converter.to_history(ollama_history)
    expected_tool_result = ToolCallResult.model_validate_json(tool_content_json)
    assert common_messages == [
        Message(
            role=Role.TOOL,
            content=[
                ContentPartToolResult(
                    id="call_lmn",
                    name="get_time",
                    content=expected_tool_result,
                ),
            ],
        ),
    ]


def test_to_history_tool_message_content_is_dict(converter) -> None:
    """Test converting tool message where content is a dict (needs dumping)."""
    tool_content_dict = {
        "success": True,
        "output": {"type": "text", "content": "Dict content"},
    }
    ollama_history = [
        {
            "role": "tool",
            "tool_call_id": "call_dict",
            "name": "tool_dict",
            "content": tool_content_dict,
        },
    ]
    with pytest.raises(
        ValidationError,
        match="ToolCallResult\\s+JSON input should be string",
    ):
        converter.to_history(ollama_history)


def test_to_history_tool_message_content_is_other_type(converter, capsys) -> None:
    """Test converting tool message where content is not str/dict (fallback to text)."""
    ollama_history = [
        {
            "role": "tool",
            "tool_call_id": "call_list",
            "name": "tool_list",
            "content": ["list", "content"],  # Invalid type for validation
        },
    ]
    with pytest.raises(
        ValidationError,
        match="ToolCallResult\\s+JSON input should be string",
    ):
        converter.to_history(ollama_history)


def test_to_history_tool_message_invalid_json_content(converter, capsys) -> None:
    """Test converting tool message with invalid JSON string content (fallback to text)."""
    invalid_json_content = '{"success": true, output:'
    ollama_history = [
        {
            "role": "tool",
            "tool_call_id": "call_invalid",
            "name": "tool_invalid",
            "content": invalid_json_content,
        },
    ]
    with pytest.raises(ValidationError, match="ToolCallResult\\s+Invalid JSON"):
        converter.to_history(ollama_history)


def test_to_history_tool_message_validation_error(converter, capsys) -> None:
    """Test converting tool message where content fails Pydantic validation."""
    # Valid JSON, but missing required fields for ToolCallResult (e.g., output)
    content_fails_validation = '{"success": true}'
    ollama_history = [
        {
            "role": "tool",
            "tool_call_id": "call_failval",
            "name": "tool_failval",
            "content": content_fails_validation,
        },
    ]
    with pytest.raises(
        ValidationError,
        match="ToolCallResult\\s+output\\s+Field required",
    ):
        converter.to_history(ollama_history)


def test_to_history_tool_message_name_inference(converter) -> None:
    """Test converting an Ollama tool message where name needs inference."""
    tool_content_json = (
        '{"success": true, "output": {"type": "text", "content": "Result"}}'
    )
    ollama_history = [
        {
            "role": "assistant",  # Preceding assistant msg provides the name
            "tool_calls": [
                {
                    "id": "call_pqr",
                    "function": {"name": "inferred_tool_name", "arguments": "{}"},
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_pqr",
            # Name missing here
            "content": tool_content_json,
        },
    ]
    common_messages = converter.to_history(ollama_history)
    expected_tool_result = ToolCallResult.model_validate_json(tool_content_json)

    assert len(common_messages) == 2  # assistant and tool

    # Check the tool message
    assert common_messages[1].role == Role.TOOL
    tool_result_part = common_messages[1].content[0]
    assert isinstance(tool_result_part, ContentPartToolResult)
    assert tool_result_part.id == "call_pqr"
    assert tool_result_part.name == "inferred_tool_name"  # Name inferred
    assert tool_result_part.content == expected_tool_result


def test_to_history_tool_message_name_inference_fails(converter) -> None:
    """Test converting tool message where name inference fails (defaults to unknown)."""
    tool_content_json = (
        '{"success": true, "output": {"type": "text", "content": "Data"}}'
    )
    ollama_history = [
        {
            "role": "tool",
            "tool_call_id": "call_unknown",
            # Name missing, and no preceding assistant message to infer from
            "content": tool_content_json,
        },
    ]
    common_messages = converter.to_history(ollama_history)
    expected_tool_result = ToolCallResult.model_validate_json(tool_content_json)

    assert len(common_messages) == 1
    tool_result_part = common_messages[0].content[0]
    assert isinstance(tool_result_part, ContentPartToolResult)
    assert tool_result_part.id == "call_unknown"
    assert tool_result_part.name == "unknown"  # Defaulted
    assert tool_result_part.content == expected_tool_result


def test_to_history_complex_conversation(converter) -> None:
    """Test converting a complex Ollama conversation history."""
    tool_a_content = (
        '{"success": true, "output": {"type": "text", "content": "Result A"}}'
    )
    tool_b_content = (
        '{"failure": true, "output": {"type": "error", "content": "Result B failed"}}'
    )

    ollama_history = [
        {"role": "system", "content": "System prompt"},  # Skipped
        {"role": "user", "content": "Context prompt"},  # Processed (Index 0)
        {"role": "user", "content": "Call tool A"},  # Processed (Index 1)
        {
            "role": "assistant",  # Processed (Index 2)
            "content": "Okay",
            "tool_calls": [
                {"id": "tool_a_1", "function": {"name": "tool_A", "arguments": "{}"}},
            ],
        },
        {
            "role": "tool",  # Processed (Index 3)
            "tool_call_id": "tool_a_1",
            "name": "tool_A",
            "content": tool_a_content,
        },
        {"role": "user", "content": "Now call tool B"},  # Processed (Index 4)
        {
            "role": "assistant",  # Processed (Index 5)
            "content": None,
            "tool_calls": [
                {
                    "id": "tool_b_1",
                    "function": {"name": "tool_B", "arguments": '{"param":"val"}'},
                },
            ],
        },
        {
            "role": "tool",  # Processed (Index 6)
            "tool_call_id": "tool_b_1",
            # Name missing, needs inference
            "content": tool_b_content,
        },
        {"role": "assistant", "content": "Tool B failed."},  # Processed (Index 7)
    ]

    common_messages = converter.to_history(ollama_history)
    # Should be 8 messages (Context, User, Asst, Tool, User, Asst, Tool, Asst)
    assert len(common_messages) == 8

    # Check messages by index
    assert common_messages[0] == Message(
        role=Role.USER,
        content=[ContentPartText(text="Context prompt")],
    )
    assert common_messages[1] == Message(
        role=Role.USER,
        content=[ContentPartText(text="Call tool A")],
    )
    assert common_messages[2] == Message(
        role=Role.MODEL,
        content=[
            ContentPartText(text="Okay"),
            ContentPartToolCall(id="tool_a_1", name="tool_A", arguments={}),
        ],
    )
    assert common_messages[3] == Message(
        role=Role.TOOL,
        content=[
            ContentPartToolResult(
                id="tool_a_1",
                name="tool_A",
                content=ToolCallResult.model_validate_json(tool_a_content),
            ),
        ],
    )
    assert common_messages[4] == Message(
        role=Role.USER,
        content=[ContentPartText(text="Now call tool B")],
    )
    assert common_messages[5] == Message(
        role=Role.MODEL,
        content=[
            ContentPartToolCall(
                id="tool_b_1",
                name="tool_B",
                arguments={"param": "val"},
            ),
        ],
    )
    assert common_messages[6] == Message(
        role=Role.TOOL,
        content=[
            ContentPartToolResult(
                id="tool_b_1",
                name="tool_B",  # Inferred name
                content=ToolCallResult.model_validate_json(tool_b_content),
            ),
        ],
    )
    assert common_messages[7] == Message(
        role=Role.MODEL,
        content=[ContentPartText(text="Tool B failed.")],
    )


def test_to_history_unknown_role_skipped(converter) -> None:
    """Test that messages with unknown roles are skipped."""
    ollama_history = [
        {"role": "user", "content": "User message"},
        {"role": "imaginary_role", "content": "Should be skipped"},
        {"role": "assistant", "content": "Assistant message"},
    ]
    common_messages = converter.to_history(ollama_history)
    assert len(common_messages) == 2
    assert common_messages[0].role == Role.USER
    assert common_messages[1].role == Role.MODEL


# --- Tests for OllamaHistoryConverter.to_history_item ---


def test_to_history_item_from_single_tool_result(converter) -> None:
    """Test converting a single tool result to an Ollama message dict."""
    tool_result_part = ContentPartToolResult(
        id="call_abc",
        name="my_tool",
        content=ToolCallResult(
            success=True,
            output=ToolOutput(type="text", content="Done."),
        ),
    )
    # Input must be a list containing the single tool result
    message_dict = converter.to_history_item([tool_result_part])
    expected_content_json = tool_result_part.content.model_dump_json(exclude_none=True)
    assert message_dict == {
        "role": "tool",
        "tool_call_id": "call_abc",
        "name": "my_tool",
        "content": expected_content_json,
    }
