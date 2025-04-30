"""Utility functions for Ollama tests.

This module provides helper functions and fixtures for testing the Ollama provider.
"""

from ollama import ChatResponse
from ollama import Message as OllamaMessage

from streetrace.llm.wrapper import ContentPartToolCall, ToolCallResult, ToolOutput


def create_mock_chat_response(
    content="This is a test response",
    role="assistant",
    tool_calls=None,
    model="llama3",
):
    """Create a mock ChatResponse for testing.

    Args:
        content: The message content
        role: The message role (assistant, user, system, tool)
        tool_calls: List of tool calls (if any)
        model: The model name

    Returns:
        ChatResponse: A mocked ChatResponse object for testing

    """
    tool_calls = tool_calls or []

    return ChatResponse(
        message=OllamaMessage(
            role=role,
            content=content,
            tool_calls=tool_calls,
        ),
        model=model,
        created_at="2023-01-01T00:00:00Z",
        eval_count=100,
        eval_duration=1000000000,
        load_duration=500000000,
        prompt_eval_count=50,
        total_duration=1500000000,
    )


def create_mock_tool_call(
    name="search_files",
    arguments=None,
):
    """Create a mock ToolCall for testing.

    Args:
        name: The function name
        arguments: The function arguments

    Returns:
        ToolCall: A mocked Ollama ToolCall object

    """
    arguments = arguments or {"pattern": "*.py", "search_string": "test"}

    return OllamaMessage.ToolCall(
        function=OllamaMessage.ToolCall.Function(
            name=name,
            arguments=arguments,
        ),
    )


def create_content_part_tool_call(
    name="search_files",
    arguments=None,
    id="tool-123",
):
    """Create a ContentPartToolCall for testing.

    Args:
        name: The function name
        arguments: The function arguments
        id: The tool call ID

    Returns:
        ContentPartToolCall: A ContentPartToolCall object for testing

    """
    arguments = arguments or {"pattern": "*.py", "search_string": "test"}

    return ContentPartToolCall(
        id=id,
        name=name,
        arguments=arguments,
    )


def create_tool_result(
    name="search_files",
    id="result-123",
    content="Found files matching pattern",
    is_error=False,
):
    """Create a tool result for testing.

    Args:
        name: The function name
        id: The result ID
        content: The result content
        is_error: Whether the result is an error

    Returns:
        ContentPartToolResult: A ContentPartToolResult object for testing

    """
    if is_error:
        result = ToolCallResult.error(error=content)
    else:
        result = ToolCallResult.ok(
            output=ToolOutput(
                type="text",
                content=content,
            ),
        )

    from streetrace.llm.wrapper import ContentPartToolResult

    return ContentPartToolResult(
        id=id,
        name=name,
        content=result,
    )
