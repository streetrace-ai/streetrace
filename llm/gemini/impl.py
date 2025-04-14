"""
Gemini AI Provider Implementation

This module implements the LLMAPI interface for Google's Gemini models.
"""

import os
import logging
from typing import Iterable, List, Dict, Any, Optional

from google import genai
from google.genai import types
from llm.history_converter import ChunkWrapper
from llm.llmapi import LLMAPI
from llm.wrapper import ContentPartToolResult, History
from llm.gemini.converter import GeminiConverter, GenerateContentPartWrapper

ProviderHistory = List[types.Content]

# Constants
MAX_TOKENS = 2**20
MODEL_NAME = 'gemini-2.5-pro-exp-03-25'
MAX_MALFORMED_RETRIES = 3  # Maximum number of retries for malformed function calls

class Gemini(LLMAPI):
    """
    Implementation of the LLMAPI interface for Google's Gemini models.
    """

    _counter = 0
    _adapter = GeminiConverter()

    def initialize_client(self) -> genai.Client:
        """
        Initialize and return the Gemini API client.

        Returns:
            genai.Client: The initialized Gemini client

        Raises:
            ValueError: If GEMINI_API_KEY environment variable is not set
        """
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        return genai.Client(api_key=api_key)

    def transform_history(self, history: History) -> ProviderHistory:
        """
        Transform conversation history from common format into Gemini-specific format.

        Args:
            history (History): Conversation history to transform

        Returns:
            List[Dict[str, Any]]: Conversation history in Gemini-specific format
        """
        return self._adapter.from_history(history)

    def update_history(self, provider_history: ProviderHistory, history: History) -> None:
        """
        Updates the conversation history in common format based on Gemini-specific history.

        Args:
            provider_history (List[Dict[str, Any]]): Gemini-specific conversation history
            history (History): Conversation history in common format
        """
        # Replace the conversation with the new messages
        history.conversation = self._adapter.to_history(provider_history)

    def transform_tools(self, tools: List[Dict[str, Any]]) -> List[types.Tool]:
        """
        Transform tools from common format to Gemini-specific format.

        Args:
            tools: List of tool definitions in common format

        Returns:
            List[types.Tool]: List of tool definitions in Gemini format
        """
        gemini_tools = []

        for tool in tools:
            # Convert properties to Gemini Schema format
            gemini_properties = {}
            for param_name, param_def in tool['function']['parameters']['properties'].items():
                if 'items' in param_def:
                    gemini_properties[param_name] = types.Schema(
                        type=param_def['type'].upper(),  # Gemini uses uppercase type names
                        items=types.Schema(
                            type=param_def['items']['type'].upper(),  # Gemini uses uppercase type names
                        ),
                        description=param_def['description']
                    )
                else:
                    gemini_properties[param_name] = types.Schema(
                        type=param_def['type'].upper(),  # Gemini uses uppercase type names
                        description=param_def['description']
                    )

            # Create the function declaration
            function_declaration = types.FunctionDeclaration(
                name=tool['function']['name'],
                description=tool['function']['description'],
                parameters=types.Schema(
                    description=f'Parameters for the {tool['function']['name']} function',
                    type='OBJECT',
                    properties=gemini_properties,
                    required=tool['function']['parameters']['required']
                )
            )

            # Add the tool to the list
            gemini_tools.append(types.Tool(function_declarations=[function_declaration]))

        return gemini_tools

    def pretty_print(self, contents: List[types.Content]) -> str:
        """
        Format content list for readable logging.

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
                    [f"{attr}: {str(val).strip()}"
                     for attr, val in part.__dict__.items()
                     if val is not None]
                )
                content_parts.append(part_attrs)

            parts.append(f"Content {i + 1}:\n - {content.role}: {'; '.join(content_parts)}")

        return "\n".join(parts)

    def manage_conversation_history(
        self,
        messages: List[Any],
        max_tokens: int = MAX_TOKENS
    ) -> bool:
        """
        Ensure contents are within token limits by intelligently pruning when needed.

        Args:
            messages: List of content objects to manage
            max_tokens: Maximum token limit

        Returns:
            bool: True if successful, False if pruning failed
        """
        try:
            client = self.initialize_client()
            token_count = client.models.count_tokens(model=MODEL_NAME, contents=messages)

            # If within limits, no action needed
            if token_count.total_tokens <= max_tokens:
                return True

            logging.info(f"Token count {token_count.total_tokens} exceeds limit {max_tokens}, pruning...")

            # Keep first item (usually system message) and last N exchanges
            if len(messages) > 3:
                # Keep important context - first message and recent exchanges
                preserve_count = min(5, len(messages) // 2)
                messages[:] = [messages[0]] + messages[-preserve_count:]

                # Recheck token count
                token_count = client.models.count_tokens(model=MODEL_NAME, contents=messages)
                logging.info(f"After pruning: {token_count.total_tokens} tokens with {len(messages)} items")

                return token_count.total_tokens <= max_tokens

            # If conversation is small but still exceeding, we have a problem
            logging.warning(f"Cannot reduce token count sufficiently: {token_count.total_tokens}")
            return False

        except Exception as e:
            logging.error(f"Error managing tokens: {e}")
            return False

    def generate(
        self,
        client: genai.Client,
        model_name: Optional[str],
        system_message: str,
        messages: ProviderHistory,
        tools: List[Dict[str, Any]],
    ) -> Iterable[GenerateContentPartWrapper]:
        """
        Get API response from Gemini, process it and handle tool calls.

        Args:
            client: The Gemini client
            model_name: The model name to use
            system_message: The system message to send in the request
            messages: The messages to send in the request
            tools: The Gemini-format tools to use

        Returns:
            Iterable[GenerateContentPartWrapper]: An iterable of content parts
        """
        model_name = model_name or MODEL_NAME

        # Set up generation configuration
        generation_config = types.GenerateContentConfig(
            tools=tools,
            system_instruction=system_message,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode='AUTO')
            )
        )

        # Get the response stream
        response_stream = client.models.generate_content_stream(
            model=model_name,
            contents=messages,
            config=generation_config
        )
        for chunk in response_stream:
            logging.debug("Raw Gemini response: %s", chunk)

            if not chunk.candidates:
                continue

            for part in chunk.candidates[0].content.parts:
                yield GenerateContentPartWrapper(part)

            if chunk.candidates[0].finish_reason == 'MALFORMED_FUNCTION_CALL':
                msg = "Received MALFORMED_FUNCTION_CALL"
                if len(chunk.candidates) > 1:
                    msg += f" (there were {len(chunk.candidates)} other candidates in the response: "
                    msg += ", ".join([f"'{c.finish_reason}'" for c in chunk.candidates[1:]]) + ")"

                raise ValueError(msg)


    def append_to_history(self, provider_history: ProviderHistory,
                             turn: List[ChunkWrapper | ContentPartToolResult]):
        """
        Add turn items into provider's conversation history.

        Args:
            provider_history: List of provider-specific message objects
            turn: List of items in this turn
        """
        # Separate chunks and tool results
        chunks: list[GenerateContentPartWrapper] = []
        tool_results: list[ContentPartToolResult] = []

        for item in turn:
            if isinstance(item, GenerateContentPartWrapper):
                chunks.append(item)
            elif isinstance(item, ContentPartToolResult):
                tool_results.append(item)

        # Add model message with all text and tool calls
        model_message = self._adapter.to_history_item(chunks)
        if model_message:
            provider_history.append(model_message)

        # Add tool results if any exist
        tool_results_message = self._adapter.to_history_item(tool_results)
        if tool_results_message:
            provider_history.append(tool_results_message)