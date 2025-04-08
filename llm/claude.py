"""
Claude AI Provider Implementation

This module implements the LLMAPI interface for Anthropic's Claude models.
"""

import json
import os
import logging
import anthropic  # pip install anthropic
import time
from typing import Iterable, List, Dict, Any, Optional, override

from colors import AnsiColors
from llm.wrapper import ChunkWrapper, ContentPart, ContentPartText, ContentPartToolCall, ContentPartToolResult, ContentType, History, ToolResult
from llm.llmapi import LLMAPI

ProviderHistory = List[anthropic.types.MessageParam]

# Constants
MAX_TOKENS = 200000  # Claude 3 Sonnet has a context window of approximately 200K tokens
MODEL_NAME = "claude-3-7-sonnet-20250219"

class ContentBlockChunkWrapper(ChunkWrapper):
    def __init__(self, chunk: anthropic.types.ContentBlock):
        self.raw = chunk

    @override
    def type(self) -> ContentType:
        match self.raw:
            case anthropic.types.TextBlock():
                return ContentType.TEXT
            case anthropic.types.ToolUseBlock():
                return ContentType.TOOL_CALL
            case _:
                raise ValueError(f"Unknown content block type encountered {type(self.raw)}: {self.raw}")

    @override
    def get_text(self) -> str:
        return self.raw.text

    @override
    def get_tool_calls(self) -> List[ContentPartToolCall]:
        return [ContentPartToolCall(self.raw.id, self.raw.name, self.raw.input)]

def _from_part(part: ContentPart) -> anthropic.types.ContentBlockParam:
    """Convert a ContentPart to Claude-specific part."""
    match part:
        case ContentPartText():
            return anthropic.types.TextBlockParam(type="text", text=part.text)
        case ContentPartToolCall():
            return anthropic.types.ToolUseBlockParam(
                type="tool_use",
                id=part.id,
                name=part.name,
                input=part.arguments)
        case ContentPartToolResult():
            return anthropic.types.ToolResultBlockParam(
                type="tool_result",
                tool_use_id=part.id,
                content=json.dumps(part.content)
            )
        case _:
            raise ValueError(f"Unknown content type encountered {type(part)}: {part}")

def _to_part(part: anthropic.types.ContentBlockParam, tool_use_names: Dict[str, str]) -> ContentPart:
    """Convert a Claude-specific part to ContentPart."""
    match part['type']:
        case 'text':
            return ContentPartText(part['text'])
        case 'tool_use':
            return ContentPartToolCall(
                part['id'],
                part['name'],
                part['input'])
        case 'tool_result':
            return ContentPartToolResult(
                part['tool_use_id'],
                tool_use_names.get(part['tool_use_id'], 'unknown'),
                json.loads(part['content']))
        case ContentType.UNKNOWN:
            raise ValueError(f"Unknown content type encountered: {part}")

