"""
Generate Module

This module provides a provider-independent implementation of generate_with_tool
that can be used by all LLMAPI-derived classes.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from streetrace.llm.history_converter import ChunkWrapper
from streetrace.llm.llmapi import LLMAPI
from streetrace.llm.wrapper import ContentPartToolResult, History
from streetrace.ui.colors import AnsiColors


def generate_with_tools(
    provider: LLMAPI,
    model_name: Optional[str],
    conversation: History,
    tools: List[Dict[str, Any]],
    call_tool: Callable,
):
    """
    Each provider will implement their provider-specific API calls by passing
    themselves as the 'provider' parameter.

    Args:
        provider: The LLMAPI-derived provider instance with provider-specific methods
        model_name: The name of the AI model to use
        conversation_history: The history of the conversation
        tools: List of tool definitions in common format
        call_tool: Function to call for tool execution
    """
    client = provider.initialize_client()
    provider_history = provider.transform_history(conversation)
    provider_tools = provider.transform_tools(tools)

    try:
        _generate_with_tools(
            provider,
            client,
            model_name,
            conversation.system_message,
            provider_history,
            provider_tools,
            call_tool,
        )
        provider.update_history(provider_history, conversation)
    except Exception as e:
        print(AnsiColors.MODELERROR + str(e) + AnsiColors.RESET)
        logging.exception(f"Error during generation: {e}")


def _generate_with_tools(
    provider: LLMAPI,
    client: Any,
    model_name: Optional[str],
    system_message: str,
    provider_history: List[Dict[str, Any]],
    provider_tools: List[Dict[str, Any]],
    f_call_tool: Callable,
):

    # Ensure history fits the context window
    if not provider.manage_conversation_history(provider_history):
        raise ValueError("Conversation history exceeds the model's context window.")

    request_count = 0
    continue_generation = True

    # Continue generating responses and handling tool calls until complete
    while continue_generation:
        continue_generation = False
        request_count += 1
        logging.info(
            f"Starting request {request_count} with {len(provider_history)} message items."
        )
        logging.debug(
            "Messages for generation:\n%s", provider.pretty_print(provider_history)
        )

        turn: List[ChunkWrapper | ContentPartToolResult] = []
        for chunk in provider.generate(
            client, model_name, system_message, provider_history, provider_tools
        ):
            turn.append(chunk)
            if chunk.get_text():
                print(
                    AnsiColors.MODEL + chunk.get_text() + AnsiColors.RESET,
                    end="",
                    flush=True,
                )
            if chunk.get_tool_calls():
                print()
                for tool_call in chunk.get_tool_calls():
                    tool_result = f_call_tool(
                        tool_call.name, tool_call.arguments, chunk.raw
                    )
                    turn.append(
                        ContentPartToolResult(
                            id=tool_call.id, name=tool_call.name, content=tool_result
                        )
                    )
                continue_generation = True  # Continue if there were tool calls
        print()

        provider.append_to_history(provider_history, turn)
