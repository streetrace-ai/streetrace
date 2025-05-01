"""Gemini AI Provider Implementation.

This module implements the LLMAPI interface for Google's Gemini models.
"""

import logging
import os
from collections.abc import Iterator
from typing import Any, override

from google import genai
from google.genai import types

from streetrace.llm.gemini.converter import GeminiHistoryConverter
from streetrace.llm.llmapi import LLMAPI
from streetrace.llm.wrapper import ContentPart, History, Message

# Set up module-level logger
logger = logging.getLogger(__name__)

ProviderHistory = list[types.Content]

# Constants
MAX_TOKENS = 2**20
MODEL_NAME = "gemini-2.5-pro-preview-03-25"
MAX_MALFORMED_RETRIES = 3  # Maximum number of retries for malformed function calls
MIN_MESSAGES_FOR_PRUNING = 3  # Minimum threshold for pruning conversation history


class Gemini(LLMAPI):
    """Implementation of the LLMAPI interface for Google's Gemini models."""

    _counter = 0
    _adapter: GeminiHistoryConverter

    def __init__(self, adapter: GeminiHistoryConverter | None = None) -> None:
        """Initialize the Gemini implementation.

        Args:
            adapter (GeminiHistoryConverter, optional): Adapter for converting history. Defaults to None.

        """
        super().__init__()
        self._adapter = adapter or GeminiHistoryConverter()

    @override
    def initialize_client(self) -> genai.Client:
        """Initialize and return the Gemini API client.

        Returns:
            genai.Client: The initialized Gemini client

        Raises:
            ValueError: If GEMINI_API_KEY environment variable is not set

        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            msg = "GEMINI_API_KEY environment variable not set."
            raise ValueError(msg)
        return genai.Client(api_key=api_key)

    @override
    def transform_history(self, history: History) -> ProviderHistory:
        """Transform conversation history from common format into Gemini-specific format.

        Args:
            history (History): Conversation history to transform

        Returns:
            List[Dict[str, Any]]: Conversation history in Gemini-specific format

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
    def transform_tools(self, tools: list[dict[str, Any]]) -> list[types.Tool]:
        """Transform tools from common format to Gemini-specific format.

        Args:
            tools: List of tool definitions in common format

        Returns:
            List[types.Tool]: List of tool definitions in Gemini format

        """
        gemini_tools = []

        for tool in tools:
            # Convert properties to Gemini Schema format
            gemini_properties = {}
            for param_name, param_def in tool["function"]["parameters"][
                "properties"
            ].items():
                if "items" in param_def:
                    gemini_properties[param_name] = types.Schema(
                        type=param_def[
                            "type"
                        ].upper(),  # Gemini uses uppercase type names
                        items=types.Schema(
                            type=param_def["items"][
                                "type"
                            ].upper(),  # Gemini uses uppercase type names
                        ),
                        description=param_def["description"],
                    )
                else:
                    gemini_properties[param_name] = types.Schema(
                        type=param_def[
                            "type"
                        ].upper(),  # Gemini uses uppercase type names
                        description=param_def["description"],
                    )

            # Create the function declaration
            function_declaration = types.FunctionDeclaration(
                name=tool["function"]["name"],
                description=tool["function"]["description"],
                parameters=types.Schema(
                    description=f"Parameters for the {tool['function']['name']} function",
                    type="OBJECT",
                    properties=gemini_properties,
                    required=tool["function"]["parameters"]["required"],
                ),
            )

            # Add the tool to the list
            gemini_tools.append(
                types.Tool(function_declarations=[function_declaration]),
            )

        return gemini_tools

    @override
    def pretty_print(self, contents: list[types.Content]) -> str:
        """Format content list for readable logging.

        Args:
            contents: List of content objects to format

        Returns:
            str: Formatted string representation

        """
        parts = []
        for i, content in enumerate(contents):
            if not content:
                parts.append(f"Content {i + 1}:\nNONE")
                continue

            content_parts = []
            for part in content.parts:
                part_attrs = ", ".join(
                    [
                        f"{attr}: {str(val).strip()}"
                        for attr, val in part.__dict__.items()
                        if val is not None
                    ],
                )
                content_parts.append(part_attrs)

            parts.append(
                f"Content {i + 1}:\n - {content.role}: {'; '.join(content_parts)}",
            )

        return "\n".join(parts)

    @override
    def manage_conversation_history(
        self,
        messages: list[Any],
        max_tokens: int = MAX_TOKENS,
    ) -> bool:
        """Ensure contents are within token limits by intelligently pruning when needed.

        Args:
            messages: List of content objects to manage
            max_tokens: Maximum token limit

        Returns:
            bool: True if successful, False if pruning failed

        """
        result = False
        try:
            logger.debug(
                "Transformed manage_conversation_history",
                extra={"messages": messages},
            )
            client = self.initialize_client()
            token_count = client.models.count_tokens(
                model=MODEL_NAME,
                contents=messages,
            )

            # If within limits, no action needed
            if token_count.total_tokens <= max_tokens:
                return True

            logger.info(
                "Token count exceeds limit, pruning...",
                extra={
                    "token_count": token_count.total_tokens,
                    "max_tokens": max_tokens,
                },
            )

            # Try to prune the conversation
            if len(messages) > MIN_MESSAGES_FOR_PRUNING:
                # Keep important context - first message and recent exchanges
                preserve_count = min(5, len(messages) // 2)
                messages[:] = [messages[0]] + messages[-preserve_count:]

                # Recheck token count
                token_count = client.models.count_tokens(
                    model=MODEL_NAME,
                    contents=messages,
                )
                logger.info(
                    "After pruning",
                    extra={
                        "token_count": token_count.total_tokens,
                        "message_count": len(messages),
                    },
                )

                result = token_count.total_tokens <= max_tokens

            if not result:
                # If pruning wasn't possible or wasn't enough
                logger.warning(
                    "Cannot reduce token count sufficiently",
                    extra={"token_count": token_count.total_tokens},
                )
        except Exception as e:
            logger.exception("Error managing tokens", exc_info=e)

        return result

    @override
    def generate(
        self,
        client: genai.Client,
        model_name: str | None,
        system_message: str,
        messages: ProviderHistory,
        tools: list[dict[str, Any]],
    ) -> Iterator[ContentPart]:
        """Get API response from Gemini, process it and handle tool calls.

        Args:
            client: The Gemini client
            model_name: The model name to use
            system_message: The system message to send in the request
            messages: The messages to send in the request
            tools: The Gemini-format tools to use

        Returns:
            Iterator[ContentPart]: Stream of response parts

        """
        model_name = model_name or MODEL_NAME

        # Set up generation configuration
        generation_config = types.GenerateContentConfig(
            tools=tools,
            system_instruction=system_message,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True,
            ),
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO"),
            ),
        )

        # Get the response stream
        response = client.models.generate_content(
            model=model_name,
            contents=messages,
            config=generation_config,
        )
        logger.debug("Raw Gemini response", extra={"response": response})

        return self._adapter.get_response_parts(response)
