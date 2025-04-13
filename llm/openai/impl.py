"""
OpenAI Provider Implementation

This module implements the LLMAPI interface for OpenAI models.
"""

import os
import logging
import time
from typing import Iterable, List, Dict, Any, Optional

import openai
from openai.types import chat
from colors import AnsiColors
from llm.history_converter import ChunkWrapper
from llm.llmapi import LLMAPI
from llm.wrapper import History, Role, ToolResult
from llm.openai.converter import OpenAIConverter, ChoiceDeltaWrapper

# Constants
MAX_TOKENS = 128000  # GPT-4 Turbo has a context window of 128K tokens
MODEL_NAME = "gpt-4-turbo-2024-04-09"  # Default model

ProviderHistory = List[chat.ChatCompletionMessageParam]

class OpenAI(LLMAPI):
    """
    Implementation of the LLMAPI interface for OpenAI models.
    """

    _adapter = OpenAIConverter()

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
        Transform conversation history from common format into OpenAI-specific format.

        Args:
            history (History): Conversation history to transform

        Returns:
            List[Dict[str, Any]]: Conversation history in OpenAI-specific format
        """
        return self._adapter.from_history(history)

    def update_history(self, provider_history: ProviderHistory, history: History) -> None:
        """
        Updates the conversation history in common format based on OpenAI-specific history.

        Args:
            provider_history (List[Dict[str, Any]]): OpenAI-specific conversation history
            history (History): Conversation history in common format
        """
        # Replace the conversation with the new messages
        history.conversation = self._adapter.to_history(provider_history)
        if history.context and history.conversation[0].role == Role.USER:
            del history.conversation[0]

    def transform_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform tools from common format to OpenAI-specific format.

        Args:
            tools: List of tool definitions in common format

        Returns:
            List[Dict[str, Any]]: List of tool definitions in OpenAI format
        """
        # OpenAI's tool format is already compatible with the common format
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
        system_message: str,
        messages: ProviderHistory,
        tools: List[Dict[str, Any]],
    ) -> Iterable[ChoiceDeltaWrapper]:
        """
        Get API response from OpenAI, process it and handle tool calls.

        Args:
            client: The OpenAI client
            model_name: The model name to use
            system_message: Not used in OpenAI (processed as a part of conversation history)
            messages: The messages to send in the request
            tools: The tools to use

        Returns:
            Iterable[ChoiceDeltaWrapper]: Stream of response chunks
        """
        model_name = model_name or MODEL_NAME
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:  # This loop handles retries for errors
            try:
                # Create the message with OpenAI
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=tools,
                    stream=True,
                    tool_choice="auto"
                )

                # Process the streamed response
                buffered_tool_calls = {}
                for chunk in response:
                    logging.debug(f"Chunk received: {chunk}")
                    if not hasattr(chunk, 'choices'):
                        continue

                    for idx, choice in enumerate(chunk.choices):
                        delta = choice.delta
                        finish_reason = choice.finish_reason

                        if finish_reason == "tool_calls":
                            # Yield full tool_call block if finished
                            tool_call_msg = buffered_tool_calls.pop(idx, None)
                            if tool_call_msg:
                                yield ChoiceDeltaWrapper(chat.ChatCompletionMessage(
                                    role = delta.role or "assistant",
                                    tool_calls=[
                                        chat.ChatCompletionMessageToolCall(
                                            type="function",
                                            id = tool_call['id'],
                                            function = chat.chat_completion_message_tool_call.Function(
                                                name=tool_call['function']['name'],
                                                arguments=tool_call['function']['arguments']
                                            )
                                        ) for tool_call in tool_call_msg['tool_calls']
                                    ]
                                ))
                            continue

                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            # Start or continue buffering tool_call
                            if idx not in buffered_tool_calls:
                                buffered_tool_calls[idx] = {"tool_calls": []}

                            for i, tool_delta in enumerate(delta.tool_calls):
                                # Ensure space for tool_calls[i]
                                while len(buffered_tool_calls[idx]["tool_calls"]) <= i:
                                    buffered_tool_calls[idx]["tool_calls"].append({
                                        "id": None, "function": {"name": "", "arguments": ""},
                                        "type": "function"
                                    })

                                existing = buffered_tool_calls[idx]["tool_calls"][i]
                                if tool_delta.id:
                                    existing["id"] = tool_delta.id
                                if tool_delta.function:
                                    if tool_delta.function.name:
                                        existing["function"]["name"] += tool_delta.function.name
                                    if tool_delta.function.arguments:
                                        existing["function"]["arguments"] += tool_delta.function.arguments
                        elif delta.content is not None: # Important, do not check for Truthy as '' messages can contain other fields.
                            # Yield regular text deltas immediately
                            yield ChoiceDeltaWrapper(delta)

                break

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
        # Separate chunks and tool results
        chunks = []
        tool_results = []

        for item in turn:
            if isinstance(item, ChoiceDeltaWrapper):
                chunks.append(item)
            elif isinstance(item, ToolResult):
                tool_results.append(item)

        # Add assistant message with all text and tool calls
        assistant_message = self._adapter.to_history_item(chunks)
        if assistant_message:
            provider_history.append(assistant_message)

        # Add tool results if any exist
        # OpenAI expects one message per tool result
        for result in tool_results:
            tool_result_message = self._adapter.to_history_item([result])
            if tool_result_message:
                provider_history.append(tool_result_message)