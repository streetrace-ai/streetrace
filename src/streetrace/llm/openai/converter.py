"""
OpenAI Data Conversion Module

This module contains utilities for converting between the common message format
and OpenAI-specific formats for API requests and responses.
"""

import json
from typing import List, Optional, override

from openai.types import chat

from streetrace.llm.history_converter import ChunkWrapper, HistoryConverter
from streetrace.llm.wrapper import (
    ContentPart,
    ContentPartText,
    ContentPartToolCall,
    ToolCallResult,
    ContentPartToolResult,
    History,
    Message,
    Role,
)

_ROLES = {
    Role.SYSTEM: "system",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "tool",
}


class ChoiceDeltaWrapper(
    ChunkWrapper[chat.chat_completion_chunk.ChoiceDelta | chat.ChatCompletionMessage]
):
    """
    Wrapper for OpenAI's ChoiceDelta that implements the ChunkWrapper interface.

    This allows for a consistent way to access content from OpenAI's streaming responses.
    """

    def __init__(self, chunk: chat.chat_completion_chunk.ChoiceDelta):
        super().__init__(chunk)

    @override
    def get_text(self) -> str:
        """Get text content from the chunk if available."""
        return self.raw.content or ""

    @override
    def get_tool_calls(self) -> List[ContentPartToolCall]:
        """Get tool calls from the chunk if available."""
        return (
            [
                ContentPartToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=(
                        json.loads(call.function.arguments)
                        if call.function.arguments
                        else {}
                    ),
                )
                for call in self.raw.tool_calls
            ]
            if self.raw.tool_calls
            else []
        )

    @override
    def get_finish_message(self) -> str:
        """Get finish message if this is the final chunk from the model."""
        return None


