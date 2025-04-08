"""
Gemini AI Provider Implementation

This module implements the LLMAPI interface for Google's Gemini models.
"""

import json
import os
import logging
from typing import Iterable, List, Dict, Any, Optional, override

from google import genai
from google.genai import types
from colors import AnsiColors
from llm.llmapi import LLMAPI
from llm.wrapper import ChunkWrapper, ContentPart, ContentPartText, ContentPartToolCall, ContentPartToolResult, ContentType, History, ToolResult

ProviderHistory = List[types.Content]

# Constants
MAX_TOKENS = 2**20
MODEL_NAME = 'gemini-2.5-pro-exp-03-25'
MAX_MALFORMED_RETRIES = 3  # Maximum number of retries for malformed function calls

class GenerateContentPartWrapper(ChunkWrapper):
    def __init__(self, chunk: types.Part):
        self.raw = chunk

    @override
    def type(self) -> ContentType:
        if self.raw.text:
            return ContentType.TEXT
        if self.raw.function_call:
            return ContentType.TOOL_CALL
        else:
            raise ValueError(f"Unknown content block type encountered {type(self.raw)}: {self.raw}")

    @override
    def get_text(self) -> str:
        return self.raw.text

    @override
    def get_tool_calls(self) -> List[ContentPartToolCall]:
        return [ContentPartToolCall(self.raw.function_call.id, self.raw.function_call.name, self.raw.function_call.args)]


def _from_part(part: ContentPart) -> types.Part:
    """Convert a ContentPart to Gemini-specific part."""
    match part:
        case ContentPartText():
            return types.Part.from_text(text=part.text)
        case ContentPartToolCall():
            return types.Part.from_function_call(
                id=part.id,
                name=part.name,
                args=part.arguments
            )
        case ContentPartToolResult():
            return types.Part.from_function_response(
                id=part.id,
                name=part.name,
                response=part.content)
        case _:
            raise ValueError(f"Unknown content type encountered {type(part)}: {part}")

def _to_part(part: types.Part) -> ContentPart:
    """Convert a Gemini-specific part to ContentPart."""
    if part.text:
        return ContentPartText(part.text)
    elif part.function_call:
        return ContentPartToolCall(
            part.function_call.id,
            part.function_call.name,
            part.function_call.args)
    elif part.function_response:
        return ContentPartToolResult(
            part.function_response.id,
            part.function_response.name,
            part.function_response.response)
    else:
        # Handle unknown content types
        raise ValueError(f"Unknown content type encountered {type(part)}: {part}")

class Gemini(LLMAPI):
    """
    Implementation of the LLMAPI interface for Google's Gemini models.
    """

    _counter = 0

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
        provider_history: ProviderHistory = []

        if history.context:
            provider_history.append(types.Content(
                role='user',
                parts=[types.Part.from_text(text=history.context)]
            ))

        for message in history.conversation:
            provider_history.append(types.Content(
                    role=message.role,
                    parts=[_from_part(part) for part in message.content]
                ))

        return provider_history

    def update_history(self, provider_history: ProviderHistory, history: History) -> None:
        """
        Updates the conversation history in common format based on Gemini-specific history.

        Args:
            provider_history (List[Dict[str, Any]]): Gemini-specific conversation history
            history (History): Conversation history in common format
        """
        history.conversation = []
        start_index = 0
        # if we expect to have a context message, skip the first message of the history
        # as it is the context message
        if history.context and provider_history[0].role == 'user':
            start_index = 1

        for content in provider_history[start_index:]:
            history.add_message(
                content.role,
                [_to_part(part) for part in content.parts]
            )

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
        conversation: History,
        messages: ProviderHistory,
        tools: List[Dict[str, Any]],
    ) -> Iterable[GenerateContentPartWrapper]:
        """
        Get API response from Gemini, process it and handle tool calls.

        Args:
            client: The Gemini client
            model_name: The model name to use
            conversation: The common conversation history
            messages: The messages to send in the request
            tools: The Gemini-format tools to use

        Returns:
            Tuple:
                - Any: The raw API response
                - List[Dict[str, Any]]: The updated messages
                - bool: Whether any tool calls were made
        """
        model_name = model_name or MODEL_NAME

        # Set up generation configuration
        generation_config = types.GenerateContentConfig(
            tools=tools,
            system_instruction=conversation.system_message,
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

            for part in chunk.candidates[0].content.parts:
                yield GenerateContentPartWrapper(part)

            if chunk.candidates[0].finish_reason == 'MALFORMED_FUNCTION_CALL':
                msg = "Received MALFORMED_FUNCTION_CALL"
                if len(chunk.candidates) > 1:
                    msg += f" (there were {len(chunk.candidates)} other candidates in the response: "
                    msg += ", ".join([f"'{c.finish_reason}'" for c in chunk.candidates[1:]]) + ")"

                raise ValueError(msg)


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
            if isinstance(block, GenerateContentPartWrapper):
                model_messages.append(block.raw)
            elif isinstance(block, ToolResult):
                # Add tool result to outputs
                tool_results.append(types.Part(
                    function_response=types.FunctionResponse(
                        id=block.tool_call.id,
                        name=block.tool_call.name,
                        response=block.tool_result
                    )
                ))

        provider_history.append(
            types.Content(
                role = 'model',
                parts = model_messages
            )
        )

        # Only add tool results if there are any
        if tool_results:
            provider_history.append(
                types.Content(
                    role = 'tool',
                    parts = tool_results
                )
            )
