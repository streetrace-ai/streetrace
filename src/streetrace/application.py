# app/application.py
import json  # Added for pretty printing
import logging
import sys
from argparse import Namespace

from streetrace.commands.command_executor import CommandExecutor
from streetrace.llm.wrapper import (
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Role,
)
from streetrace.prompt_processor import PromptProcessor
from streetrace.ui.console_ui import ConsoleUI
from streetrace.ui.interaction_manager import InteractionManager

logger = logging.getLogger(__name__)


class Application:
    """
    Orchestrates the StreetRace application flow.

    Initializes and coordinates components like UI, command execution,
    prompt processing, and AI interaction. Manages the application lifecycle
    for both interactive and non-interactive modes.
    """

    def __init__(
        self,
        args: Namespace,
        ui: ConsoleUI,
        cmd_executor: CommandExecutor,
        prompt_processor: PromptProcessor,
        interaction_manager: InteractionManager,
        working_dir: str,
    ):
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
        self.conversation_history: History | None = None  # Initialize history attribute
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

        # Check for internal commands first (e.g., if someone runs with --prompt history)
        command_executed, should_continue = self.cmd_executor.execute(
            prompt_input, self
        )  # Pass self

        if command_executed:
            logger.info(
                f"Non-interactive prompt was command: '{prompt_input}'. Exiting."
            )
            # Non-interactive commands always exit, regardless of return value
            sys.exit(0)
        else:
            logger.info("Processing non-interactive prompt.")
            # Build context and history for this single prompt
            prompt_context = self.prompt_processor.build_context(
                prompt_input, self.working_dir
            )
            single_prompt_history = History(
                system_message=prompt_context.system_message,
                context=prompt_context.project_context,
            )

            # Add mentioned files to history (if any)
            self._add_mentions_to_history(
                prompt_context.mentioned_files, single_prompt_history
            )

            # Add the user prompt itself
            single_prompt_history.add_message(
                role=Role.USER, content=[ContentPartText(text=prompt_input)]
            )
            logging.debug(f"User prompt added to single-use history: '{prompt_input}'")

            # Process with InteractionManager
            self.interaction_manager.process_prompt(single_prompt_history)
            logging.info("Non-interactive mode finished.")

    def _run_interactive(self):
        """Handles interactive mode (conversation loop)."""
        self.ui.display_info(
            "Entering interactive mode. Type 'history', 'exit', 'quit' or press Ctrl+C/Ctrl+D to quit."
        )

        # Initialize history for the session and store it as an instance variable
        initial_context = self.prompt_processor.build_context("", self.working_dir)
        self.conversation_history = History(
            system_message=initial_context.system_message,
            context=initial_context.project_context,
        )
        logger.info("Interactive session history initialized.")

        while True:
            try:
                user_input = self.ui.get_user_input()

                command_executed, should_continue = self.cmd_executor.execute(
                    user_input, self
                )  # Pass self

                if command_executed:
                    if not should_continue:
                        self.ui.display_info("Exiting.")
                        logging.info("Exit command executed.")
                        break  # Exit loop
                    else:
                        # Command handled (like history), continue loop for next input
                        continue

                # Ensure history exists before proceeding (should always exist in interactive)
                if not self.conversation_history:
                    logger.error(
                        "Conversation history is missing in interactive mode. Re-initializing."
                    )
                    # Re-initialize using the initial context captured at the start
                    self.conversation_history = History(
                        system_message=initial_context.system_message,
                        context=initial_context.project_context,
                    )


                if user_input.strip():
                    # Process the prompt within the interactive session
                    # Build context again mainly for mentions specific to this input
                    prompt_specific_context = self.prompt_processor.build_context(
                        user_input, self.working_dir
                    )

                    # Add mentioned files to history (if any)
                    self._add_mentions_to_history(
                        prompt_specific_context.mentioned_files, self.conversation_history
                    )

                    # Add the user prompt itself
                    self.conversation_history.add_message(
                        role=Role.USER, content=[ContentPartText(text=user_input)]
                    )
                    logging.debug(
                        f"User prompt added to interactive history: '{user_input}'"
                    )

                # Process with InteractionManager using the persistent history
                self.interaction_manager.process_prompt(self.conversation_history)

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
                self.ui.display_error(
                    f"\nAn unexpected error occurred in the interactive loop: {loop_err}"
                )
                logging.exception(
                    "Unexpected error in interactive loop.", exc_info=loop_err
                )
                # Decide whether to continue or break here. Let's continue for now.

    def _add_mentions_to_history(self, mentioned_files: list, history: History):
        """Helper method to add content from mentioned files to history."""
        if not mentioned_files:
            return

        # UI indication is handled within prompt_processor now
        for filepath, content in mentioned_files:
            context_message = (
                f"Content of mentioned file '@{filepath}':\n---\n{content}\n---"
            )
            MAX_MENTION_CONTENT_LENGTH = 10000  # Consider making this configurable
            if len(content) > MAX_MENTION_CONTENT_LENGTH:
                context_message = f"Content of mentioned file '@{filepath}' (truncated):\n---\n{content[:MAX_MENTION_CONTENT_LENGTH]}\n...\n---"
                logging.warning(
                    f"Truncated content for mentioned file @{filepath} due to size."
                )
            # Add mention context as USER role for simplicity in display/processing for now
            history.add_message(
                role=Role.USER, content=[ContentPartText(text=context_message)]
            )
            logging.debug(f"Added context from @{filepath} to history.")

    def _display_history(self) -> bool:
        """
        Displays the current conversation history using the UI.

        Returns:
            True, indicating the application should continue.
        """
        if not self.conversation_history:
            self.ui.display_warning("No history available yet.")
            return True  # Nothing to display, but continue running

        self.ui.display_info("\n--- Conversation History ---")

        # Display system message if present
        if self.conversation_history.system_message:
            self.ui.display_system_message(self.conversation_history.system_message)

        # Display context if present
        if self.conversation_history.context:
            # Context might be large, maybe summarize or just indicate presence?
            # For now, let's display the first N chars or a summary
            context_str = str(self.conversation_history.context)
            max_len = 200
            display_context = (
                context_str[:max_len] + "..."
                if len(context_str) > max_len
                else context_str
            )
            self.ui.display_context_message(display_context)

        if not self.conversation_history.conversation:
            self.ui.display_info("No messages in history yet.")
        else:
            for msg in self.conversation_history.conversation:
                role_str = msg.role.name.capitalize()
                content_str = ""
                if not msg.content:  # Handle potential empty content list
                    content_str = "[Empty Message Content]"
                else:
                    for part in msg.content:
                        if isinstance(part, ContentPartText):
                            content_str += part.text + "\n"
                        elif isinstance(part, ContentPartToolCall):
                            # Ensure arguments are formatted as a string (e.g., JSON)
                            args_str = (
                                json.dumps(part.arguments)
                                if isinstance(part.arguments, dict)
                                else str(part.arguments)
                            )
                            content_str += f"Tool Call: {part.name}({args_str})\n"
                        elif isinstance(part, ContentPartToolResult):
                            if "error" in part.content:
                                content_str += (
                                    f"Tool Result: (Error) {part.content['message']}\n"
                                )
                            else:
                                content_str += "Tool Result: (OK)\n"
                        elif part is None:  # Handle potential None parts
                            content_str += "[None Content Part]\n"
                        else:
                            content_str += str(part) + "\n"  # Fallback
                content_str = content_str.strip()  # Clean up trailing whitespace

                # Use appropriate UI methods based on role
                if msg.role == Role.MODEL:
                    # Check if it's a tool call or regular response
                    self.ui.display_history_assistant_message(content_str)
                elif msg.role == Role.USER or msg.role == Role.TOOL:
                    self.ui.display_history_user_message(content_str)
                else:  # Fallback for other potential roles
                    self.ui.display_info(f"{role_str}: {content_str.strip()}")

        self.ui.display_info("--- End History ---")
        return True  # Signal to continue the application loop