class Claude(LLMAPI):
    """
    Implementation of the LLMAPI interface for Anthropic's Claude models.
    """

    def initialize_client(self) -> anthropic.Anthropic:
        """
        Initialize and return the Claude API client.

        Returns:
            anthropic.Anthropic: The initialized Claude client

        Raises:
            ValueError: If ANTHROPIC_API_KEY environment variable is not set
        """
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
        return anthropic.Anthropic(api_key=api_key)

    def transform_history(self, history: History) -> ProviderHistory:
        """
        Transform conversation history from common format into Claude-specific format.

        Args:
            history (History): Conversation history to transform

        Returns:
            List[Dict[str, Any]]: Conversation history in Claude-specific format
        """
        provider_history: ProviderHistory = []

        if history.context:
            provider_history.append(
                anthropic.types.MessageParam(
                    role = 'user',
                    content = [anthropic.types.TextBlockParam(type="text", text=history.context)]
                )
            )

        for message in history.conversation:
            provider_history.append(
                anthropic.types.MessageParam(
                    role = message.role,
                    content = [_from_part(part) for part in message.content]
                )
            )

        return provider_history

    def update_history(self, provider_history: ProviderHistory, history: History) -> None:
        """
        Updates the conversation history in common format based on Claude-specific history.

        Args:
            provider_history (List[Dict[str, Any]]): Claude-specific conversation history
            history (History): Conversation history in common format
        """
        history.conversation = []
        start_index = 0
        # if we expect to have a context message, skip the first message of the history
        # as it is the context message
        if history.context and provider_history[0].get('role') == 'user':
            start_index = 1

        tool_use_names = {}

        for message in provider_history:
            for content in message.get('content'):
                if content.get('type') == 'tool_use':
                    tool_use_names[content.get('id')] = content.get('name')

        for message in provider_history[start_index:]:
            history.add_message(
                message.get('role'),
                [_to_part(part, tool_use_names) for part in message.get('content')]
            )

    def transform_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform tools from common format to Claude-specific format.

        Args:
            tools: List of tool definitions in common format

        Returns:
            List[Dict[str, Any]]: List of tool definitions in Claude format
        """
        claude_tools = [
            {
                "type": "custom",
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "input_schema": tool["function"]["parameters"]
            } for tool in tools
        ]

        return claude_tools

    def pretty_print(self, messages: ProviderHistory) -> str:
        """
        Format message list for readable logging.

        Args:
            messages: List of message objects to format

        Returns:
            str: Formatted string representation
        """
        parts = []
        for i, message in enumerate(messages):
            content_str = str(message.get('content', 'NONE'))
            role = message.get('role', 'unknown')
            parts.append(f"Message {i + 1}:\n - {role}: {content_str}")

        return "\n".join(parts)

    def manage_conversation_history(self, messages: ProviderHistory, max_tokens: int = MAX_TOKENS) -> bool:
        """
        Ensure conversation history is within token limits by intelligently pruning when needed.

        Args:
            messages: List of message objects to manage
            max_tokens: Maximum token limit

        Returns:
            bool: True if successful, False if pruning failed
        """
        try:
            # Simplified token count estimation - would need actual token counting in production
            # This is a placeholder for an actual token counting function
            estimated_tokens = sum(len(str(msg)) for msg in messages) // 4

            # If within limits, no action needed
            if estimated_tokens <= max_tokens:
                return True

            logging.info(f"Estimated token count {estimated_tokens} exceeds limit {max_tokens}, pruning...")

            # Keep first item (usually system message) and last N exchanges
            if len(messages) > 3:
                # Keep important context - first message and recent exchanges
                preserve_count = min(5, len(messages) // 2)
                messages[:] = [messages[0]] + messages[-preserve_count:]

                # Recheck token count
                estimated_tokens = sum(len(str(msg)) for msg in messages) // 4
                logging.info(f"After pruning: {estimated_tokens} tokens with {len(messages)} items")

                return estimated_tokens <= max_tokens

            # If conversation is small but still exceeding, we have a problem
            logging.warning(f"Cannot reduce token count sufficiently: {estimated_tokens}")
            return False

        except Exception as e:
            logging.error(f"Error managing tokens: {e}")
            return False

    def generate(
        self,
        client: anthropic.Anthropic,
        model_name: Optional[str],
        conversation: History,
        messages: ProviderHistory,
        tools: List[Dict[str, Any]],
    ) -> Iterable[ContentBlockChunkWrapper]:
        """
        Get API response from Claude, process it and handle tool calls.

        Args:
            client: The Claude client
            model_name: The model name to use
            conversation: The common conversation history
            messages: The messages to send in the request
            tools: The Claude-format tools to use

        Returns:
            Iterable[ContentBlockChunkWrapper]: The response chunks from Claude
        """
        model_name = model_name or MODEL_NAME
        retry_count = 0

        while True:  # This loop handles retries for rate limit errors
            try:
                # Create the message with Claude
                response = client.messages.create(
                    model=model_name,
                    max_tokens=20000,
                    system=conversation.system_message,
                    messages=messages,
                    # stream=True,
                    tools=tools)

                logging.debug("Raw Claude response: %s", response)

                return [ContentBlockChunkWrapper(content_block) for content_block in response.content]

            except anthropic.RateLimitError as e:
                retry_count += 1
                wait_time = 30  # Wait for 30 seconds before retrying

                error_msg = f"Rate limit error encountered. Retrying in {wait_time} seconds... (Attempt {retry_count})"
                logging.exception(e)
                logging.warning(error_msg)
                print(AnsiColors.WARNING + error_msg + AnsiColors.RESET)
                time.sleep(wait_time)
                continue

            except Exception as e:
                logging.exception(f"Error during API call: {e}")
                print(AnsiColors.WARNING +
                      f"\nError during API call: {e}" +
                      AnsiColors.RESET)
                # For non-rate limit errors, don't retry
                raise


    def append_to_history(self, provider_history: ProviderHistory,
                                turn: List[ChunkWrapper | ToolResult]):
        """
        Add turn items into provider's conversation history.

        Args:
            provider_history: List of provider-specific message objects
            turn: List of items in this turn
        """
        # Every part of the turn can contain a part of a text message, a tool call, or a tool result
        # We will build the history out in the order of the turn parts, making sure to produce two items in history:
        # 1. The assistant item, consisting of one part of all text messages, and more parts for tool calls
        # 2. The tool results item, consisting of all tool results

        model_messages = []
        tool_results = []

        for block in turn:
            if isinstance(block, ContentBlockChunkWrapper):
                match block.type():
                    case ContentType.TEXT:
                        # Add text message to outputs
                        model_messages.append(anthropic.types.TextBlockParam(
                            type="text",
                            text=block.raw.text))
                    case ContentType.TOOL_CALL:
                        # Add tool call to outputs
                        model_messages.append(anthropic.types.ToolUseBlockParam(
                            type="tool_use",
                            id=block.raw.id,
                            name=block.raw.name,
                            input=block.raw.input))
                    case _:
                        # Unknown type, raise an error
                        raise ValueError(f"Unknown content block type encountered {type(block)}: {block}")
            elif isinstance(block, ToolResult):
                # Add tool result to outputs
                tool_results.append(anthropic.types.ToolResultBlockParam(
                    type='tool_result',
                    tool_use_id = block.chunk.raw.id,
                    content = json.dumps(block.tool_result)
                ))

        provider_history.append(
            anthropic.types.MessageParam(
                role='assistant',
                content=model_messages
            )
        )

        # Only add tool results if there are any
        if tool_results:
            provider_history.append(
                anthropic.types.MessageParam(
                    role='user',
                    content=tool_results
                )
            )
