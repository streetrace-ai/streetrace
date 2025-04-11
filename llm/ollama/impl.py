"""
Ollama Provider Implementation

This module implements the LLMAPI interface for Ollama models.
"""

import os
import logging
import time
import json
from typing import List, Dict, Any, Callable, Optional, Union, Tuple

import ollama
from colors import AnsiColors
from llm.llmapi import LLMAPI

# Constants
MAX_TOKENS = 32768  # Default context window for most Ollama models
MODEL_NAME = "llama3:8b"  # Default model


class Ollama(LLMAPI):
    """
    Implementation of the LLMAPI interface for Ollama models.
    """

    def get_base_url(self) -> str:
        """Get the base URL for Ollama API, defaulting to localhost if not specified."""
        return os.environ.get('OLLAMA_API_URL', 'http://localhost:11434')

    def initialize_client(self) -> ollama.Client:
        """
        Initialize and return the Ollama API client.

        Returns:
            ollama.Client: The initialized Ollama client
        """
        return ollama.Client(
            host=self.get_base_url(),
            headers={'x-some-header': 'some-value'}
        )

    def transform_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform tools from common format to Ollama-specific format.

        Args:
            tools: List of tool definitions in common format

        Returns:
            List[Dict[str, Any]]: List of tool definitions in Ollama format
        """
        ollama_tools = tools
        return ollama_tools

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

    def prepare_conversation(
        self,
        conversation_history: List[Dict[str, Any]],
        system_message: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Prepare the conversation history with system message if needed.

        Args:
            conversation_history: The current conversation history
            system_message: The system message to use

        Returns:
            List[Dict[str, Any]]: The updated conversation history
        """
        if len(conversation_history) == 0:
            default_system_message = """You are an experienced software engineer implementing code for a project working as a peer engineer
with the user. Fullfill all your peer user's requests completely and following best practices and intentions.
If can't understand a task, ask for clarifications."""

            conversation_history.append({
                'role': 'system',
                'content': system_message or default_system_message,
            })

        return conversation_history

    def add_project_context(
        self,
        conversation_history: List[Dict[str, Any]],
        project_context: str
    ) -> List[Dict[str, Any]]:
        """
        Add project context to the conversation history.

        Args:
            conversation_history: The current conversation history
            project_context: The project context to add

        Returns:
            List[Dict[str, Any]]: The updated conversation history
        """
        conversation_history.append({
            'role': 'user',
            'content': project_context
        })
        return conversation_history

    def add_user_prompt(
        self,
        conversation_history: List[Dict[str, Any]],
        prompt: str
    ) -> List[Dict[str, Any]]:
        """
        Add user prompt to the conversation history.

        Args:
            conversation_history: The current conversation history
            prompt: The user prompt to add

        Returns:
            List[Dict[str, Any]]: The updated conversation history
        """
        conversation_history.append({
            'role': 'user',
            'content': prompt
        })
        return conversation_history

    def get_api_response(
        self,
        client: ollama.Client,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        model_name: Optional[str] = MODEL_NAME,
        call_tool: Callable = None
    ) -> Tuple[Any, List[Dict[str, Any]], bool]:
        """
        Get API response from Ollama, process it and handle tool calls.

        Args:
            client: The Ollama client
            messages: The messages to send in the request
            tools: The Ollama-format tools to use
            model_name: The model name to use
            call_tool: The function to call tools

        Returns:
            Tuple:
                - Any: The raw API response
                - List[Dict[str, Any]]: The updated messages
                - bool: Whether any tool calls were made
        """
        model_name = model_name or MODEL_NAME
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:  # This loop handles retries for errors
            try:
                response = client.chat(model=model_name, messages=messages, tools=tools, stream=True)

                # Process the streamed response
                full_response = ""
                tool_calls = []
                tool_results = []

                for chunk in response:
                    if not chunk:
                        continue

                    try:
                        # Process message content
                        if chunk.message:
                            # Handle streaming text output
                            if chunk.message.content:
                                print(AnsiColors.MODEL + chunk.message.content + AnsiColors.RESET, end='')
                                full_response += chunk.message.content

                            # Handle tool calls
                            if chunk.message.tool_calls:
                                for tool_call in chunk.message.tool_calls:
                                    tool_calls.append(tool_call)
                                    function_name = tool_call.function.name
                                    function_args = tool_call.function.arguments

                                    print(AnsiColors.TOOL + f"{function_name}: {function_args}" + AnsiColors.RESET)
                                    logging.info(f"Tool call: {function_name} with {function_args}")

                                    # Execute the tool
                                    tool_result = call_tool(function_name, function_args, tool_call)

                                    # Add tool result to the list
                                    tool_results.append({
                                        "role": "tool",
                                        "name": function_name,
                                        "content": str(tool_result)
                                    })
                        # Check for end of response
                        if chunk.done:
                            break

                    except json.JSONDecodeError as e:
                        logging.warning(f"Error parsing JSON from stream: {e}")
                    except Exception as e:
                        logging.error(f"Error processing response chunk: {e}")

                # Add the assistant's response to conversation history
                assistant_message = {
                    'role': 'assistant'
                }

                # Only add if we have content
                if full_response.strip():
                    assistant_message['content'] = full_response

                if tool_calls:
                    assistant_message['tool_calls'] = tool_calls

                messages.append(assistant_message)

                if tool_results:
                    messages.extend(tool_results)

                # Determine if there were tool calls
                tool_calls_made = len(tool_results) > 0

                return response, messages, tool_calls_made

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