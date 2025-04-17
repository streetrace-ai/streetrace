"""
Claude Data Conversion Module

This module contains utilities for converting between the common message format
and Claude-specific formats for API requests and responses.
"""

import json
from typing import Dict, List, Optional, override

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
    ToolCallResult,
    ToolOutput,
)

_ROLES = {
    Role.SYSTEM: "system",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "user",  # Tool results are sent in a user message in Claude
}
_CLAUDE_ROLES = {
    "system": Role.SYSTEM,
    "user": Role.USER,
    "assistant": Role.MODEL,
    # Note: No specific reverse mapping for TOOL needed as Claude receives tool results as 'user'
}


class ContentBlockChunkWrapper(ChunkWrapper[anthropic.types.ContentBlock]):
    """
    Wrapper for Claude's ContentBlock that implements the ChunkWrapper interface.

    This allows for a consistent way to access content from Claude's responses.
    """

    def __init__(self, chunk: anthropic.types.ContentBlock):
        super().__init__(chunk)

    @override
    def get_text(self) -> str:
        """Get text content from the chunk if it's a TextBlock."""
        return self.raw.text if isinstance(self.raw, anthropic.types.TextBlock) else ""

    @override
    def get_tool_calls(self) -> List[ContentPartToolCall]:
        """Get tool calls from the chunk if it's a ToolUseBlock."""
        return (
            [
                ContentPartToolCall(
                    id=self.raw.id, name=self.raw.name, arguments=self.raw.input
                )
            ]
            if isinstance(self.raw, anthropic.types.ToolUseBlock)
            else []
        )

    @override
    def get_finish_message(self) -> Optional[str]:
        """Get finish message. Returns None for Claude as finish reason is separate."""
        return None


