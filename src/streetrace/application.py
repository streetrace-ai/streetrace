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
from streetrace.interaction_manager import InteractionManager
from streetrace.prompt_processor import PromptProcessor
from streetrace.system_context import SystemContext
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
        system_context: SystemContext,
        interaction_manager: InteractionManager,
        history_manager: "HistoryManager",
    ) -> None:
        """Initialize the Application with necessary components and configuration.

        Args:
            app_config: App configuration parameters.
            ui: ConsoleUI instance for handling user interaction and displaying output.
            cmd_executor: CommandExecutor instance for processing internal commands.
            prompt_processor: PromptProcessor instance for processing prompts and file mentions.
            system_context: SystemContext instance for loading system and project context.
            interaction_manager: InteractionManager instance for handling AI model interactions.
            history_manager: HistoryManager instance for managing conversation history.

        """
        self.config = app_config
        self.ui = ui
        self.cmd_executor = cmd_executor
        self.prompt_processor = prompt_processor
        self.system_context = system_context
        self.interaction_manager = interaction_manager
        self.history_manager = history_manager
        logger.info("Application initialized.")

    def run(self) -> None:
        """Start the application execution based on provided arguments."""
        self.history_manager.initialize_history()
        if self.config.non_interactive_prompt:
            self._run_non_interactive()
        else:
            self._run_interactive()

    def _run_non_interactive(self) -> None:
        """Handle non-interactive mode (single prompt execution)."""
        user_input = self.config.non_interactive_prompt
        # According to coding guide, core components should be fail-fast.
        # Raise if non_interactive_prompt is unexpectedly None.
        if user_input is None:
            error_msg = "Non-interactive mode requires a prompt, but none was provided."
            logger.error(error_msg)
            # Use ValueError for invalid configuration/state
            raise ValueError(error_msg)

        self.ui.display_user_prompt(user_input)

        command_executed, _ = self.cmd_executor.execute(user_input, self)

        if command_executed:
            logger.info(
                "Non-interactive prompt was command: '%s'. Exiting.",
                user_input,
            )
            sys.exit(0)
        else:
            logger.info("Processing non-interactive prompt.")

            # Process the prompt for file mentions
            prompt_context = self.prompt_processor.build_context(
                user_input,
                self.config.working_dir,
            )
            # Add mentioned files and the user prompt via HistoryManager
            self.history_manager.add_mentions_to_history(
                prompt_context.mentioned_files,
            )
            self.history_manager.add_user_message(user_input)
            logger.debug(
                "User prompt added to history",
                extra={"user_input": user_input},
            )
            self.interaction_manager.process_prompt(
                self.config.initial_model,
                self.history_manager.get_history(),
                self.config.tools,
            )
            logger.info("Non-interactive mode finished.")

    def _run_interactive(self) -> None:
        """Handle interactive mode (conversation loop)."""
        self.ui.display_info(
            "Entering interactive mode. Type '/history', '/compact', '/clear', '/exit', or press Ctrl+C/Ctrl+D to quit.",
        )

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
                        "User prompt added to history",
                        extra={"user_input": user_input},
                    )

                # Process with InteractionManager using the persistent history
                self.interaction_manager.process_prompt(
                    self.config.initial_model,
                    self.history_manager.get_history(),
                    self.config.tools,
                )

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
