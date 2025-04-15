"""
Claude Data Conversion Module

This module contains utilities for converting between the common message format
and Claude-specific formats for API requests and responses.
"""

import json
from typing import Dict, List, Optional

import anthropic

from streetrace.llm.history_converter import ChunkWrapper, HistoryConverter
from streetrace.llm.wrapper import (
    ContentPart,
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Message,
    Role,
)

_ROLES = {
    Role.SYSTEM: "system",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "user",
}
_CLAUDE_ROLES = {
    "system": Role.SYSTEM,
    "user": Role.USER,
    "assistant": Role.MODEL,
}


class ContentBlockChunkWrapper(ChunkWrapper[anthropic.types.ContentBlock]):
    """
    Wrapper for Claude's ContentBlock that implements the ChunkWrapper interface.

    This allows for a consistent way to access content from Claude's responses.
    """

    def __init__(self, chunk: anthropic.types.ContentBlock):
        super().__init__(chunk)

    def get_text(self) -> str:
        """Get text content from the chunk if it's a TextBlock."""
        return self.raw.text if type(self.raw) is anthropic.types.TextBlock else ""

    def get_tool_calls(self) -> List[ContentPartToolCall]:
        """Get tool calls from the chunk if it's a ToolUseBlock."""
        return (
            [
                ContentPartToolCall(
                    id=self.raw.id, name=self.raw.name, arguments=self.raw.input
                )
            ]
            if type(self.raw) is anthropic.types.ToolUseBlock
            else []
        )


class ClaudeConverter(
    HistoryConverter[anthropic.types.MessageParam, anthropic.types.ContentBlock]
):
    """
    Handles conversion between common message format and Claude-specific formats.

    This class centralizes all conversion logic to make code more maintainable
    and provide a clear data flow path.
    """

    def _from_content_part(
        self, part: ContentPart
    ) -> anthropic.types.ContentBlockParam:
        """
        Convert a common format ContentPart to a Claude-specific content block.

        Args:
            part: The common format content part to convert

        Returns:
            A Claude-specific content block

        Raises:
            ValueError: If the content part type is not recognized
        """
        match part:
            case ContentPartText():
                return anthropic.types.TextBlockParam(type="text", text=part.text)
            case ContentPartToolCall():
                return anthropic.types.ToolUseBlockParam(
                    type="tool_use", id=part.id, name=part.name, input=part.arguments
                )
            case ContentPartToolResult():
                return anthropic.types.ToolResultBlockParam(
                    type="tool_result",
                    tool_use_id=part.id,
                    content=json.dumps(part.content),
                )
            case _:
                raise ValueError(
                    f"Unknown content type encountered {type(part)}: {part}"
                )

    def _to_content_part(
        self, part: anthropic.types.ContentBlockParam, tool_use_names: Dict[str, str]
    ) -> ContentPart:
        """
        Convert a Claude-specific content part to common format ContentPart.

        Args:
            part: The Claude-specific content part to convert
            tool_use_names: Dictionary mapping tool_use_ids to tool names

        Returns:
            A common format ContentPart

        Raises:
            ValueError: If the content type is not recognized
        """
        match part["type"]:
            case "text":
                return ContentPartText(text=part["text"])
            case "tool_use":
                return ContentPartToolCall(
                    id=part["id"], name=part["name"], arguments=part["input"]
                )
            case "tool_result":
                return ContentPartToolResult(
                    id=part["tool_use_id"],
                    name=tool_use_names.get(part["tool_use_id"], "unknown"),
                    content=json.loads(part["content"]),
                )
            case _:
                raise ValueError(f"Unknown content type encountered: {part}")

    def from_history(self, history: History) -> List[anthropic.types.MessageParam]:
        """
        Convert common History format to Claude-specific message format.

        Args:
            history: The common format history

        Returns:
            List of Claude-specific messages
        """
        provider_history: List[anthropic.types.MessageParam] = []

        # Add context as a user message if it exists
        if history.context:
            provider_history.append(
                anthropic.types.MessageParam(
                    role="user",
                    content=[
                        anthropic.types.TextBlockParam(
                            type="text", text=history.context
                        )
                    ],
                )
            )

        # Convert each message in the conversation
        for message in history.conversation:
            provider_history.append(
                anthropic.types.MessageParam(
                    role=_ROLES[message.role],
                    content=[self._from_content_part(part) for part in message.content],
                )
            )

        return provider_history

    def to_history(
        self, provider_history: List[anthropic.types.MessageParam]
    ) -> List[Message]:
        """
        Convert Claude-specific history to common format messages.

        Args:
            provider_history: The Claude-specific history

        Returns:
            List of common format messages
        """
        if not provider_history:
            return []

        common_messages = []
        start_index = 0

        # If we have a context message and should skip it
        if provider_history[0].get("role") == "user":
            start_index = 1

        # Build a mapping of tool_use_ids to tool names
        tool_use_names = {}
        for message in provider_history:
            for content in message.get("content", []):
                if content.get("type") == "tool_use":
                    tool_use_names[content.get("id")] = content.get("name")

        # Convert each message
        for message in provider_history[start_index:]:
            common_content = [
                self._to_content_part(part, tool_use_names)
                for part in message.get("content", [])
            ]
            common_messages.append(
                Message(role=_CLAUDE_ROLES[message.get("role")], content=common_content)
            )

        return common_messages

    def to_history_item(
        self,
        messages: List[ContentBlockChunkWrapper] | List[ContentPartToolResult],
    ) -> Optional[anthropic.types.MessageParam]:
        if not messages:
            return None

        if isinstance(messages[0], ContentPartToolResult):
            return self._tool_results_to_message(messages)
        else:
            return self._content_blocks_to_message(messages)

    def _content_blocks_to_message(
        self, messages: List[ContentBlockChunkWrapper]
    ) -> Optional[anthropic.types.MessageParam]:
        """
        Create an assistant message from content chunks.

        Args:
            chunks: The chunks to include in the message

        Returns:
            An assistant message with the content from all chunks
        """

        content_blocks = []

        for chunk in messages:
            if chunk.get_text():
                content_blocks.append(
                    anthropic.types.TextBlockParam(type="text", text=chunk.get_text())
                )

            for tool_call in chunk.get_tool_calls():
                content_blocks.append(
                    anthropic.types.ToolUseBlockParam(
                        type="tool_use",
                        id=tool_call.id,
                        name=tool_call.name,
                        input=tool_call.arguments,
                    )
                )

        return anthropic.types.MessageParam(role="assistant", content=content_blocks)

    def _tool_results_to_message(
        self, messages: List[ContentPartToolResult]
    ) -> Optional[anthropic.types.MessageParam]:
        """
        Create a tool results message from tool results.

        Args:
            results: The tool results to include in the message

        Returns:
            A tool results message if there are results, None otherwise
        """
        if not messages:
            return None

        return anthropic.types.MessageParam(
            role="user",
            content=[
                anthropic.types.ToolResultBlockParam(
                    type="tool_result",
                    tool_use_id=result.id,
                    content=json.dumps(result.content),
                )
                for result in messages
            ],
        )

    def create_chunk_wrapper(
        self,
        chunk: anthropic.types.ContentBlock,
    ) -> ChunkWrapper[anthropic.types.ContentBlock]:
        """
        Create a wrapper for provider-specific streaming content chunks.

        Args:
            chunk: The chunk to wrap

        Returns:
            A ChunkWrapper[T] implementation to access chunk data
        """
        return ContentBlockChunkWrapper(chunk)
