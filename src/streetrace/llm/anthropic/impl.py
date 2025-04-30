"""Anthropic AI Provider Implementation.

This module implements the LLMAPI interface for Anthropic's Anthropic models.
"""

import logging
import os
from collections.abc import Iterator
from typing import Any, override

import anthropic

from streetrace.llm.anthropic.converter import AnthropicHistoryConverter
from streetrace.llm.llmapi import LLMAPI, RetriableError
from streetrace.llm.wrapper import ContentPart, History, Message

ProviderHistory = list[anthropic.types.MessageParam]

# Constants
MAX_TOKENS = 200000  # Anthropic 3 Sonnet has a context window of approximately 200K tokens
MODEL_NAME = "anthropic-3-7-sonnet-20250219"


class Anthropic(LLMAPI):
    """Implementation of the LLMAPI interface for Anthropic's Anthropic models."""

    _adapter = AnthropicHistoryConverter()

    @override
    def initialize_client(self) -> anthropic.Anthropic:
        """Initialize and return the Anthropic API client.

        Returns:
            anthropic.Anthropic: The initialized Anthropic client

        Raises:
            ValueError: If ANTHROPIC_API_KEY environment variable is not set

        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            msg = "ANTHROPIC_API_KEY environment variable not set."
            raise ValueError(msg)
        return anthropic.Anthropic(api_key=api_key)

    @override
    def transform_history(self, history: History) -> ProviderHistory:
        """Transform conversation history from common format into Anthropic-specific format.

        Args:
            history (History): Conversation history to transform

        Returns:
            List[Dict[str, Any]]: Conversation history in Anthropic-specific format

        """
        return self._adapter.create_provider_history(history)

    @override
    def append_history(
        self,
        provider_history: ProviderHistory,
        turn: list[Message],
    ) -> None:
        """Add turn items into provider's conversation history.

        Args:
            provider_history: List of provider-specific message objects
            turn: List of items in this turn

        """
        for message in self._adapter.to_provider_history_items(turn):
            provider_history.append(message)

    @override
    def transform_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform tools from common format to Anthropic-specific format.

        Args:
            tools: List of tool definitions in common format

        Returns:
            List[Dict[str, Any]]: List of tool definitions in Anthropic format

        """
        return [
            {
                "type": "custom",
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "input_schema": tool["function"]["parameters"],
            }
            for tool in tools
        ]

    @override
    def pretty_print(self, messages: ProviderHistory) -> str:
        """Format message list for readable logging.

        Args:
            messages: List of message objects to format

        Returns:
            str: Formatted string representation

        """
        parts = []
        for i, message in enumerate(messages):
            content_str = str(message.get("content", "NONE"))
            role = message.get("role", "unknown")
            parts.append(f"Message {i + 1}:\n - {role}: {content_str}")

        return "\n".join(parts)

    @override
    def manage_conversation_history(
        self,
        messages: ProviderHistory,
        max_tokens: int = MAX_TOKENS,
    ) -> bool:
        """Ensure conversation history is within token limits by intelligently pruning when needed.

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

            logging.info(
                f"Estimated token count {estimated_tokens} exceeds limit {max_tokens}, pruning...",
            )

            # Keep first item (usually system message) and last N exchanges
            if len(messages) > 3:
                # Keep important context - first message and recent exchanges
                preserve_count = min(5, len(messages) // 2)
                messages[:] = [messages[0]] + messages[-preserve_count:]

                # Recheck token count
                estimated_tokens = sum(len(str(msg)) for msg in messages) // 4
                logging.info(
                    f"After pruning: {estimated_tokens} tokens with {len(messages)} items",
                )

                return estimated_tokens <= max_tokens

            # If conversation is small but still exceeding, we have a problem
            logging.warning(
                f"Cannot reduce token count sufficiently: {estimated_tokens}",
            )
            return False

        except Exception as e:
            logging.exception(f"Error managing tokens: {e}")
            return False

    @override
    def generate(
        self,
        client: anthropic.Anthropic,
        model_name: str | None,
        system_message: str,
        messages: ProviderHistory,
        tools: list[dict[str, Any]],
    ) -> Iterator[ContentPart]:
        """Get API response from Anthropic, process it and handle tool calls.

        Args:
            client: The Anthropic client
            model_name: The model name to use
            system_message: The system message to send
            messages: The messages to send in the request
            tools: The Anthropic-format tools to use

        Returns:
            Iterator[ContentPart]: Stream of response parts

        """
        model_name = model_name or MODEL_NAME

        while True:  # This loop handles retries for rate limit errors
            try:
                # Create the message with Anthropic
                response = client.messages.create(
                    model=model_name,
                    max_tokens=20000,
                    system=system_message,
                    messages=messages,
                    # stream=True,
                    tools=tools,
                    extra_headers={"x-should-retry": "false"},
                )

                logging.debug("Raw Anthropic response: %s", response)

                return self._adapter.get_response_parts(response)

            except anthropic.RateLimitError as e:
                raise RetriableError(str(e), max_retries=3) from e
