"""Test utilities for Anthropic provider.

This module provides helper functions and fixtures for Anthropic tests.
"""

from anthropic.types import (
    ContentBlockParam,
    MessageParam,
    TextBlockParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
    Usage,
)
from anthropic.types import (
    Message as AnthropicMessage,
)


def create_text_message(role: str, text: str) -> MessageParam:
    """Create a Anthropic message with text content.

    Args:
        role: The role of the message sender (user or assistant)
        text: The text content

    Returns:
        MessageParam: A Anthropic-format message

    """
    text_block = TextBlockParam(type="text", text=text)
    return MessageParam(
        role=role,
        content=[text_block],
    )


def create_tool_use_message(role: str, name: str, input_args: dict) -> MessageParam:
    """Create a Anthropic message with a tool use.

    Args:
        role: The role of the message sender (usually assistant)
        name: The name of the tool
        input_args: The input arguments for the tool

    Returns:
        MessageParam: A Anthropic-format message with tool use

    """
    tool_use_block = ToolUseBlockParam(
        type="tool_use",
        id=f"tool-{name}",
        name=name,
        input=input_args,
    )
    return MessageParam(
        role=role,
        content=[tool_use_block],
    )


def create_tool_result_message(
    role: str,
    tool_use_id: str,
    result_content: str,
    is_error: bool = False,
) -> MessageParam:
    """Create a Anthropic message with a tool result.

    Args:
        role: The role of the message sender (usually user)
        tool_use_id: The ID of the corresponding tool use
        result_content: The result content
        is_error: Whether this result represents an error

    Returns:
        MessageParam: A Anthropic-format message with tool result

    """
    tool_result_block = ToolResultBlockParam(
        type="tool_result",
        tool_use_id=tool_use_id,
        content=result_content,
        is_error=is_error,
    )
    return MessageParam(
        role=role,
        content=[tool_result_block],
    )


def create_mixed_message(
    role: str,
    text: str,
    tool_name: str,
    input_args: dict,
) -> MessageParam:
    """Create a Anthropic message with both text and tool use.

    Args:
        role: The role of the message sender
        text: The text content
        tool_name: The name of the tool
        input_args: The input arguments for the tool

    Returns:
        MessageParam: A Anthropic-format message with mixed content

    """
    text_block = TextBlockParam(type="text", text=text)
    tool_use_block = ToolUseBlockParam(
        type="tool_use",
        id=f"tool-{tool_name}",
        name=tool_name,
        input=input_args,
    )
    return MessageParam(
        role=role,
        content=[text_block, tool_use_block],
    )


def create_anthropic_message_response(
    content_blocks: list[ContentBlockParam],
    stop_reason: str = "end_turn",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> AnthropicMessage:
    """Create a complete Anthropic message response.

    Args:
        content_blocks: The content blocks in the response
        stop_reason: The reason the model stopped generating
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        AnthropicMessage: A complete Anthropic message response

    """
    return AnthropicMessage(
        id="msg_123456",
        role="assistant",
        content=content_blocks,
        model="anthropic-3-sonnet-20240229",
        stop_reason=stop_reason,
        type="message",
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    )
