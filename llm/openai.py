"""
OpenAI Provider Implementation

This module implements the LLMAPI interface for OpenAI models.
"""

import os
import logging
import json
import time
from typing import Iterable, List, Dict, Any, Optional, override

import openai
from openai.types import chat
from colors import AnsiColors
from llm.history_converter import ChunkWrapper
from llm.llmapi import LLMAPI
from llm.wrapper import ContentPartText, ContentPartToolCall, History, Role, ToolResult

# Constants
MAX_TOKENS = 128000  # GPT-4 Turbo has a context window of 128K tokens
MODEL_NAME = "gpt-4-turbo-2024-04-09"  # Default model

ProviderHistory = List[chat.ChatCompletionMessageParam]

_ROLES = {
    Role.SYSTEM: "system",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "tool",
}

class ChoiceDeltaWrapper(ChunkWrapper):
    def __init__(self, chunk: chat.chat_completion_chunk.ChoiceDelta):
        self.raw = chunk

    @override
    def get_text(self) -> str:
        return self.raw.content

    @override
    def get_tool_calls(self) -> List[ContentPartToolCall]:
        return [
            ContentPartToolCall(
                call.id,
                call.function.name,
                json.loads(call.function.arguments)
            ) for call in self.raw.tool_calls
        ] if self.raw.tool_calls else []

