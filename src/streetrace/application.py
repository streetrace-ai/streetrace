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

    This class serves as the central coordinator for the application, managing the
    interaction between components and handling the application lifecycle. It supports
    both interactive chat mode and non-interactive single prompt execution.

    The Application class initializes and coordinates key components including:
    - User interface handling (ConsoleUI)
    - Command execution (CommandExecutor)
    - Prompt processing and context building (PromptProcessor)
    - AI model interaction (InteractionManager)
    - Conversation history management
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
        Initializes the Application with necessary components and configuration.

        Args:
            args: Parsed command-line arguments that control application behavior.
            ui: ConsoleUI instance for handling user interaction and displaying output.
            cmd_executor: CommandExecutor instance for processing internal commands.
            prompt_processor: PromptProcessor instance for building context and processing prompts.
            interaction_manager: InteractionManager instance for handling AI model interactions.
            working_dir: The absolute path to the effective working directory for file operations.
        """
        self.args = args
        self.ui = ui
        self.cmd_executor = cmd_executor
        self.prompt_processor = prompt_processor
        self.interaction_manager = interaction_manager
        self.working_dir = working_dir
        self.conversation_history: History | None = (
            None  # Stores ongoing conversation in interactive mode
        )
        logger.info("Application initialized.")

    def run(self):
        """
        Starts the application execution based on provided arguments.

        Determines whether to run in interactive or non-interactive mode based on
        whether a prompt was provided via command-line arguments.
        """
        if self.args.prompt:
            self._run_non_interactive()
        else:
            self._run_interactive()

    def _run_non_interactive(self):
        """
        Handles non-interactive mode (single prompt execution).

        Processes a single prompt provided via command-line arguments and exits.
        First checks if the prompt is an internal command, and if not, processes
        it through the AI model and displays the response.
        """
        prompt_input = self.args.prompt
        self.ui.display_user_prompt(prompt_input)

        # Check for internal commands first (e.g., if someone runs with --prompt history)
        command_executed, _ = self.cmd_executor.execute(
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
        """
        Handles interactive mode (conversation loop).

        Initializes and maintains an ongoing conversation with the AI assistant.
        Continuously prompts for user input, processes commands or sends prompts
        to the AI model, and displays responses until the user chooses to exit.

        Handles keyboard interrupts and EOF signals gracefully for smooth termination.
        """
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
                user_input = self.ui.prompt()

                command_executed, should_continue = self.cmd_executor.execute(
                    user_input, self
                )  # Pass self

                if command_executed:
                    if should_continue:
                        # Command handled (like history), continue loop for next input
                        continue
                    else:
                        self.ui.display_info("Leaving...")
                        break  # Exit loop

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
                        prompt_specific_context.mentioned_files,
                        self.conversation_history,
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
                # Continue the loop to maintain interactive session after error

    def _add_mentions_to_history(self, mentioned_files: list, history: History):
        """
        Adds content from mentioned files to conversation history.

        When the user references files with @ mentions in their prompt,
        this method adds the content of those files to the conversation
        history to provide context to the AI model.

        Args:
            mentioned_files: List of tuples containing (filepath, content) for each mentioned file.
            history: The History object to which file contents should be added.
        """
        if not mentioned_files:
            return

        # UI indication is handled within prompt_processor now
        for filepath, content in mentioned_files:
            context_message = (
                f"Content of mentioned file '@{filepath}':\n---\n{content}\n---"
            )
            MAX_MENTION_CONTENT_LENGTH = (
                20000  # Maximum length for file content to prevent excessive tokens
            )
            if len(content) > MAX_MENTION_CONTENT_LENGTH:
                context_message = f"Content of mentioned file '@{filepath}' (truncated):\n---\n{content[:MAX_MENTION_CONTENT_LENGTH]}\n...\n---"
                logging.warning(
                    f"Truncated content for mentioned file @{filepath} due to size."
                )
            # Add mention context as USER role for simplicity in display/processing for now
            history.add_message(
                role=Role.CONTEXT, content=[ContentPartText(text=context_message)]
            )
            logging.debug(f"Added context from @{filepath} to history.")

    def _display_history(self) -> bool:
        """
        Displays the current conversation history using the UI.

        This method is called when the user requests to see the conversation
        history via the 'history' command. It formats and displays different
        types of message content including text, tool calls, and tool results.

        Returns:
            True, indicating the application should continue running after
            displaying history.
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
            # Show a preview of context due to potential large size
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
                            if part.content.error:
                                content_str += f"Tool Result: (Error) {part.content.output.content}\n"
                            else:
                                content_str += "Tool Result: (OK)\n"
                        elif part is None:  # Handle potential None parts
                            content_str += "[None Content Part]\n"
                        else:
                            content_str += str(part) + "\n"  # Fallback
                content_str = content_str.strip()  # Clean up trailing whitespace

                # Use appropriate UI methods based on role
                if msg.role == Role.MODEL:
                    # Display assistant/model messages
                    self.ui.display_history_assistant_message(content_str)
                elif msg.role == Role.USER or msg.role == Role.TOOL:
                    # Display user messages or tool messages
                    self.ui.display_history_user_message(content_str)
                else:  # Fallback for other potential roles
                    self.ui.display_info(f"{role_str}: {content_str.strip()}")

        self.ui.display_info("--- End History ---")
        return True  # Signal to continue the application loop
