# app/application.py
import logging
import sys
import os
from argparse import Namespace

# Assuming components are importable
try:
    from .console_ui import ConsoleUI
    from .command_executor import CommandExecutor
    from .prompt_processor import PromptProcessor
    from .interaction_manager import InteractionManager
except ImportError: # Handle running script directly for testing, etc.
    from console_ui import ConsoleUI
    from command_executor import CommandExecutor
    from prompt_processor import PromptProcessor
    from interaction_manager import InteractionManager

# Assuming History and related types are accessible
from llm.wrapper import History, Role, ContentPartText

logger = logging.getLogger(__name__)

class Application:
    """
    Orchestrates the StreetRace application flow.

    Initializes and coordinates components like UI, command execution,
    prompt processing, and AI interaction. Manages the application lifecycle
    for both interactive and non-interactive modes.
    """
    def __init__(self,
                 args: Namespace,
                 ui: ConsoleUI,
                 cmd_executor: CommandExecutor,
                 prompt_processor: PromptProcessor,
                 interaction_manager: InteractionManager,
                 working_dir: str):
        """
        Initializes the Application.

        Args:
            args: Parsed command-line arguments.
            ui: Initialized ConsoleUI instance.
            cmd_executor: Initialized CommandExecutor instance.
            prompt_processor: Initialized PromptProcessor instance.
            interaction_manager: Initialized InteractionManager instance.
            working_dir: The absolute path to the effective working directory.
        """
        self.args = args
        self.ui = ui
        self.cmd_executor = cmd_executor
        self.prompt_processor = prompt_processor
        self.interaction_manager = interaction_manager
        self.working_dir = working_dir
        logger.info("Application initialized.")

    def run(self):
        """Starts the application execution based on args."""
        if self.args.prompt:
            self._run_non_interactive()
        else:
            self._run_interactive()

    def _run_non_interactive(self):
        """Handles non-interactive mode (single prompt execution)."""
        prompt_input = self.args.prompt
        self.ui.display_user_prompt(prompt_input)

        command_executed, should_continue = self.cmd_executor.execute(prompt_input)

        if command_executed:
            logger.info(f"Non-interactive prompt was command: '{prompt_input}'. Exiting.")
            # Non-interactive commands always exit, regardless of return value
            sys.exit(0)
        else:
            logger.info("Processing non-interactive prompt.")
            # Build context and history for this single prompt
            prompt_context = self.prompt_processor.build_context(prompt_input, self.working_dir)
            single_prompt_history = History(
                system_message=prompt_context.system_message,
                context=prompt_context.project_context
            )

            # Add mentioned files to history (if any)
            self._add_mentions_to_history(prompt_context.mentioned_files, single_prompt_history)

            # Add the user prompt itself
            single_prompt_history.add_message(role=Role.USER, content=[ContentPartText(text=prompt_input)])
            logging.debug(f"User prompt added to single-use history: '{prompt_input}'")

            # Process with InteractionManager
            self.interaction_manager.process_prompt(single_prompt_history)
            logging.info("Non-interactive mode finished.")

    def _run_interactive(self):
        """Handles interactive mode (conversation loop)."""
        self.ui.display_info("Entering interactive mode. Type 'exit', 'quit' or press Ctrl+C/Ctrl+D to quit.")

        # Initialize history for the session
        initial_context = self.prompt_processor.build_context("", self.working_dir)
        conversation_history = History(
            system_message=initial_context.system_message,
            context=initial_context.project_context
        )
        logger.info("Interactive session history initialized.")

        while True:
            try:
                user_input = self.ui.get_user_input()

                command_executed, should_continue = self.cmd_executor.execute(user_input)

                if command_executed:
                    if not should_continue:
                        self.ui.display_info("Exiting.")
                        logging.info("Exit command executed.")
                        break # Exit loop
                    else:
                        continue # Command handled, continue loop

                if not user_input.strip():
                    continue

                # Process the prompt within the interactive session
                # Build context again mainly for mentions specific to this input
                prompt_specific_context = self.prompt_processor.build_context(user_input, self.working_dir)

                # Add mentioned files to history (if any)
                self._add_mentions_to_history(prompt_specific_context.mentioned_files, conversation_history)

                # Add the user prompt itself
                conversation_history.add_message(role=Role.USER, content=[ContentPartText(text=user_input)])
                logging.debug(f"User prompt added to interactive history: '{user_input}'")

                # Process with InteractionManager using the persistent history
                self.interaction_manager.process_prompt(conversation_history)

            except EOFError:
                 self.ui.display_info("\nExiting.")
                 logging.info("Exiting due to EOF.")
                 break
            except KeyboardInterrupt:
                 self.ui.display_info("\nExiting.")
                 logging.info("Exiting due to KeyboardInterrupt.")
                 break
            except Exception as loop_err:
                # Use UI to display unexpected errors
                self.ui.display_error(f"\nAn unexpected error occurred in the interactive loop: {loop_err}")
                logging.exception("Unexpected error in interactive loop.", exc_info=loop_err)
                # Decide whether to continue or break here. Let's continue for now.

    def _add_mentions_to_history(self, mentioned_files: list, history: History):
        """Helper method to add content from mentioned files to history."""
        if not mentioned_files:
            return

        # UI indication is handled within prompt_processor now
        for filepath, content in mentioned_files:
            context_message = f"Content of mentioned file '@{filepath}':\n---\n{content}\n---"
            MAX_MENTION_CONTENT_LENGTH = 10000 # Consider making this configurable
            if len(content) > MAX_MENTION_CONTENT_LENGTH:
                context_message = f"Content of mentioned file '@{filepath}' (truncated):\n---\n{content[:MAX_MENTION_CONTENT_LENGTH]}\n...\n---"
                logging.warning(f"Truncated content for mentioned file @{filepath} due to size.")
            history.add_message(role=Role.USER, content=[ContentPartText(text=context_message)])
            logging.debug(f"Added context from @{filepath} to history.")
