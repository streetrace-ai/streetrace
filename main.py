# Corrected code for main.py

import json
import logging
import os
import argparse
import re # Make sure re is imported
import sys

from llm.wrapper import ContentPartText, History, Role
from tools.fs_tool import TOOLS, TOOL_IMPL
from messages import SYSTEM
# Removed direct import of AnsiColors as it's handled by ConsoleUI
# from colors import AnsiColors
from llm.llmapi_factory import get_ai_provider
from llm.generate import generate_with_tools
from app.command_executor import CommandExecutor
# --- New Import ---
from app.console_ui import ConsoleUI

# Configure logging (remains the same)
# ... (logging configuration code - unchanged) ...
# File handler (INFO level by default)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='generation.log',
                    filemode='a') # Append mode

# Console handler (INFO level by default, format without timestamp for cleaner console)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)

# Get the root logger and add the console handler
root_logger = logging.getLogger()
root_logger.addHandler(console_handler)
# Set root logger level to DEBUG initially to capture everything,
# handlers control what gets output where.
root_logger.setLevel(logging.DEBUG)


# --- Logging Setup Complete ---

# --- Modified Functions to Accept UI ---

def read_system_message(ui: ConsoleUI): # Added ui parameter
    """
    Read the system message from a file or return the default message.

    Args:
        ui: The ConsoleUI instance for displaying errors.

    Returns:
        str: The system message content
    """
    system_message_path = '.streetrace/system.md'
    if os.path.exists(system_message_path):
        try:
            with open(system_message_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logging.error(f"Error reading system message file '{system_message_path}': {e}")
            # Use ui.display_error instead of print
            ui.display_error(f"Error reading system message file: {e}")

    # Default system message
    return SYSTEM


def read_project_context(ui: ConsoleUI): # Added ui parameter
    """
    Read all project context files from .streetrace directory excluding system.md.

    Args:
        ui: The ConsoleUI instance for displaying errors.

    Returns:
        str: Combined content of all context files, or empty string if none exist
    """
    context_files_dir = '.streetrace'
    combined_context = ""

    if not os.path.exists(context_files_dir) or not os.path.isdir(context_files_dir):
        logging.info(f"Context directory '{context_files_dir}' not found.")
        return combined_context

    try:
        context_files = [
            f for f in os.listdir(context_files_dir)
            if os.path.isfile(os.path.join(context_files_dir, f)) and f != 'system.md'
        ]
    except Exception as e:
        logging.error(f"Error listing context directory '{context_files_dir}': {e}")
        # Use ui.display_error instead of print
        ui.display_error(f"Error listing context directory '{context_files_dir}': {e}")
        return combined_context

    if not context_files:
        logging.info(f"No context files found in '{context_files_dir}'.")
        return combined_context

    context_content_parts = []
    logging.info(f"Reading context files: {', '.join(context_files)}")
    for file_name in context_files:
        file_path = os.path.join(context_files_dir, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                context_content_parts.append(f"\n\n--- Context from: {file_name} ---\n\n{content}\n\n--- End Context: {file_name} ---\n")
        except Exception as e:
            logging.error(f"Error reading context file {file_path}: {e}")
            # Use ui.display_error instead of print
            ui.display_error(f"Error reading context file {file_path}: {e}")

    combined_context = "".join(context_content_parts)
    logging.info(f"Successfully loaded context from {len(context_content_parts)} file(s).")
    return combined_context


def parse_and_load_mentions(prompt: str, working_dir: str, ui: ConsoleUI) -> list[tuple[str, str]]: # Added ui parameter
    """
    Parses a prompt for @<filepath> mentions, loads valid files, and displays info/errors via UI.

    Args:
        prompt: The user input string.
        working_dir: The current working directory for resolving relative paths.
        ui: The ConsoleUI instance for displaying messages.

    Returns:
        A list of tuples, where each tuple contains the cleaned mentioned filepath
        (relative to working_dir) and its content.
    """
    mention_pattern = r"@([^\s@]+)"
    raw_mentions = re.findall(mention_pattern, prompt)

    processed_mentions = set()
    trailing_punctuation = '.,!?;:)]}"\''

    for raw_mention in raw_mentions:
        cleaned_mention = raw_mention
        while len(cleaned_mention) > 1 and cleaned_mention[-1] in trailing_punctuation:
            cleaned_mention = cleaned_mention[:-1]
        processed_mentions.add(cleaned_mention)

    mentions = sorted(list(processed_mentions))
    loaded_files = []

    if not mentions:
        return loaded_files

    # Use ui.display_info instead of print
    ui.display_info(f"[Detected mentions: {', '.join(['@'+m for m in mentions])}]")
    logging.info(f"Detected mentions after cleaning: {', '.join(mentions)}")

    absolute_working_dir = os.path.realpath(working_dir)

    for mention in mentions:
        potential_rel_path = mention
        try:
            normalized_path = os.path.normpath(os.path.join(working_dir, mention))
            absolute_mention_path = os.path.realpath(normalized_path)

            common_path = os.path.commonpath([absolute_working_dir, absolute_mention_path])

            if common_path != absolute_working_dir:
                 # Use ui.display_warning instead of print
                 ui.display_warning(f"Mention '@{mention}' points outside the working directory '{working_dir}'. Skipping.")
                 logging.warning(f"Security Warning: Mention '@{mention}' resolved to '{absolute_mention_path}' which is outside the working directory '{absolute_working_dir}'. Skipping.")
                 continue

            if os.path.isfile(absolute_mention_path):
                try:
                    with open(absolute_mention_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    loaded_files.append((potential_rel_path, content))
                    # Use ui.display_info instead of print
                    ui.display_info(f"[Loaded context from @{mention}]")
                    logging.info(f"Loaded context from mentioned file: {absolute_mention_path} (Mention: @{mention})")
                except Exception as e:
                    # Use ui.display_error instead of print
                    ui.display_error(f"[Error reading @{mention}: {e}]")
                    logging.error(f"Error reading mentioned file '{absolute_mention_path}' (Mention: @{mention}): {e}")
            else:
                # Use ui.display_error instead of print
                ui.display_error(f"[Mentioned path @{mention} ('{absolute_mention_path}') not found or is not a file. Skipping.]")
                logging.warning(f"Mentioned path '@{mention}' resolved to '{absolute_mention_path}' which was not found or is not a file.")
        except Exception as e:
            # Use ui.display_error instead of print
            ui.display_error(f"[Error processing mention @{mention}: {e}]")
            logging.error(f"Error processing mention '@{mention}': {e}")

    return loaded_files


def parse_arguments():
    """ Parses command line arguments. (Unchanged) """
    # ... (argument parsing code - unchanged) ...
    parser = argparse.ArgumentParser(
        description='Run AI assistant with different models')
    parser.add_argument('--engine',
                        type=str,
                        choices=['claude', 'gemini', 'ollama', 'openai'],
                        help='Choose AI engine (claude, gemini, ollama, or openai)')
    parser.add_argument(
        '--model',
        type=str,
        help=
        'Specific model name to use (e.g., claude-3-opus-20240229, gemini-1.5-flash, llama3:8b, or gpt-4o)'
    )
    parser.add_argument(
        '--prompt',
        type=str,
        help=
        'Prompt to send to the AI model (skips interactive mode if provided)')
    parser.add_argument(
        '--path',
        type=str,
        default=None,
        help=
        'Specify which path to use as the working directory for all file operations'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging to console and file.'
    )
    return parser.parse_args()

def call_tool(tool_name, args, original_call, work_dir, ui: ConsoleUI): # Added ui parameter
    """
    Call the appropriate tool function based on the tool name, using UI for output.

    Args:
        tool_name: Name of the tool to call
        args: Dictionary of arguments to pass to the function
        original_call: The original function call object from the model (if available)
        work_dir: Path to use as the working directory for file operations
        ui: The ConsoleUI instance for displaying messages.

    Returns:
        dict: A dictionary representing the tool result (success or error)
    """
    args_display = json.dumps(args)
    if len(args_display) > 100:
        args_display = args_display[:97] + "..."
    # Use ui.display_tool_call instead of print
    ui.display_tool_call(tool_name, args_display)
    logging.info(f"Tool call: {tool_name} with args: {args}")

    if tool_name in TOOL_IMPL:
        tool_func = TOOL_IMPL[tool_name]
        tool_result = None
        try:
            import inspect
            sig = inspect.signature(tool_func)
            tool_params = sig.parameters

            if 'work_dir' in tool_params:
                args_with_workdir = { **args, 'work_dir': work_dir }
                tool_result = tool_func(**args_with_workdir)
            else:
                tool_result = tool_func(**args)

            if not isinstance(tool_result, dict):
                 result_data = {"result": tool_result}
            else:
                 result_data = tool_result

            display_result = str(result_data)
            # Display using ui (truncation now handled within ui method)
            ui.display_tool_result(display_result)
            logging.info(f"Tool '{tool_name}' result: {result_data}")

            final_result_payload = {}
            try:
                 json.dumps(result_data) # Test serializability
                 final_result_payload = {"success": True, "result": result_data}
            except TypeError as json_err:
                 logging.warning(f"Tool '{tool_name}' result is not fully JSON serializable: {json_err}. Returning string representation within result.")
                 # Fallback: put string representation inside the result field
                 final_result_payload = {"success": True, "result": str(result_data)}

            return final_result_payload # Tool executed successfully

        except Exception as e:
            error_msg = f"Error executing tool '{tool_name}': {str(e)}"
            # Use ui.display_error instead of print
            ui.display_error(error_msg)
            # Log full exception with stack trace
            logging.exception(f"Error during tool call: {tool_name} with args {args}", exc_info=e)
            # Return a structured error message
            return {"error": True, "message": error_msg}
    else:
        error_msg = f"Tool not found: {tool_name}"
        # Use ui.display_error instead of print
        ui.display_error(error_msg)
        logging.error(error_msg)
        # Return a structured error message
        return {"error": True, "message": error_msg}

# --- End Modified Functions ---


def main():
    """Main entry point for the application"""
    args = parse_arguments()

    # --- Initialize UI early ---
    ui = ConsoleUI(debug_enabled=args.debug)

    # --- Configure Logging Level based on --debug ---
    if args.debug:
        # Set console handler to DEBUG, file handler remains INFO (or DEBUG if needed)
        console_handler.setLevel(logging.DEBUG)
        # Optionally set file handler level too:
        # logging.getLogger().handlers[0].setLevel(logging.DEBUG) # Assuming file handler is the first one
        root_logger.setLevel(logging.DEBUG) # Ensure root logger captures DEBUG
        logging.debug("Debug logging enabled.")
        # Optional: Display debug status via UI if desired
        # ui.display_debug("Debug mode enabled.")
    else:
        # Set console handler to INFO, file handler remains INFO
        console_handler.setLevel(logging.INFO)
        root_logger.setLevel(logging.INFO) # Ensure root logger captures INFO
    # --- End Logging Level Config ---

    # --- Initialize Command Executor ---
    cmd_executor = CommandExecutor()
    # Register built-in commands
    cmd_executor.register("exit", lambda: False) # Return False to signal exit
    cmd_executor.register("quit", lambda: False) # Alias for exit

    # Add help command registration using UI (example, needs implementation in ConsoleUI)
    # cmd_executor.register("help", lambda: ui.display_help(cmd_executor.get_commands()))
    # --- End Command Executor Setup ---


    # Set up the appropriate AI model
    model_name = args.model.strip().lower() if args.model else None
    provider_name = args.engine.strip().lower() if args.engine else None

    # --- Load Config using UI ---
    # Pass UI instance to config loading functions
    system_message = read_system_message(ui)
    project_context = read_project_context(ui)
    # --- End Load Config ---

    # Initialize conversation history
    conversation_history = History(
        system_message=system_message,
        context=project_context) # Pass context during initialization

    if project_context:
        # Acknowledge context loading (already logged in read_project_context)
        # Use ui.display_info instead of print
        ui.display_info("[Loaded context from .streetrace/ files]")

    # --- Determine and Validate Working Directory using UI ---
    initial_cwd = os.getcwd()
    target_work_dir = args.path if args.path else initial_cwd
    abs_working_dir = os.path.abspath(target_work_dir)

    # Validate if the target working directory exists and is a directory
    if not os.path.isdir(abs_working_dir):
        # Use ui.display_error instead of print
        ui.display_error(f"Specified path '{target_work_dir}' is not a valid directory. Using current directory '{initial_cwd}'.")
        logging.error(f"Specified path '{target_work_dir}' resolved to '{abs_working_dir}' which is not a valid directory.")
        abs_working_dir = os.path.abspath(initial_cwd) # Fallback to initial CWD
    else:
         # If --path was used and is valid, change the current directory
         if args.path:
             try:
                 os.chdir(abs_working_dir)
                 logging.info(f"Changed current working directory to: {abs_working_dir}")
             except Exception as e:
                 # Use ui.display_error instead of print
                 ui.display_error(f"Failed to change directory to '{abs_working_dir}': {e}")
                 logging.exception(f"Failed to change directory to '{abs_working_dir}': {e}")
                 # Fallback to initial CWD's absolute path if chdir fails
                 abs_working_dir = os.path.abspath(initial_cwd)
                 # Use ui.display_warning instead of print
                 ui.display_warning(f"Continuing from directory: {abs_working_dir}")

    # Use ui.display_info instead of print
    ui.display_info(f"Working directory: {abs_working_dir}")
    logging.info(f"Final working directory set to: {abs_working_dir}")
    # --- End Working Directory Setup ---


    # --- Tool calling closure capturing UI and work_dir ---
    def call_tool_f(tool_name, args, original_call=None): # Add default for original_call
        # Pass ui instance to call_tool
        return call_tool(tool_name, args, original_call, abs_working_dir, ui)

    # --- Initialize AI Provider using UI ---
    provider = get_ai_provider(provider_name)
    if not provider:
        # Use ui.display_error instead of print
        ui.display_error(f"Could not initialize AI provider: {provider_name or 'default'}. Please check configuration and API keys.")
        logging.critical(f"Failed to initialize AI provider: {provider_name or 'default'}")
        sys.exit(1) # Use sys.exit

    # Use ui.display_info instead of print
    ui.display_info(f"Using provider: {type(provider).__name__.replace('Provider', '')}")
    if model_name:
        # Use ui.display_info instead of print
        ui.display_info(f"Using model: {model_name}")
    else:
         # Use ui.display_info instead of print
         ui.display_info("Using default model for the provider.")
    # --- End AI Provider Setup ---


    # --- Prompt Handling Function (Accepts UI) ---
    def handle_prompt(user_prompt: str):
        """Handles parsing mentions, adding messages to history, and calling AI."""
        logging.debug(f"Handling prompt: '{user_prompt}'")
        # Pass ui instance to mention parser
        mentioned_files_content = parse_and_load_mentions(user_prompt, abs_working_dir, ui)

        # --- Add mentioned file contents to history BEFORE the user prompt ---
        # Use USER role for this context injection for simplicity,
        # as it directly precedes the user's query that might refer to it.
        if mentioned_files_content:
            # Use ui.display_info instead of print
            ui.display_info(f"[Injecting content from {len(mentioned_files_content)} mentioned file(s) into history]")
        for filepath, content in mentioned_files_content:
            # Use a clear format for the context message
            # Ensure backticks in file paths/content are handled if using markdown code blocks
            # Let's avoid code blocks for the outer message for simplicity
            context_message = f"Content of mentioned file '@{filepath}':\n---\n{content}\n---"
            # Limit injected content size to avoid excessive history growth (optional)
            MAX_MENTION_CONTENT_LENGTH = 10000 # Example limit
            if len(content) > MAX_MENTION_CONTENT_LENGTH:
                context_message = f"Content of mentioned file '@{filepath}' (truncated):\n---\n{content[:MAX_MENTION_CONTENT_LENGTH]}\n...\n---"
                logging.warning(f"Truncated content for mentioned file @{filepath} due to size.")

            conversation_history.add_message(role=Role.USER, content=[ContentPartText(text=context_message)])
            logging.debug(f"Added context from @{filepath} to history.")
        # --- End Mention Content Injection ---


        # --- Add the actual user prompt to history ---
        conversation_history.add_message(role=Role.USER, content=[ContentPartText(text=user_prompt)])
        logging.debug(f"User prompt added to history: '{user_prompt}'")
        # Log the full history before calling the AI (DEBUG level)
        logging.debug(f"Conversation History before generation: {conversation_history.conversation}")

        # --- Call the AI ---
        try:
            # TODO: Refactor generate_with_tools to accept UI for streaming output
            # For now, it might print directly or handle output internally.
            generate_with_tools(
                provider,
                model_name,
                conversation_history,
                TOOLS,
                call_tool_f, # Closure now includes ui
            )
            logging.debug("AI generation call completed.")
        except Exception as gen_err:
            # Use ui.display_error instead of print
            ui.display_error(f"An error occurred during AI generation: {gen_err}")
            logging.exception("An error occurred during AI generation call.", exc_info=gen_err)
            # Decide how to handle this - maybe continue interactive loop or exit?
            # For interactive mode, we probably want to allow the user to try again.
    # --- End Prompt Handling Function ---


    # --- Main Execution Logic (using UI) ---
    if args.prompt:
        # Non-interactive mode
        prompt_input = args.prompt
        # Use ui.display_user_prompt instead of print
        ui.display_user_prompt(prompt_input)

        # Check if the non-interactive prompt is a command
        command_executed, should_continue = cmd_executor.execute(prompt_input)

        if command_executed:
            logging.info(f"Non-interactive prompt was command: '{prompt_input}'. Exiting: {not should_continue}")
            if not should_continue:
                 # Optional: UI feedback before exiting for command
                 # ui.display_info("Executing command and exiting.")
                 sys.exit(0) # Exit cleanly if command signaled exit
            else:
                 # Optional: UI feedback before exiting for command
                 # ui.display_info("Command executed, exiting.")
                 sys.exit(0) # Also exit if command executed but didn't signal exit (e.g. help)
        else:
            # If not a command, process as AI prompt
            handle_prompt(prompt_input)
            logging.info("Non-interactive mode finished.")
    else:
        # Interactive mode
        # Use ui.display_info instead of print
        ui.display_info("Entering interactive mode. Type 'exit', 'quit' or press Ctrl+C/Ctrl+D to quit.")
        while True:
            try:
                # Use ui.get_user_input instead of input
                user_input = ui.get_user_input()

                # --- Check for commands first ---
                command_executed, should_continue = cmd_executor.execute(user_input)

                if command_executed:
                    if not should_continue:
                        # Use ui.display_info instead of print
                        ui.display_info("Exiting.") # Give user feedback on exit command
                        logging.info("Exit command executed.")
                        break # Exit the loop
                    else:
                        # Command executed, but didn't signal exit (e.g., future 'help' command)
                        continue # Go to next iteration of the loop
                # --- End Command Check ---

                # If it wasn't a command, and input is not empty, process as a prompt
                if not user_input.strip(): # Handle empty or whitespace-only input (after command check)
                    continue

                handle_prompt(user_input) # Process the valid input as AI prompt

            except EOFError: # Graceful exit on Ctrl+D
                 # Use ui.display_info instead of print
                 ui.display_info("\nExiting.")
                 logging.info("Exiting due to EOF.")
                 break
            except KeyboardInterrupt: # Graceful exit on Ctrl+C
                 # Use ui.display_info instead of print
                 ui.display_info("\nExiting.")
                 logging.info("Exiting due to KeyboardInterrupt.")
                 break
            except Exception as loop_err:
                # Catch unexpected errors in the loop/input handling
                # Use ui.display_error instead of print
                ui.display_error(f"\nAn unexpected error occurred: {loop_err}")
                logging.exception("Unexpected error in interactive loop.", exc_info=loop_err)
                # Optional: break here or allow continuing? Let's allow continue for now.


if __name__ == "__main__":
    main()
