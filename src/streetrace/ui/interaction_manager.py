# app/interaction_manager.py
import logging
from typing import Any, Callable, Dict, List, Optional

from streetrace.llm.generate import generate_with_tools

# Assuming these are accessible
from streetrace.llm.wrapper import History
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
        provider: Any,
        model_name: Optional[str],
        tools: List[Dict[str, Any]],
        tool_callback: Callable,
        ui: ConsoleUI,
    ):
        """
        Initializes the InteractionManager.

        Args:
            provider: The initialized AI provider instance (e.g., ClaudeProvider).
            model_name: The specific model name to use (or None for provider default).
            tools: The list of tool definitions provided to the AI.
            tool_callback: The function to execute tool calls requested by the AI.
                           Expected signature: tool_callback(tool_name, args, original_call) -> result_dict
            ui: The ConsoleUI instance for displaying errors.
        """
        self.provider = provider
        self.model_name = model_name
        self.tools = tools
        self.tool_callback = tool_callback
        self.ui = ui
        logger.info(
            f"InteractionManager initialized for provider: {type(provider).__name__}"
        )

    def process_prompt(self, history: History):
        """
        Processes the prompt by calling the AI with the provided history and tools.

        Handles potential exceptions during the AI generation call and displays
        errors using the ConsoleUI. Modifies the history object in place.

        Args:
            history: The conversation History object containing the context and prompt.
        """
        logger.debug("Initiating AI generation call.")
        try:
            # generate_with_tools handles the conversation loop (user -> AI -> tool -> AI ...)
            # and potentially modifies the history object directly.
            # It also likely handles streaming output internally for now.
            # TODO: Refactor generate_with_tools to accept UI for streaming output
            generate_with_tools(
                self.provider,
                self.model_name,
                history,
                self.tools,
                self.tool_callback,
            )
            logger.debug("AI generation call completed successfully.")
        except Exception as gen_err:
            # Use the UI instance to display the error
            error_message = f"An error occurred during AI generation: {gen_err}"
            self.ui.display_error(error_message)
            # Log the full exception traceback
            logger.exception(
                "An error occurred during AI generation call.", exc_info=gen_err
            )
            # Depending on desired behavior, we might want to re-raise,
            # return an error status, or just let the main loop continue.
            # For interactive mode, allowing continuation seems reasonable.