class OpenAIConverter(
    HistoryConverter[
        chat.ChatCompletionMessageParam, chat.chat_completion_chunk.ChoiceDelta
    ]
):
    """
    Handles conversion between common message format and OpenAI-specific formats.

    This class centralizes all conversion logic to make code more maintainable
    and provide a clear data flow path.
    """

    def _from_content_part(
        self, part: ContentPart
    ) -> chat.ChatCompletionContentPartParam:
        """
        Convert a common format ContentPart to an OpenAI-specific content part.

        Args:
            part: The common format content part to convert

        Returns:
            An OpenAI-specific content part

        Raises:
            ValueError: If the content part type is not recognized
        """
        match part:
            case ContentPartText():
                return chat.ChatCompletionContentPartTextParam(
                    type="text", text=part.text
                )
            case ContentPartToolCall():
                return chat.ChatCompletionMessageToolCallParam(
                    id=part.id,
                    function=chat.Function(
                        name=part.name, arguments=json.dumps(part.arguments)
                    ),
                )
            case ContentPartToolResult():
                # OpenAI uses a different structure for tool results
                return None
            case _:
                raise ValueError(
                    f"Unknown content type encountered {type(part)}: {part}"
                )

    def from_history(self, history: History) -> List[chat.ChatCompletionMessageParam]:
        """
        Convert common History format to OpenAI-specific message format.

        Args:
            history: The common format history

        Returns:
            List of OpenAI-specific messages
        """
        provider_history: List[chat.ChatCompletionMessageParam] = []

        # Add system message if it exists
        if history.system_message:
            provider_history.append(
                chat.ChatCompletionSystemMessageParam(
                    role=_ROLES[Role.SYSTEM],
                    content=[
                        chat.ChatCompletionContentPartTextParam(
                            type="text", text=history.system_message
                        )
                    ],
                )
            )

        # Add context as a user message if it exists
        if history.context:
            provider_history.append(
                chat.ChatCompletionUserMessageParam(
                    role=_ROLES[Role.USER],
                    content=[
                        chat.ChatCompletionContentPartTextParam(
                            type="text", text=history.context
                        )
                    ],
                )
            )

        # Convert each message in the conversation
        for message in history.conversation:
            match message.role:
                case Role.USER:
                    provider_history.append(
                        chat.ChatCompletionUserMessageParam(
                            role=_ROLES[Role.USER],
                            content=[
                                chat.ChatCompletionContentPartTextParam(
                                    type="text", text=msg.text
                                )
                                for msg in message.content
                                if isinstance(msg, ContentPartText)
                            ],
                        )
                    )
                case Role.MODEL:
                    text_parts = [
                        chat.ChatCompletionContentPartTextParam(
                            type="text", text=msg.text
                        )
                        for msg in message.content
                        if isinstance(msg, ContentPartText)
                    ]

                    tool_calls = [
                        chat.ChatCompletionMessageToolCallParam(
                            id=msg.id,
                            function=chat.Function(
                                name=msg.name, arguments=json.dumps(msg.arguments)
                            ),
                        )
                        for msg in message.content
                        if isinstance(msg, ContentPartToolCall)
                    ]

                    provider_history.append(
                        chat.ChatCompletionAssistantMessageParam(
                            role=_ROLES[Role.MODEL],
                            content=text_parts,
                            tool_calls=tool_calls,
                        )
                    )
                case Role.TOOL:
                    # Tool messages contain tool results
                    for msg in message.content:
                        if isinstance(msg, ContentPartToolResult):
                            provider_history.append(
                                chat.ChatCompletionToolMessageParam(
                                    role=_ROLES[Role.TOOL],
                                    tool_call_id=msg.id,
                                    content=msg.content.model_dump_json(),
                                )
                            )
                case _:
                    raise ValueError(f"Unknown role encountered {message.role}")

        return provider_history

    def to_history(
        self, provider_history: List[chat.ChatCompletionMessageParam]
    ) -> List[Message]:
        """
        Convert OpenAI-specific history to common format messages.

        Args:
            provider_history: The OpenAI-specific history

        Returns:
            List of common format messages
        """
        if not provider_history:
            return []

        common_messages = []

        # Track tool call IDs to names for referencing in tool results
        tool_use_names = {}

        # First, build the tool_use_names dictionary
        for message in provider_history:
            if (
                message.get("role") == "assistant"
                and hasattr(message, "tool_calls")
                and message.get("tool_calls")
            ):
                for tool_call in message.get("tool_calls"):
                    tool_use_names[tool_call.get("id")] = tool_call.get("function").get(
                        "name"
                    )

        # Convert each message
        for message in provider_history:
            role = message.get("role")
            if role == "system":
                # Skip system messages
                continue
            content = message.get("content")
            tool_calls = message.get("tool_calls")
            tool_call_id = message.get("tool_call_id")
            match role:
                case "user":
                    text_parts = []

                    # Handle different content formats
                    if isinstance(content, str):
                        text_parts = [ContentPartText(text=content)]
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(
                                    ContentPartText(text=part.get("text", ""))
                                )
                            elif isinstance(part, str):
                                text_parts.append(ContentPartText(text=part))

                    if text_parts:
                        common_messages.append(
                            Message(role=Role.USER, content=text_parts)
                        )

                case "assistant":
                    text_parts = []
                    common_tool_calls = []

                    if isinstance(content, str):
                        text_parts = [ContentPartText(text=content)]
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(
                                    ContentPartText(text=part.get("text", ""))
                                )
                            elif isinstance(part, str):
                                text_parts.append(ContentPartText(text=part))

                    # Extract tool calls
                    if tool_calls:
                        for tool_call in tool_calls:
                            if tool_call.get("function"):
                                common_tool_calls.append(
                                    ContentPartToolCall(
                                        id=tool_call.get("id"),
                                        name=tool_call.get("function").get("name"),
                                        arguments=json.loads(
                                            tool_call.get("function").get("arguments")
                                        ),
                                    )
                                )

                    common_messages.append(
                        Message(role=Role.MODEL, content=text_parts + common_tool_calls)
                    )

                case "tool":
                    if tool_call_id:
                        tool_name = tool_use_names.get(tool_call_id, "unknown")

                        common_messages.append(
                            Message(
                                role=Role.TOOL,
                                content=[
                                    ContentPartToolResult(
                                        id=tool_call_id,
                                        name=tool_name,
                                        content=ToolCallResult.model_validate_json(content),
                                    )
                                ],
                            )
                        )
                case _:
                    raise ValueError(f"Unknown role encountered {message.get('role')}")

        return common_messages

    def to_history_item(
        self,
        messages: List[ChoiceDeltaWrapper] | List[ContentPartToolResult],
    ) -> Optional[chat.ChatCompletionMessageParam]:
        """
        Convert chunks or tool results to an OpenAI-specific message.

        Args:
            messages: The chunks or tool results to convert

        Returns:
            An OpenAI-specific message, or None if no valid message can be created
        """
        if not messages:
            return None

        if isinstance(messages[0], ContentPartToolResult):
            return self._tool_results_to_message(messages)
        else:
            return self._content_blocks_to_message(messages)

    def _content_blocks_to_message(
        self, messages: List[ChoiceDeltaWrapper]
    ) -> Optional[chat.ChatCompletionMessageParam]:
        """
        Create an assistant message from content chunks.

        Args:
            chunks: The chunks to include in the message

        Returns:
            An assistant message with the content from all chunks
        """
        text_content = ""
        tool_calls = []
        roles = set()

        for chunk in messages:
            if chunk.raw.role:
                roles.add(chunk.raw.role)
            if chunk.get_text():
                text_content += chunk.get_text()

            for tool_call in chunk.get_tool_calls():
                tool_calls.append(
                    chat.ChatCompletionMessageToolCallParam(
                        type="function",
                        id=tool_call.id,
                        function=chat.chat_completion_message_tool_call_param.Function(
                            name=tool_call.name,
                            arguments=json.dumps(tool_call.arguments),
                        ),
                    )
                )

        if len(roles) != 1:
            raise ValueError(
                f"Multiple roles detected in a single message chunk {len(roles)}: {', '.join(str(r) for r in roles)}"
            )

        return chat.ChatCompletionAssistantMessageParam(
            role=roles.pop(),
            content=text_content,
            tool_calls=tool_calls if tool_calls else None,
        )

    def _tool_results_to_message(
        self, messages: List[ContentPartToolResult]
    ) -> Optional[chat.ChatCompletionMessageParam]:
        """
        Create a tool results message from tool results.

        Args:
            results: The tool results to include in the message

        Returns:
            A tool results message if there are results, None otherwise
        """
        if not messages:
            return None

        # We need to convert each tool result to a separate message
        # OpenAI expects one message per tool result
        result = messages[0]  # Take the first result

        return chat.ChatCompletionToolMessageParam(
            role=_ROLES[Role.TOOL],
            tool_call_id=result.id,
            content=result.content.model_dump_json(),
        )

    def create_chunk_wrapper(
        self,
        chunk: chat.chat_completion_chunk.ChoiceDelta,
    ) -> ChunkWrapper[chat.chat_completion_chunk.ChoiceDelta]:
        """
        Create a wrapper for provider-specific streaming content chunks.

        Args:
            chunk: The chunk to wrap

        Returns:
            A ChunkWrapper[T] implementation to access chunk data
        """
        return ChoiceDeltaWrapper(chunk)