class ClaudeConverter(
    HistoryConverter[anthropic.types.MessageParam, anthropic.types.ContentBlock]
):
    """
    Handles conversion between common message format and Claude-specific formats.
    """

    def _from_content_part(
        self, part: ContentPart
    ) -> anthropic.types.ContentBlockParam:
        """
        Convert a common format ContentPart to a Claude-specific content block.
        """
        if isinstance(part, ContentPartText):
            return anthropic.types.TextBlockParam(type="text", text=part.text)
        elif isinstance(part, ContentPartToolCall):
            args = part.arguments if isinstance(part.arguments, dict) else {}
            return anthropic.types.ToolUseBlockParam(
                type="tool_use", id=part.id, name=part.name, input=args
            )
        elif isinstance(part, ContentPartToolResult):
            return anthropic.types.ToolResultBlockParam(
                type="tool_result",
                tool_use_id=part.id,
                content=part.content.model_dump_json(exclude_none=True),
            )
        else:
            raise ValueError(
                f"Unknown content part type encountered {type(part)}: {part}"
            )

    def _to_content_part(
        self, part: anthropic.types.ContentBlockParam, tool_use_names: Dict[str, str]
    ) -> ContentPart:
        """
        Convert a Claude-specific content part (as dict) to common format ContentPart.
        """
        if not isinstance(part, dict):
            raise ValueError(
                f"Expected a dict for Claude content part, got {type(part)}"
            )

        part_type = part.get("type")
        if part_type == "text":
            return ContentPartText(text=part.get("text", ""))
        elif part_type == "tool_use":
            return ContentPartToolCall(
                id=part.get("id", ""),
                name=part.get("name", ""),
                arguments=part.get("input", {}),
            )
        elif part_type == "tool_result":
            tool_use_id = part.get("tool_use_id", "")
            content_str = part.get("content", "{}")
            if not isinstance(content_str, str):
                content_str = json.dumps(content_str)

            try:
                tool_content = ToolCallResult.model_validate_json(content_str)
            except Exception as e:
                print(f"Error parsing tool result content: {e}, content: {content_str}")
                # Fix: Create fallback ToolCallResult indicating failure correctly
                fallback_output = ToolOutput(
                    type="text", content=f"Error parsing result: {e}"
                )
                tool_content = ToolCallResult(
                    output=fallback_output, success=False, failure=True
                )

            return ContentPartToolResult(
                id=tool_use_id,
                name=tool_use_names.get(tool_use_id, "unknown_tool_name"),
                content=tool_content,
            )
        else:
            raise ValueError(f"Unknown Claude content type encountered: {part_type}")

    def from_history(self, history: History) -> List[anthropic.types.MessageParam]:
        """
        Convert common History format to Claude-specific message format.
        """
        provider_history: List[anthropic.types.MessageParam] = []
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

        for message in history.conversation:
            if not message.content:
                continue
            claude_role = _ROLES.get(message.role)
            if not claude_role:
                print(
                    f"Warning: Unsupported role {message.role} encountered, skipping message."
                )
                continue
            claude_content = []
            for part in message.content:
                try:
                    claude_content.append(self._from_content_part(part))
                except ValueError as e:
                    print(f"Warning: Skipping invalid content part: {e}")
                    continue
            if claude_content:
                provider_history.append(
                    anthropic.types.MessageParam(
                        role=claude_role, content=claude_content
                    )
                )
        return provider_history

    def to_history(
        self, provider_history: List[anthropic.types.MessageParam]
    ) -> List[Message]:
        """
        Convert Claude-specific history (list of MessageParam dicts) to common format messages.
        """
        if not provider_history:
            return []
        common_messages: List[Message] = []
        tool_use_names: Dict[str, str] = {}
        for message_param in provider_history:
            if not isinstance(message_param, dict):
                print(
                    f"Warning: Skipping non-dict item in provider_history: {message_param}"
                )
                continue
            content_list = message_param.get("content", [])
            if not isinstance(content_list, list):
                print(
                    f"Warning: Content for message is not a list, skipping tool name extraction: {message_param}"
                )
                continue
            for content_block in content_list:
                if (
                    isinstance(content_block, dict)
                    and content_block.get("type") == "tool_use"
                ):
                    tool_id = content_block.get("id")
                    tool_name = content_block.get("name")
                    if tool_id and tool_name:
                        tool_use_names[tool_id] = tool_name

        for message_param in provider_history:
            if not isinstance(message_param, dict):
                continue
            claude_role = message_param.get("role")
            common_role = _CLAUDE_ROLES.get(str(claude_role))
            if not common_role:
                print(
                    f"Warning: Unknown or unmappable Claude role '{claude_role}', skipping message."
                )
                continue
            content_list = message_param.get("content", [])
            common_content: List[ContentPart] = []
            if isinstance(content_list, list):
                for part in content_list:
                    try:
                        if isinstance(part, dict):
                            common_content.append(
                                self._to_content_part(part, tool_use_names)
                            )
                        else:
                            print(f"Warning: Skipping non-dict content part: {part}")
                    except Exception as e:
                        print(f"Error converting content part: {e}, part: {part}")
                        continue
            else:
                print(
                    f"Warning: Content for message is not a list, skipping content conversion: {message_param}"
                )

            common_messages.append(Message(role=common_role, content=common_content))
        return common_messages

    def to_history_item(
        self,
        messages: List[ContentBlockChunkWrapper] | List[ContentPartToolResult],
    ) -> Optional[anthropic.types.MessageParam]:
        """
        Converts a list of chunks or tool results into a single Claude MessageParam.
        """
        if not messages:
            return None
        if isinstance(messages[0], ContentPartToolResult):
            if not all(isinstance(m, ContentPartToolResult) for m in messages):
                raise TypeError(
                    "Mixed types in messages list, expected all ContentPartToolResult."
                )
            tool_results: List[ContentPartToolResult] = messages  # type: ignore
            return self._tool_results_to_message(tool_results)
        elif isinstance(messages[0], ContentBlockChunkWrapper):
            if not all(isinstance(m, ContentBlockChunkWrapper) for m in messages):
                raise TypeError(
                    "Mixed types in messages list, expected all ContentBlockChunkWrapper."
                )
            chunks: List[ContentBlockChunkWrapper] = messages  # type: ignore
            return self._content_blocks_to_message(chunks)
        else:
            raise TypeError(f"Unsupported message type in list: {type(messages[0])}")

    def _content_blocks_to_message(
        self, chunks: List[ContentBlockChunkWrapper]
    ) -> Optional[anthropic.types.MessageParam]:
        """
        Create an assistant message param from content block chunks.
        """
        content_blocks: List[anthropic.types.ContentBlockParam] = []
        for chunk in chunks:
            text = chunk.get_text()
            if text:
                content_blocks.append(
                    anthropic.types.TextBlockParam(type="text", text=text)
                )
            tool_calls = chunk.get_tool_calls()
            for tool_call in tool_calls:
                args = (
                    tool_call.arguments if isinstance(tool_call.arguments, dict) else {}
                )
                content_blocks.append(
                    anthropic.types.ToolUseBlockParam(
                        type="tool_use",
                        id=tool_call.id,
                        name=tool_call.name,
                        input=args,
                    )
                )
        if content_blocks:
            return anthropic.types.MessageParam(
                role="assistant", content=content_blocks
            )
        else:
            return None

    def _tool_results_to_message(
        self, results: List[ContentPartToolResult]
    ) -> Optional[anthropic.types.MessageParam]:
        """
        Create a tool results message param (role=user) from tool results.
        """
        if not results:
            return None
        tool_result_blocks = []
        for result in results:
            try:
                content_json = result.content.model_dump_json(exclude_none=True)
                tool_result_blocks.append(
                    anthropic.types.ToolResultBlockParam(
                        type="tool_result", tool_use_id=result.id, content=content_json
                    )
                )
            except Exception as e:
                print(f"Error serializing tool result content: {e}, result: {result}")
                error_content = json.dumps(
                    {
                        "error": f"Serialization failed: {e}",
                        "original_content": str(result.content),
                    }
                )
                tool_result_blocks.append(
                    anthropic.types.ToolResultBlockParam(
                        type="tool_result", tool_use_id=result.id, content=error_content
                    )
                )
                continue
        if not tool_result_blocks:
            return None
        return anthropic.types.MessageParam(role="user", content=tool_result_blocks)

    def create_chunk_wrapper(
        self,
        chunk: anthropic.types.ContentBlock,
    ) -> ChunkWrapper[anthropic.types.ContentBlock]:
        """
        Create a wrapper for provider-specific streaming content chunks.
        """
        if chunk is None:
            raise TypeError("Input chunk cannot be None")
        return ContentBlockChunkWrapper(chunk)
