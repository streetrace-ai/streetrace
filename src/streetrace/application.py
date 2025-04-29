# app/application.py
import json  # Added for pretty printing
import logging
import sys
from argparse import Namespace

from streetrace.commands.command_executor import CommandExecutor
from streetrace.interaction_manager import InteractionManager
from streetrace.llm.wrapper import (
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Role,
)
from streetrace.prompt_processor import PromptContext, PromptProcessor
from streetrace.ui.console_ui import ConsoleUI

logger = logging.getLogger(__name__)


class Application:
    """Orchestrates the StreetRace application flow.

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
    ) -> None:
        """Initialize the Application with necessary components and configuration.

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
        self.conversation_history: History | None = None  # Current history
        logger.info("Application initialized.")

    def run(self) -> None:
        """Start the application execution based on provided arguments.

        Determines whether to run in interactive or non-interactive mode based on
        whether a prompt was provided via command-line arguments.
        """
        if self.args.prompt:
            self._run_non_interactive()
        else:
            self._run_interactive()

    def _run_non_interactive(self) -> None:
        """Handle non-interactive mode (single prompt execution).

        Processes a single prompt provided via command-line arguments and exits.
        First checks if the prompt is an internal command, and if not, processes
        it through the AI model and displays the response.
        """
        prompt_input = self.args.prompt
        self.ui.display_user_prompt(prompt_input)

        # Check for internal commands first (e.g., if someone runs with --prompt history)
        command_executed, _ = self.cmd_executor.execute(prompt_input, self)  # Pass self

        if command_executed:
            logger.info(
                "Non-interactive prompt was command: '%s'. Exiting.",
                prompt_input,
            )
            # Non-interactive commands always exit, regardless of return value
            sys.exit(0)
        else:
            logger.info("Processing non-interactive prompt.")
            # Build context and history for this single prompt
            prompt_context = self.prompt_processor.build_context(
                prompt_input,
                self.working_dir,
            )
            single_prompt_history = History(
                system_message=prompt_context.system_message,
                context=prompt_context.project_context,
            )

            # Add mentioned files to history (if any)
            self._add_mentions_to_history(
                prompt_context.mentioned_files,
                single_prompt_history,
            )

            # Add the user prompt itself
            single_prompt_history.add_message(
                role=Role.USER,
                content=[ContentPartText(text=prompt_input)],
            )
            logger.debug(
                "User prompt added to single-use history",
                extra={"prompt_input": prompt_input},
            )

            # Process with InteractionManager
            self.interaction_manager.process_prompt(single_prompt_history)
            logger.info("Non-interactive mode finished.")

    def _run_interactive(self) -> None:
        """Handle interactive mode (conversation loop).

        Initializes and maintains an ongoing conversation with the AI assistant.
        Continuously prompts for user input, processes commands or sends prompts
        to the AI model, and displays responses until the user chooses to exit.

        Handles keyboard interrupts and EOF signals gracefully for smooth termination.
        """
        self.ui.display_info(
            "Entering interactive mode. Type '/history', '/compact', '/clear', '/exit', or press Ctrl+C/Ctrl+D to quit.",
        )

        # Get initial context directly using build_context
        initial_prompt_context: PromptContext = self.prompt_processor.build_context(
            "",
            self.working_dir,
        )

        # Initialize history for the session using the initial context
        self.conversation_history = History(
            system_message=initial_prompt_context.system_message,
            context=initial_prompt_context.project_context,
        )
        logger.info("Interactive session history initialized.")

        while True:
            try:
                user_input = self.ui.prompt()
                if user_input == "/__reprompt":
                    continue

                command_executed, should_continue = self.cmd_executor.execute(
                    user_input,
                    self,
                )  # Pass self

                if command_executed:
                    if should_continue:
                        # Command handled (like history, compact, clear), continue loop for next input
                        continue
                    self.ui.display_info("Leaving...")
                    break  # Exit loop

                # Ensure history exists before proceeding (should always exist in interactive)
                if not self.conversation_history:
                    logger.error(
                        "Conversation history is missing in interactive mode. Attempting to reset.",
                    )
                    # Try to reset using _clear_history (which now uses build_context)
                    if self._clear_history():  # Reset the history
                        self.ui.display_warning("History has been reset.")
                    else:
                        # If reset fails (e.g., build_context fails), we might need to exit
                        # Note: _clear_history currently always returns True, but keeping check for robustness
                        self.ui.display_error(
                            "Critical error: History missing and could not be reset.",
                        )
                        break
                    continue  # Continue to next prompt after reset

                if user_input.strip():
                    # Process the prompt within the interactive session
                    # Build context again mainly for mentions specific to this input
                    prompt_specific_context = self.prompt_processor.build_context(
                        user_input,
                        self.working_dir,
                    )

                    # Add mentioned files to history (if any)
                    self._add_mentions_to_history(
                        prompt_specific_context.mentioned_files,
                        self.conversation_history,
                    )

                    # Add the user prompt itself
                    self.conversation_history.add_message(
                        role=Role.USER,
                        content=[ContentPartText(text=user_input)],
                    )
                    logger.debug(
                        "User prompt added to interactive history",
                        extra={"user_input": user_input},
                    )

                # Process with InteractionManager using the persistent history
                self.interaction_manager.process_prompt(self.conversation_history)

            except EOFError:
                self.ui.display_info("\nExiting.")
                logger.info("Exiting due to EOF.")
                break
            except KeyboardInterrupt:
                self.ui.display_info("\nExiting.")
                logger.info("Exiting due to KeyboardInterrupt.")
                break
            except Exception as loop_err:
                # Use UI to display unexpected errors
                self.ui.display_error(
                    f"\nAn unexpected error occurred in the interactive loop: {loop_err}",
                )
                logger.exception(
                    "Unexpected error in interactive loop.",
                    exc_info=loop_err,
                )
                # Continue the loop to maintain interactive session after error

    def _add_mentions_to_history(self, mentioned_files: list, history: History) -> None:
        """Add content from mentioned files to conversation history.

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
            max_mention_content_length = (
                20000  # Maximum length for file content to prevent excessive tokens
            )
            if len(content) > max_mention_content_length:
                context_message = f"Content of mentioned file '@{filepath}' (truncated):\n---\n{content[:max_mention_content_length]}\n...\n---"
                logger.warning(
                    "Truncated content for mentioned file @%s due to size.",
                    filepath,
                )
            # Add mention context as USER role for simplicity in display/processing for now
            history.add_message(
                role=Role.CONTEXT,
                content=[ContentPartText(text=context_message)],
            )
            logger.debug("Added context from @%s to history.", filepath)

    def _display_history(self) -> bool:
        """Display the current conversation history using the UI.

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
                            if part.content.failure:
                                if "return_code" in part.content.output.content:
                                    content_str += f"Tool Result: (Error)\n\n**RETURN CODE**: {part.content.output.content.get('return_code')}\n\n**STDOUT**:\n\n{part.content.output.content.get('stdout')}\n\n**STDERR**:\n\n{part.content.output.content.get('stderr')}\n"
                                else:
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
                elif msg.role in (Role.USER, Role.TOOL):
                    # Display user messages or tool messages
                    self.ui.display_history_user_message(content_str)
                else:  # Fallback for other potential roles
                    self.ui.display_info(f"{role_str}: {content_str.strip()}")

        self.ui.display_info("--- End History ---")
        return True  # Signal to continue the application loop

    def _compact_history(self) -> bool:
        """Compacts the current conversation history by generating a summary.

        This method:
        1. Checks if there's a conversation history to compact
        2. Prepares a prompt that instructs the LLM to create a summary
        3. Uses the interaction manager to generate a summarized version
        4. Replaces the current history with the summarized version

        Returns:
            True, indicating the application should continue running after
            compacting history.

        """
        if not self.conversation_history or not self.conversation_history.conversation:
            self.ui.display_warning("No history available to compact.")
            return True  # Nothing to compact, but continue running

        self.ui.display_info("Compacting conversation history...")

        # Create a copy of the system message and context from the current history
        system_message = self.conversation_history.system_message
        context = self.conversation_history.context

        # Create a new temporary history for the summarization request
        summary_request_history = History(
            system_message=system_message,
            context=context,
            conversation=self.conversation_history.conversation[:],
        )

        # Add a message requesting summarization
        summary_prompt = """Please summarize our conversation so far, maintaining the key points and decisions.
Your summary should:
1. Preserve all important information, file paths, and code changes
2. Include any important decisions or conclusions we've reached
3. Keep any critical context needed for continuing the conversation
4. Format the summary as a concise narrative

Return ONLY the summary without explaining what you're doing."""

        summary_request_history.add_message(
            role=Role.USER,
            content=[ContentPartText(text=summary_prompt)],
        )

        # Process with the interaction manager to get the summary
        logger.info("Requesting conversation summary from LLM")

        # We use the existing interaction manager to process this request
        self.interaction_manager.process_prompt(summary_request_history)

        # Get the summary message from the response
        if (
            len(summary_request_history.conversation) >= 2
            and summary_request_history.conversation[-1].role == Role.MODEL
        ):
            # Create a new history with just the summary
            new_history = History(system_message=system_message, context=context)

            # Add the summary message to the new history
            new_history.add_message(
                role=Role.MODEL,
                content=summary_request_history.conversation[-1].content,
            )

            # Replace the current history with the summary
            self.conversation_history = new_history

            self.ui.display_info("History compacted successfully.")
        else:
            self.ui.display_error(
                "Failed to generate summary. History remains unchanged.",
            )

        return True  # Signal to continue the application loop

    def _clear_history(self) -> bool:
        """Clear the current conversation history, resetting it to the initial state.

        This method rebuilds the initial context using the prompt processor and
        replaces the current `conversation_history` with a new History object
        containing only the initial system message and project context.

        Returns:
            True, indicating the application should continue running after
            clearing history.

        """
        logger.info(
            "Attempting to clear conversation history by rebuilding initial context.",
        )

        try:
            # Rebuild the initial context
            initial_prompt_context: PromptContext = self.prompt_processor.build_context(
                "",
                self.working_dir,
            )

            # Create a new History object with the fresh initial state
            self.conversation_history = History(
                system_message=initial_prompt_context.system_message,
                context=initial_prompt_context.project_context,
            )

            logger.info("Conversation history cleared successfully.")
            self.ui.display_info("Conversation history has been cleared.")

        except Exception as e:
            logger.exception("Failed to rebuild context while clearing history")
            self.ui.display_error(
                f"Could not clear history due to an error rebuilding context: {e}",
            )
            # Even if clearing fails, we should probably continue the loop

        return True  # Signal to continue the application loop
