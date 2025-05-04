"""Orchestrate the StreetRace application flow and manage component interactions.

This module contains the Application class which serves as the central
coordinator for the StreetRace application, handling the interaction between
components and managing the application lifecycle.
"""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from streetrace.commands.command_executor import CommandExecutor
from streetrace.history import History  # Keep for non-interactive temporary history
from streetrace.interaction_manager import InteractionManager
from streetrace.prompt_processor import PromptProcessor
from streetrace.tools.tools import ToolCall
from streetrace.ui.console_ui import ConsoleUI

if TYPE_CHECKING:
    # Avoid circular import, only needed for type hinting
    from streetrace.history_manager import HistoryManager


logger = logging.getLogger(__name__)


@dataclass
class ApplicationConfig:
    """Configuration for the Application class."""

    working_dir: Path
    non_interactive_prompt: str | None = None
    initial_model: str | None = None
    tools: ToolCall | None = None


class Application:
    """Orchestrates the StreetRace application flow."""

    def __init__(  # noqa: PLR0913 - Many dependencies needed for orchestration
        self,
        app_config: ApplicationConfig,
        ui: ConsoleUI,
        cmd_executor: CommandExecutor,
        prompt_processor: PromptProcessor,
        interaction_manager: InteractionManager,
        history_manager: "HistoryManager",
    ) -> None:
        """Initialize the Application with necessary components and configuration.

        Args:
            app_config: App configuration parameters.
            ui: ConsoleUI instance for handling user interaction and displaying output.
            cmd_executor: CommandExecutor instance for processing internal commands.
            prompt_processor: PromptProcessor instance for building context and processing prompts.
            interaction_manager: InteractionManager instance for handling AI model interactions.
            history_manager: HistoryManager instance for managing conversation history.

        """
        self.config = app_config
        self.ui = ui
        self.cmd_executor = cmd_executor
        self.prompt_processor = prompt_processor
        self.interaction_manager = interaction_manager
        self.history_manager = history_manager
        logger.info("Application initialized.")

    def run(self) -> None:
        """Start the application execution based on provided arguments."""
        if self.config.non_interactive_prompt:
            self._run_non_interactive()
        else:
            self._run_interactive()

    def _run_non_interactive(self) -> None:
        """Handle non-interactive mode (single prompt execution)."""
        prompt_input = self.config.non_interactive_prompt
        # According to coding guide, core components should be fail-fast.
        # Raise if non_interactive_prompt is unexpectedly None.
        if prompt_input is None:
            error_msg = "Non-interactive mode requires a prompt, but none was provided."
            logger.error(error_msg)
            # Use ValueError for invalid configuration/state
            raise ValueError(error_msg)

        self.ui.display_user_prompt(prompt_input)

        command_executed, _ = self.cmd_executor.execute(prompt_input, self)

        if command_executed:
            logger.info(
                "Non-interactive prompt was command: '%s'. Exiting.",
                prompt_input,
            )
            sys.exit(0)
        else:
            logger.info("Processing non-interactive prompt.")
            prompt_context = self.prompt_processor.build_context(
                prompt_input,
                self.config.working_dir,
            )
            single_prompt_history = History(
                system_message=prompt_context.system_message,
                context=prompt_context.project_context,
            )
            self._add_mentions_to_temporary_history(
                prompt_context.mentioned_files,
                single_prompt_history,
            )
            single_prompt_history.add_user_message(prompt_input)
            logger.debug(
                "User prompt added to single-use history",
                extra={"prompt_input": prompt_input},
            )
            self.interaction_manager.process_prompt(
                self.config.initial_model,
                single_prompt_history,
                self.config.tools,
            )
            logger.info("Non-interactive mode finished.")

    def _process_interactive_input(self, user_input: str) -> None:
        """Process a single user input during interactive mode."""
        # Get current history from the manager
        current_history = self.history_manager.get_history()

        # Ensure history exists before proceeding
        if not current_history:
            logger.error(
                "Conversation history is missing. Attempting to reset.",
            )
            self.history_manager.clear_history()
            # Check if reset was successful
            current_history = self.history_manager.get_history()
            if not current_history:
                self.ui.display_error(
                    "Critical error: History missing and could not be reset.",
                )
                # Assign error message to variable before raising
                error_msg = "Exiting due to critical history reset failure."
                raise SystemExit(error_msg)
            return  # Return to prompt after successful reset

        if user_input.strip():
            # Build context mainly for mentions specific to this input
            prompt_specific_context = self.prompt_processor.build_context(
                user_input,
                self.config.working_dir,
            )

            # Add mentioned files and the user prompt via HistoryManager
            self.history_manager.add_mentions_to_history(
                prompt_specific_context.mentioned_files,
            )
            self.history_manager.add_user_message(user_input)
            logger.debug(
                "User prompt added to interactive history",
                extra={"user_input": user_input},
            )

        # Process with InteractionManager using the persistent history
        self.interaction_manager.process_prompt(
            self.config.initial_model,
            current_history,
            self.config.tools,
        )

    def _run_interactive(self) -> None:
        """Handle interactive mode (conversation loop)."""
        self.ui.display_info(
            "Entering interactive mode. Type '/history', '/compact', '/clear', '/exit', or press Ctrl+C/Ctrl+D to quit.",
        )
        self.history_manager.initialize_history()

        while True:
            try:
                user_input = self.ui.prompt()
                if user_input.strip() == "/__reprompt":
                    continue

                command_executed, should_continue = self.cmd_executor.execute(
                    user_input,
                    self,
                )

                if command_executed:
                    if not should_continue:
                        self.ui.display_info("Leaving...")
                        break  # Exit loop for exit command
                    continue  # Continue loop for other commands (history, clear, compact)

                # If not a command, process the input as a prompt
                self._process_interactive_input(user_input)

            except (EOFError, KeyboardInterrupt):
                self.ui.display_info("\nExiting.")
                logger.info("Exiting due to user interruption (EOF/KeyboardInterrupt).")
                break
            except SystemExit:
                # Use logging.exception for exceptions, no need for message arg
                logger.exception("Exiting due to SystemExit")
                break
            except Exception as loop_err:
                self.ui.display_error(
                    f"\nAn unexpected error occurred in the interactive loop: {loop_err}",
                )
                logger.exception(
                    "Unexpected error in interactive loop.",
                    exc_info=loop_err,
                )
                # Continue loop after displaying error

    # Keep a private helper for non-interactive mode's temporary history
    def _add_mentions_to_temporary_history(
        self,
        mentioned_files: list[tuple[str, str]],
        history: History,
    ) -> None:
        """Add content from mentioned files to a temporary History object."""
        if not mentioned_files:
            return

        # Rename local variable to lowercase
        max_mention_content_length = 20000

        for filepath, content in mentioned_files:
            context_title = filepath
            context_message = content
            if len(content) > max_mention_content_length:
                context_title = f"{filepath} (truncated)"
                context_message = content[:max_mention_content_length]
                logger.warning(
                    "Truncated content for mentioned file @%s due to size.",
                    filepath,
                )
            history.add_context_message(context_title, context_message)
            logger.debug("Added context from @%s to temporary history.", filepath)
