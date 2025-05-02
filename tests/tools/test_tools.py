from pathlib import Path

import pytest
from litellm import ChatCompletionMessageToolCall, Function

from streetrace.tools.tools import ToolCall


def test_tools_calls_error_if_args_is_string() -> None:
    """Test that the tool calls are valid and return expected results."""
    # Arrange
    mock_tool_impl = {
        "mock_tool": lambda arg1: ({"result": "success"}, arg1),
    }
    fake_tool_call = ChatCompletionMessageToolCall(
        function=Function(
            name="mock_tool",
            arguments="value1",
        ),
        id="tool_call_id",
        type="function",
    )

    # Act
    tool_call = ToolCall(None, mock_tool_impl, Path("/fake/working/dir"))
    result = tool_call.call_tool(fake_tool_call)

    # Assert
    assert result.failure is True
    assert "Tool call arguments are not valid dict" in result.output.content


def test_tools_calls_error_if_invalid_args() -> None:
    """Test that the tool calls are valid and return expected results."""
    # Arrange
    mock_tool_impl = {
        "mock_tool": lambda _: ({"result": "success"}, "Mocked result"),
    }
    fake_tool_call = ChatCompletionMessageToolCall(
        function=Function(
            name="mock_tool",
            arguments={"arg1": "value1"},
        ),
        id="tool_call_id",
        type="function",
    )

    # Act
    tool_call = ToolCall(None, mock_tool_impl, Path("/fake/working/dir"))
    result = tool_call.call_tool(fake_tool_call)

    # Assert
    assert result.failure is True
    assert "Error executing tool" in result.output.content
    assert "arg1" in result.output.content


def test_tools_calls_valid_tool() -> None:
    """Test that the tool calls are valid and return expected results."""
    # Arrange
    mock_tool_impl = {
        "mock_tool": lambda arg1: ({"result": "success"}, arg1),
    }
    fake_tool_call = ChatCompletionMessageToolCall(
        function=Function(
            name="mock_tool",
            arguments={"arg1": "value1"},
        ),
        id="tool_call_id",
        type="function",
    )

    # Act
    tool_call = ToolCall(None, mock_tool_impl, Path("/fake/working/dir"))
    result = tool_call.call_tool(fake_tool_call)

    # Assert
    assert result.success is True
    assert result.output.content == {"result": "success"}
    assert result.display_output.content == "value1"


def test_tools_calls_missing_tool() -> None:
    """Test that the tool calls are valid and return expected results."""
    # Arrange
    mock_tool_impl = {
        "mock_tool": lambda arg1: ({"result": "success"}, arg1),
    }
    fake_tool_call = ChatCompletionMessageToolCall(
        function=Function(
            name="wrong_name",
            arguments={"arg1": "value1"},
        ),
        id="tool_call_id",
        type="function",
    )

    # Act
    tool_call = ToolCall(None, mock_tool_impl, Path("/fake/working/dir"))
    result = tool_call.call_tool(fake_tool_call)

    # Assert
    assert result.failure is True
    assert "Tool not found: wrong_name" in result.output.content


def test_tools_calls_not_callable() -> None:
    """Test that the tool calls are valid and return expected results."""
    # Arrange
    mock_tool_impl = {
        "mock_tool": [lambda arg1: ({"result": "success"}, arg1)],
    }
    fake_tool_call = ChatCompletionMessageToolCall(
        function=Function(
            name="mock_tool",
            arguments={"arg1": "value1"},
        ),
        id="tool_call_id",
        type="function",
    )

    # Act
    tool_call = ToolCall(None, mock_tool_impl, Path("/fake/working/dir"))
    result = tool_call.call_tool(fake_tool_call)

    # Assert
    assert result.failure is True
    assert "is not callable" in result.output.content


@pytest.mark.skip(reason="litellm (1.67.5) converts all arg names to str")
def test_tools_calls_args_not_string() -> None:
    """Test that the tool calls are valid and return expected results."""
    # Arrange
    mock_tool_impl = {
        "mock_tool": lambda arg1: ({"result": "success"}, arg1),
    }
    fake_tool_call = ChatCompletionMessageToolCall(
        function=Function(
            name="mock_tool",
            arguments={1: "value1"},
        ),
        id="tool_call_id",
        type="function",
    )

    # Act
    tool_call = ToolCall(None, mock_tool_impl, Path("/fake/working/dir"))
    result = tool_call.call_tool(fake_tool_call)

    # Assert
    assert result.failure is True
    assert "arguments must be a dict[str, Any]" in result.output.content


def test_tools_calls_adds_work_dir() -> None:
    """Test that the tool calls are valid and return expected results."""
    # Arrange
    mock_tool_impl = {
        "mock_tool": lambda work_dir: ({"result": "success"}, work_dir),
    }
    fake_tool_call = ChatCompletionMessageToolCall(
        function=Function(
            name="mock_tool",
            arguments={},
        ),
        id="tool_call_id",
        type="function",
    )

    # Act
    tool_call = ToolCall(None, mock_tool_impl, Path("/fake/working/dir"))
    result = tool_call.call_tool(fake_tool_call)

    # Assert
    assert result.success is True
    assert result.display_output.content == "/fake/working/dir"


def test_tools_calls_to_str_if_result_not_json_serializable() -> None:
    """Test that the tool calls are valid and return expected results."""

    # Arrange
    class NonJsonSerializable:
        def __str__(self) -> str:
            return "str:NonJsonSerializable"

    mock_tool_impl = {
        "mock_tool": lambda arg1: (NonJsonSerializable(), arg1),
    }
    fake_tool_call = ChatCompletionMessageToolCall(
        function=Function(
            name="mock_tool",
            arguments={"arg1": "value1"},
        ),
        id="tool_call_id",
        type="function",
    )

    # Act
    tool_call = ToolCall(None, mock_tool_impl, Path("/fake/working/dir"))
    result = tool_call.call_tool(fake_tool_call)

    # Assert
    assert result.success is True
    assert result.output.content == "str:NonJsonSerializable"
    assert result.display_output.content == "value1"
