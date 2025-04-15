"""
Claude AI Provider Implementation

This module implements the LLMAPI interface for Anthropic's Claude models.
"""

import os
import logging
import anthropic  # pip install anthropic
import time
from typing import Iterable, List, Dict, Any, Optional

from streetrace.ui.colors import AnsiColors
from streetrace.llm.history_converter import ChunkWrapper
from streetrace.llm.wrapper import ContentPartToolResult, History
from streetrace.llm.llmapi import LLMAPI
from streetrace.llm.claude.converter import ClaudeConverter, ContentBlockChunkWrapper

ProviderHistory = List[anthropic.types.MessageParam]

# Constants
MAX_TOKENS = 200000  # Claude 3 Sonnet has a context window of approximately 200K tokens
MODEL_NAME = "claude-3-7-sonnet-20250219"

class Claude(LLMAPI):
    """
    Implementation of the LLMAPI interface for Anthropic's Claude models.
    """

    _adapter = ClaudeConverter()

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
        return self._adapter.from_history(history)

    def update_history(self, provider_history: ProviderHistory, history: History) -> None:
        """
        Updates the conversation history in common format based on Claude-specific history.

        Args:
            provider_history (List[Dict[str, Any]]): Claude-specific conversation history
            history (History): Conversation history in common format
        """
        # Replace the conversation with the new messages
        history.conversation = self._adapter.to_history(provider_history)

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
        system_message: str,
        messages: ProviderHistory,
        tools: List[Dict[str, Any]],
    ) -> Iterable[ContentBlockChunkWrapper]:
        """
        Get API response from Claude, process it and handle tool calls.

        Args:
            client: The Claude client
            model_name: The model name to use
            system_message: The system message to send
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
                    system=system_message,
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
                             turn: List[ChunkWrapper | ContentPartToolResult]):
        """
        Add turn items into provider's conversation history.

        Args:
            provider_history: List of provider-specific message objects
            turn: List of items in this turn
        """
        # Separate chunks and tool results
        chunks = []
        tool_results = []

        for item in turn:
            if isinstance(item, ContentBlockChunkWrapper):
                chunks.append(item)
            elif isinstance(item, ContentPartToolResult):
                tool_results.append(item)

        # Add assistant message with all text and tool calls
        provider_history.append(self._adapter.to_history_item(chunks))

        # Add tool results if any exist
        tool_results_message = self._adapter.to_history_item(tool_results)
        if tool_results_message:
            provider_history.append(tool_results_message)