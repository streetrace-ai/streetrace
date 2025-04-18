# app/interaction_manager.py
import logging
from typing import List, Optional

from streetrace.llm.history_converter import ChunkWrapper
from streetrace.llm.llmapi import LLMAPI
from streetrace.llm.wrapper import ContentPartToolResult, History
from streetrace.tools.tools import ToolCall

# Assuming these are accessible
from streetrace.ui.console_ui import ConsoleUI

logger = logging.getLogger(__name__)


class InteractionManager:
    """
    Handles the core interaction with the AI model via generate_with_tools.

    Encapsulates the provider, model, tools, tool callback, and error handling
    for the AI generation process.
    """

    def __init__(
        self,
        provider: LLMAPI,
        model_name: Optional[str],
        tools: ToolCall,
        ui: ConsoleUI,
    ):
        """
        Initializes the InteractionManager.

        Args:
            provider: The initialized AI provider instance (e.g., ClaudeProvider).
            model_name: The specific model name to use (or None for provider default).
            tools: Tool call implementaiton that defines tools provided to the AI.
            tool_callback: The function to execute tool calls requested by the AI.
                           Expected signature: tool_callback(tool_name, args, original_call) -> result_dict
            ui: The ConsoleUI instance for displaying errors.
        """
        self.provider = provider
        self.model_name = model_name
        self.tools = tools
        self.ui = ui
        logger.info(
            f"InteractionManager initialized for provider: {type(provider).__name__}"
        )

    def process_prompt(self, history: History):
        """
        Processes the prompt by calling the AI with the provided history.

        Handles potential exceptions during the AI generation call and displays
        errors using the ConsoleUI. Modifies the history object in place.

        Args:
            history: The conversation History object containing the context and prompt.
        """
        logger.debug("Initiating AI generation call.")
        provider_history = None # Initialize in case client init fails
        try:
            # generate_with_tools handles the conversation loop (user -> AI -> tool -> AI ...)
            # and potentially modifies the history object directly.
            # It also likely handles streaming output internally for now.
            # TODO: Refactor generate_with_tools to accept UI for streaming output
            client = self.provider.initialize_client()
            provider_history = self.provider.transform_history(history)
            provider_tools = self.provider.transform_tools(self.tools.tools)

            # Ensure history fits the context window
            if not self.provider.manage_conversation_history(provider_history):
                raise ValueError(
                    "Conversation history exceeds the model's context window."
                )

            request_count = 0
            has_tool_calls = False
            finish_reason = None

            # Continue generating responses and handling tool calls until complete
            while has_tool_calls or not finish_reason:
                has_tool_calls = False
                finish_reason = None
                request_count += 1
                logging.info(
                    f"Starting request {request_count} with {len(provider_history)} message items."
                )
                logging.debug(
                    "Messages for generation:\n%s",
                    self.provider.pretty_print(provider_history),
                )

                # The condition to stop is when there are no tool calls and no finish message in this turn
                turn: List[ChunkWrapper | ContentPartToolResult] = []
                with self.ui.status("Working..."):
                    for chunk in self.provider.generate(
                        client,
                        self.model_name,
                        history.system_message,
                        provider_history,
                        provider_tools,
                    ):
                        if chunk.get_finish_message():
                            finish_reason = chunk.get_finish_message()
                            break
                        turn.append(chunk)
                        if chunk.get_text():
                            self.ui.display_ai_response_chunk(chunk.get_text())
                        if chunk.get_tool_calls():
                            for tool_call in chunk.get_tool_calls():
                                self.ui.display_tool_call(tool_call)
                                logging.info(
                                    f"Tool call: {tool_call.name} with args: {tool_call.arguments}"
                                )
                                tool_result = self.tools.call_tool(tool_call, chunk.raw)
                                if tool_result.success:
                                    self.ui.display_tool_result(tool_result)
                                    logging.info(
                                        f"Tool '{tool_call.name}' result: {tool_result.output.content}'"
                                    )
                                else:
                                    self.ui.display_tool_error(tool_result)
                                    logging.error(tool_result.output.content)
                                turn.append(
                                    ContentPartToolResult(
                                        id=tool_call.id,
                                        name=tool_call.name,
                                        content=tool_result,
                                    )
                                )
                                has_tool_calls = True

                self.provider.append_to_history(provider_history, turn)
            self.ui.display_info(finish_reason)
            self.provider.update_history(provider_history, history)
        except Exception as gen_err:
            # --- Added history update here ---
            if provider_history is not None:
                try:
                    self.provider.update_history(provider_history, history)
                    logger.info("History updated with partial results before exception.")
                except Exception as update_err:
                    # Log if updating history itself fails, but don't overwrite original error
                    logger.error(f"Failed to update history after generation error: {update_err}", exc_info=update_err)
            # -----------------------------------

            # Use the UI instance to display the original error
            error_message = f"An error occurred during AI generation: {gen_err}"
            self.ui.display_error(error_message)
            # Log the full exception traceback for the original error
            logger.exception(
                "An error occurred during AI generation call.", exc_info=gen_err
            )