class OpenAI(LLMAPI):
    """
    Implementation of the LLMAPI interface for OpenAI models.
    """

    def initialize_client(self) -> openai.OpenAI:
        """
        Initialize and return the OpenAI API client.

        Returns:
            OpenAI: The initialized OpenAI client

        Raises:
            ValueError: If OPENAI_API_KEY environment variable is not set
        """
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")

        base_url = os.environ.get('OPENAI_API_BASE')
        if base_url:
            return openai.OpenAI(api_key=api_key, base_url=base_url)
        return openai.OpenAI(api_key=api_key)

    def transform_history(self, history: History) -> ProviderHistory:
        """
        Transform conversation history from common format into Gemini-specific format.

        Args:
            history (History): Conversation history to transform

        Returns:
            List[Dict[str, Any]]: Conversation history in Gemini-specific format
        """
        provider_history: ProviderHistory = []

        if history.system_message:
            provider_history.append(
                chat.ChatCompletionSystemMessageParam(
                    role = _ROLES[Role.SYSTEM],
                    content = [chat.ChatCompletionContentPartTextParam(type="text", text=history.context)]
                )
            )

        if history.context:
            provider_history.append(
                chat.ChatCompletionUserMessageParam(
                    role = _ROLES[Role.USER],
                    content = [chat.ChatCompletionContentPartTextParam(type="text", text=history.context)]
                )
            )

        for message in history.conversation:
            match message.role:
                case Role.USER:
                    provider_history.append(
                        chat.ChatCompletionUserMessageParam(
                            role = _ROLES[Role.USER],
                            content = [
                                chat.ChatCompletionContentPartTextParam(type="text", text=msg.text)
                                for msg in message.content
                            ]
                        )
                    )
                case Role.MODEL:
                    provider_history.append(
                        chat.ChatCompletionAssistantMessageParam(
                            role = _ROLES[Role.MODEL],
                            content = [
                                chat.ChatCompletionContentPartTextParam(type="text", text=msg.text)
                                for msg in message.content if type(msg) is ContentPartText
                            ],
                            tool_calls=[
                                chat.ChatCompletionMessageToolCallParam(
                                    id = msg.id,
                                    function = chat.Function(
                                        name = msg.name,
                                        arguments = json.dumps(msg.arguments)
                                    ))
                                for msg in message.content if type(msg) is ContentPartToolCall
                            ]
                        )
                    )
                case Role.TOOL:
                    provider_history.append(
                        chat.ChatCompletionToolMessageParam(
                            role = _ROLES[Role.TOOL],
                            content = [
                                chat.ChatCompletionContentPartTextParam(type="text", text=msg.text)
                                for msg in message.content
                            ]
                        )
                    )

        return provider_history

    def update_history(self, provider_history: ProviderHistory, history: History) -> None:
        """
        Updates the conversation history in common format based on Gemini-specific history.

        Args:
            provider_history (List[Dict[str, Any]]): Gemini-specific conversation history
            history (History): Conversation history in common format
        """
        history.conversation = []
        expect_context = False
        if history.context:
            expect_context = True

        tool_use_names = {}

        for message in provider_history:
            if type(message) is chat.ChatCompletionAssistantMessageParam and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_use_names[tool_call.id] = tool_call.function.name

        for message in provider_history:
            match message:
                case chat.ChatCompletionSystemMessageParam():
                    history.system_message = message.get('content')
                case chat.ChatCompletionUserMessageParam():
                    if expect_context:
                        history.context = message.get('content')
                        expect_context = False
                    elif type(message.get('content')) is str:
                        history.add_message(
                            Role.USER,
                            [ContentPartText(message.get('content'))]
                        )
                    else:
                        history.add_message(
                            Role.USER,
                            [ContentPartText(part) for part in message.get('content')]
                        )
                case chat.ChatCompletionAssistantMessageParam():
                    content = message.get('content')
                    if not isinstance(content, list):
                        content = [content]
                    text_parts = [ContentPartText(part) for part in content]
                    tool_calls = [ContentPartToolCall(
                        part.id,
                        part.function.name,
                        json.loads(part.function.arguments)) for part in message.get('tool_calls')]
                    history.add_message(
                        Role.MODEL,
                        text_parts + tool_calls
                    )
                case chat.ChatCompletionToolMessageParam():
                    history.add_message(
                        Role.TOOL,
                        [ContentPartToolCall(
                            message.tool_call_id,
                            tool_use_names[message.tool_call.id],
                            json.loads(message.get('content')))
                         ]
                    )

    def transform_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform tools from common format to OpenAI-specific format.

        Args:
            tools: List of tool definitions in common format

        Returns:
            List[Dict[str, Any]]: List of tool definitions in OpenAI format
        """
        return tools

    def pretty_print(self, messages: List[Dict[str, Any]]) -> str:
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

    def manage_conversation_history(
        self,
        conversation_history: List[Dict[str, Any]],
        max_tokens: int = MAX_TOKENS
    ) -> bool:
        """
        Ensure conversation history is within token limits by intelligently pruning when needed.

        Args:
            conversation_history: List of message objects to manage
            max_tokens: Maximum token limit

        Returns:
            bool: True if successful, False if pruning failed
        """
        try:
            # Simplified token count estimation - would need actual token counting in production
            # This is a placeholder for an actual token counting function
            estimated_tokens = sum(len(str(msg)) for msg in conversation_history) // 4

            # If within limits, no action needed
            if estimated_tokens <= max_tokens:
                return True

            logging.info(f"Estimated token count {estimated_tokens} exceeds limit {max_tokens}, pruning...")

            # Keep first item (usually system message) and last N exchanges
            if len(conversation_history) > 3:
                # Keep important context - first message and recent exchanges
                preserve_count = min(5, len(conversation_history) // 2)
                conversation_history[:] = [conversation_history[0]] + conversation_history[-preserve_count:]

                # Recheck token count
                estimated_tokens = sum(len(str(msg)) for msg in conversation_history) // 4
                logging.info(f"After pruning: {estimated_tokens} tokens with {len(conversation_history)} items")

                return estimated_tokens <= max_tokens

            # If conversation is small but still exceeding, we have a problem
            logging.warning(f"Cannot reduce token count sufficiently: {estimated_tokens}")
            return False

        except Exception as e:
            logging.error(f"Error managing tokens: {e}")
            return False

    def generate(
        self,
        client: openai.OpenAI,
        model_name: Optional[str],
        conversation: History,
        messages: ProviderHistory,
        tools: List[Dict[str, Any]],
    ) -> Iterable[ChoiceDeltaWrapper]:
        """
        Get API response from OpenAI, process it and handle tool calls.

        Args:
            client: The OpenAI client
            model_name: The model name to use
            conversation: The common conversation history
            messages: The messages to send in the request
            tools: The Gemini-format tools to use

        Returns:
            Iterable[ChoiceDeltaWrapper]: Stream of response chunks
        """
        model_name = model_name or MODEL_NAME
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:  # This loop handles retries for errors
            try:
                print(f"Sending to openai: {messages}")
                exit(0)
                # Create the message with OpenAI
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=tools,
                    stream=True,
                    tool_choice="auto"
                )

                # Process the streamed response
                for chunk in response:
                    logging.debug(f"Chunk received: {chunk}")
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    yield ChoiceDeltaWrapper(delta)

            except Exception as e:
                retry_count += 1

                if retry_count >= max_retries:
                    error_msg = f"Failed after {max_retries} retries: {e}"
                    logging.error(error_msg)
                    print(AnsiColors.MODELERROR + error_msg + AnsiColors.RESET)
                    raise

                wait_time = 5 * retry_count  # Increase wait time with each retry

                error_msg = f"API error encountered. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries}): {e}"
                logging.warning(error_msg)
                print(AnsiColors.WARNING + error_msg + AnsiColors.RESET)

                time.sleep(wait_time)

    def append_to_history(self, provider_history: ProviderHistory,
                                turn: List[ChunkWrapper | ToolResult]):
        """
        Add turn items into provider's conversation history.

        Args:
            provider_history: List of provider-specific message objects
            turn: List of items in this turn
        """
        for block in turn:
            if isinstance(block, ChoiceDeltaWrapper):
                provider_history.append(chat.ChatCompletionAssistantMessageParam(
                    role=_ROLES[Role.MODEL],
                    content=block.raw.content,
                    tool_calls=[
                        chat.ChatCompletionMessageToolCallParam(
                            type = 'function',
                            id = call.id,
                            function = chat.Function(
                                name = call.function.name,
                                arguments = call.function.arguments
                            )
                        )
                        for call in block.raw.tool_calls]))
            elif isinstance(block, ToolResult):
                # Add tool result to outputs
                provider_history.append(chat.ChatCompletionToolMessageParam(
                    role = _ROLES[Role.TOOL],
                    tool_call_id = block.tool_call.id,
                    content = json.dumps(block.tool_result)
                ))
