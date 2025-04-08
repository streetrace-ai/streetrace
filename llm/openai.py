"""
OpenAI Provider Implementation

This module implements the LLMAPI interface for OpenAI models.
"""

import os
import logging
import json
import time
from typing import List, Dict, Any, Callable, Optional, Tuple

import openai
from colors import AnsiColors
from llm.llmapi import LLMAPI

# Constants
MAX_TOKENS = 128000  # GPT-4 Turbo has a context window of 128K tokens
MODEL_NAME = "gpt-4-turbo-2024-04-09"  # Default model


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
        # Initialize conversation history with system message if empty
        if len(conversation_history) == 0:
            default_system_message = """You are an experienced software engineer implementing code for a project working as a peer engineer
with the user. Fullfill all your peer user's requests completely and following best practices and intentions.
If can't understand a task, ask for clarifications."""
            
            conversation_history.append({
                'role': 'system',
                'content': system_message or default_system_message
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
        client: openai.OpenAI,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        model_name: Optional[str] = MODEL_NAME,
        call_tool: Callable = None
    ) -> Tuple[Any, List[Dict[str, Any]], bool]:
        """
        Get API response from OpenAI, process it and handle tool calls.
        
        Args:
            client: The OpenAI client
            messages: The messages to send in the request
            tools: The OpenAI-format tools to use
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
                # Create the message with OpenAI
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=tools,
                    stream=True,
                    tool_choice="auto"
                )
                
                # Process the streamed response
                full_response = ""
                tool_calls = []
                tool_results = []

                for chunk in response:
                    logging.debug(f"Chunk received: {chunk}")
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    # Process message content
                    if delta.content:
                        print(AnsiColors.MODEL + delta.content + AnsiColors.RESET, end='')
                        full_response += delta.content

                    # Process tool calls
                    if delta.tool_calls:
                        for tool_call_delta in delta.tool_calls:
                            # Initialize or update the tool call in our tracking list
                            if tool_call_delta.index is not None:
                                idx = tool_call_delta.index

                                # Create a new tool call entry if this is a new index
                                if idx >= len(tool_calls):
                                    tool_calls.append({
                                        "id": tool_call_delta.id or "",
                                        "type": "function",
                                        "function": {
                                            "name": "",
                                            "arguments": ""
                                        }
                                    })

                                # Update name if provided
                                if tool_call_delta.function and tool_call_delta.function.name:
                                    tool_calls[idx]["function"]["name"] = tool_call_delta.function.name

                                # Update arguments if provided
                                if tool_call_delta.function and tool_call_delta.function.arguments:
                                    tool_calls[idx]["function"]["arguments"] += tool_call_delta.function.arguments

                # Process any complete tool calls
                for tool_call in tool_calls:
                    if tool_call["function"]["name"] and tool_call["function"]["arguments"]:
                        function_name = tool_call["function"]["name"]
                        try:
                            function_args = json.loads(tool_call["function"]["arguments"])
                        except json.JSONDecodeError:
                            # Handle case where arguments might not be valid JSON
                            logging.warning(f"Invalid JSON in arguments: {tool_call['function']['arguments']}")
                            function_args = {}

                        print(AnsiColors.TOOL + f"{function_name}: {function_args}" + AnsiColors.RESET)
                        logging.info(f"Tool call: {function_name} with {function_args}")

                        # Execute the tool
                        tool_result = call_tool(function_name, function_args, tool_call)

                        # Add tool result to the list
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": function_name,
                            "content": str(tool_result)
                        })

                # Add the assistant's response to conversation history
                if full_response.strip() or tool_calls:
                    assistant_message = {
                        'role': 'assistant',
                        'content': full_response
                    }

                    if tool_calls:
                        assistant_message['tool_calls'] = tool_calls

                    messages.append(assistant_message)

                    # Add tool results to the conversation history
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