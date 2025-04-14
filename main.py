# Corrected code for main.py

import json
import logging
import os
import argparse
import re # Make sure re is imported
from llm.wrapper import ContentPartText, History, Role
from tools.fs_tool import TOOLS, TOOL_IMPL
from messages import SYSTEM
from colors import AnsiColors
from llm.llmapi_factory import get_ai_provider
from llm.generate import generate_with_tools

# Configure logging
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
# Avoid double printing if root logger already had handlers (though basicConfig should handle this)
# root_logger.propagate = False # Generally not needed after basicConfig

# --- Logging Setup Complete ---

def read_system_message():
    """
    Read the system message from a file or return the default message.

    Returns:
        str: The system message content
    """
    system_message_path = '.streetrace/system.md'
    if os.path.exists(system_message_path):
        try:
            with open(system_message_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            # Use logging for errors, print is less flexible
            logging.error(f"Error reading system message file '{system_message_path}': {e}")
            print(f"{AnsiColors.TOOLERROR}Error reading system message file: {e}{AnsiColors.RESET}") # Keep print for immediate user feedback

    # Default system message
    return SYSTEM


def read_project_context():
    """
    Read all project context files from .streetrace directory excluding system.md.

    Returns:
        str: Combined content of all context files, or empty string if none exist
    """
    context_files_dir = '.streetrace'
    combined_context = ""

    # Check if the directory exists
    if not os.path.exists(context_files_dir) or not os.path.isdir(context_files_dir):
        logging.info(f"Context directory '{context_files_dir}' not found.")
        return combined_context

    # Get all files in the directory excluding system.md
    try:
        context_files = [
            f for f in os.listdir(context_files_dir)
            if os.path.isfile(os.path.join(context_files_dir, f)) and f != 'system.md'
        ]
    except Exception as e:
        logging.error(f"Error listing context directory '{context_files_dir}': {e}")
        print(f"{AnsiColors.TOOLERROR}Error listing context directory '{context_files_dir}': {e}{AnsiColors.RESET}")
        return combined_context

    if not context_files:
        logging.info(f"No context files found in '{context_files_dir}'.")
        return combined_context

    # Read and combine content from all context files
    context_content_parts = []
    logging.info(f"Reading context files: {', '.join(context_files)}")
    for file_name in context_files:
        file_path = os.path.join(context_files_dir, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Use a more structured format for context clarity
                context_content_parts.append(f"\n\n--- Context from: {file_name} ---\n\n{content}\n\n--- End Context: {file_name} ---\n")
        except Exception as e:
            logging.error(f"Error reading context file {file_path}: {e}")
            print(f"{AnsiColors.TOOLERROR}Error reading context file {file_path}: {e}{AnsiColors.RESET}")

    combined_context = "".join(context_content_parts)
    logging.info(f"Successfully loaded context from {len(context_content_parts)} file(s).")
    return combined_context


def parse_and_load_mentions(prompt: str, working_dir: str) -> list[tuple[str, str]]:
    """
    Parses a prompt for @<filepath> mentions, cleans trailing punctuation,
    validates the paths relative to the working directory, and loads the
    content of valid files.

    Args:
        prompt: The user input string.
        working_dir: The current working directory for resolving relative paths.

    Returns:
        A list of tuples, where each tuple contains the cleaned mentioned filepath
        (relative to working_dir) and its content. Returns an empty list
        if no valid mentions are found.
    """
    # Regex to find @ followed by non-space, non-@ characters
    mention_pattern = r"@([^\s@]+)"
    raw_mentions = re.findall(mention_pattern, prompt)

    # Process mentions: strip trailing punctuation and ensure uniqueness
    processed_mentions = set()
    # Define the set of punctuation characters to strip from the end
    # Corrected string literal:
    trailing_punctuation = '.,!?;:)]}"\'' # Use single quotes for the outer string, escape internal single quote

    for raw_mention in raw_mentions:
        cleaned_mention = raw_mention
        # Keep stripping as long as the string is longer than 1 char and the last char is punctuation
        while len(cleaned_mention) > 1 and cleaned_mention[-1] in trailing_punctuation:
            cleaned_mention = cleaned_mention[:-1]
        # Add the potentially cleaned mention to the set
        processed_mentions.add(cleaned_mention)

    # Convert set back to list and sort for deterministic order in tests/output
    mentions = sorted(list(processed_mentions))
    loaded_files = []

    if not mentions:
        return loaded_files

    print(f"{AnsiColors.INFO}[Detected mentions: {', '.join(['@'+m for m in mentions])}]{AnsiColors.RESET}")
    logging.info(f"Detected mentions after cleaning: {', '.join(mentions)}")

    absolute_working_dir = os.path.realpath(working_dir) # Resolve symlinks for working dir

    for mention in mentions:
        # Construct the potential path relative to the working directory using the cleaned mention
        potential_rel_path = mention # Keep cleaned mention for return value
        try:
            # Join working dir and mention, then normalize (removes '.', handles '/')
            normalized_path = os.path.normpath(os.path.join(working_dir, mention))

            # Resolve symlinks and get the canonical absolute path
            absolute_mention_path = os.path.realpath(normalized_path)

            # --- Security Check ---
            # Ensure the canonical path of the file is within the canonical path of the working directory
            common_path = os.path.commonpath([absolute_working_dir, absolute_mention_path])

            # Important: commonpath might return a parent if paths diverge early.
            # We must ensure the common path *is* the working directory.
            if common_path != absolute_working_dir:
                 print(f"{AnsiColors.TOOLERROR}[Security Warning] Mention '@{mention}' points outside the working directory '{working_dir}'. Skipping.{AnsiColors.RESET}")
                 logging.warning(f"Security Warning: Mention '@{mention}' resolved to '{absolute_mention_path}' which is outside the working directory '{absolute_working_dir}'. Skipping.")
                 continue
            # --- End Security Check ---

            if os.path.isfile(absolute_mention_path):
                try:
                    with open(absolute_mention_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # Return the cleaned mention (relative path user likely intended) and content
                    loaded_files.append((potential_rel_path, content))
                    print(f"{AnsiColors.INFO}[Loaded context from @{mention}]{AnsiColors.RESET}")
                    logging.info(f"Loaded context from mentioned file: {absolute_mention_path} (Mention: @{mention})")
                except Exception as e:
                    print(f"{AnsiColors.TOOLERROR}[Error reading @{mention}: {e}]{AnsiColors.RESET}")
                    logging.error(f"Error reading mentioned file '{absolute_mention_path}' (Mention: @{mention}): {e}")
            else:
                # File not found *after* security check and path resolution
                print(f"{AnsiColors.TOOLERROR}[Mentioned path @{mention} ('{absolute_mention_path}') not found or is not a file. Skipping.]{AnsiColors.RESET}")
                logging.warning(f"Mentioned path '@{mention}' resolved to '{absolute_mention_path}' which was not found or is not a file.")
        except Exception as e:
            # Catch potential errors during path manipulation (e.g., invalid chars)
            print(f"{AnsiColors.TOOLERROR}[Error processing mention @{mention}: {e}]{AnsiColors.RESET}")
            logging.error(f"Error processing mention '@{mention}': {e}")

    return loaded_files


def parse_arguments():
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: The parsed arguments
    """
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


def call_tool(tool_name, args, original_call, work_dir):
    """
    Call the appropriate tool function based on the tool name.

    Args:
        tool_name: Name of the tool to call
        args: Dictionary of arguments to pass to the function
        original_call: The original function call object from the model (if available)
        work_dir: Path to use as the working directory for file operations

    Returns:
        dict: A dictionary representing the tool result (success or error)
    """
    # Use json.dumps for potentially complex args display, limit length
    args_display = json.dumps(args)
    if len(args_display) > 100:
        args_display = args_display[:97] + "..."
    print(f"{AnsiColors.TOOL}Tool Call: {tool_name}({args_display}){AnsiColors.RESET}")
    logging.info(f"Tool call: {tool_name} with args: {args}") # Log full args

    if tool_name in TOOL_IMPL:
        tool_func = TOOL_IMPL[tool_name]
        tool_result = None
        # Check if the tool function expects 'work_dir' and add it if necessary
        try:
            # Get parameters of the tool function
            import inspect
            sig = inspect.signature(tool_func)
            tool_params = sig.parameters

            if 'work_dir' in tool_params:
                # Only add work_dir if the function expects it
                args_with_workdir = { **args, 'work_dir': work_dir }
                tool_result = tool_func(**args_with_workdir)
            else:
                # Call without work_dir if not expected
                tool_result = tool_func(**args)

            # Prepare result for logging and display
            # Convert result to dict if it's not already (for consistency)
            if not isinstance(tool_result, dict):
                 # Basic conversion, assuming simple types or objects with __str__
                 result_data = {"result": tool_result}
            else:
                 result_data = tool_result

            display_result = str(result_data) # Use str representation for display
            if len(display_result) > 500:
                display_result = display_result[:497] + "..."

            print(f"{AnsiColors.TOOL}Result: {display_result}{AnsiColors.RESET}")
            logging.info(f"Tool '{tool_name}' result: {result_data}") # Log structured result

            # Return a structured result suitable for the AI model (Claude expects specific format)
            # Ensure the result is JSON serializable if it's complex
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
            print(f"{AnsiColors.TOOLERROR}{error_msg}{AnsiColors.RESET}")
            # Log full exception with stack trace
            logging.exception(f"Error during tool call: {tool_name} with args {args}", exc_info=e)
            # Return a structured error message
            return {"error": True, "message": error_msg}
    else:
        error_msg = f"Tool not found: {tool_name}"
        print(f"{AnsiColors.TOOLERROR}{error_msg}{AnsiColors.RESET}")
        logging.error(error_msg)
        # Return a structured error message
        return {"error": True, "message": error_msg}


def main():
    """Main entry point for the application"""
    # Parse command line arguments
    args = parse_arguments()

    # --- Configure Logging Level based on --debug ---
    if args.debug:
        # Set console handler to DEBUG, file handler remains INFO (or DEBUG if needed)
        console_handler.setLevel(logging.DEBUG)
        # Optionally set file handler level too:
        # logging.getLogger().handlers[0].setLevel(logging.DEBUG) # Assuming file handler is the first one
        root_logger.setLevel(logging.DEBUG) # Ensure root logger captures DEBUG
        logging.debug("Debug logging enabled.")
    else:
        # Set console handler to INFO, file handler remains INFO
        console_handler.setLevel(logging.INFO)
        root_logger.setLevel(logging.INFO) # Ensure root logger captures INFO
    # --- End Logging Level Config ---

    # Set up the appropriate AI model
    model_name = args.model.strip().lower() if args.model else None
    provider_name = args.engine.strip().lower() if args.engine else None

    # Initialize conversation history
    system_message = read_system_message()
    project_context = read_project_context()
    conversation_history = History(
        system_message=system_message,
        context=project_context) # Pass context during initialization

    if project_context:
        # Acknowledge context loading (already logged in read_project_context)
        print(f"{AnsiColors.INFO}[Loaded context from .streetrace/ files]{AnsiColors.RESET}")

    # --- Determine and Validate Working Directory ---
    initial_cwd = os.getcwd()
    target_work_dir = args.path if args.path else initial_cwd
    abs_working_dir = os.path.abspath(target_work_dir)

    # Validate if the target working directory exists and is a directory
    if not os.path.isdir(abs_working_dir):
        print(f"{AnsiColors.TOOLERROR}Specified path '{target_work_dir}' is not a valid directory. Using current directory '{initial_cwd}'.{AnsiColors.RESET}")
        logging.error(f"Specified path '{target_work_dir}' resolved to '{abs_working_dir}' which is not a valid directory.")
        abs_working_dir = os.path.abspath(initial_cwd) # Fallback to initial CWD
    else:
         # If --path was used and is valid, change the current directory
         if args.path:
             try:
                 os.chdir(abs_working_dir)
                 logging.info(f"Changed current working directory to: {abs_working_dir}")
             except Exception as e:
                 print(f"{AnsiColors.TOOLERROR}Failed to change directory to '{abs_working_dir}': {e}{AnsiColors.RESET}")
                 logging.exception(f"Failed to change directory to '{abs_working_dir}': {e}")
                 # Fallback to initial CWD's absolute path if chdir fails
                 abs_working_dir = os.path.abspath(initial_cwd)
                 print(f"{AnsiColors.WARNING}Continuing from directory: {abs_working_dir}{AnsiColors.RESET}")

    print(f"{AnsiColors.INFO}Working directory: {abs_working_dir}{AnsiColors.RESET}")
    logging.info(f"Final working directory set to: {abs_working_dir}")
    # --- End Working Directory Setup ---


    # Tool calling function closure, capturing the final absolute working directory
    def call_tool_f(tool_name, args, original_call=None): # Add default for original_call
        return call_tool(tool_name, args, original_call, abs_working_dir)

    # Initialize AI Provider
    provider = get_ai_provider(provider_name)
    if not provider:
        print(f"{AnsiColors.TOOLERROR}Could not initialize AI provider: {provider_name or 'default'}. Please check configuration and API keys.{AnsiColors.RESET}")
        logging.critical(f"Failed to initialize AI provider: {provider_name or 'default'}")
        exit(1) # Exit if provider fails

    print(f"{AnsiColors.INFO}Using provider: {type(provider).__name__.replace('Provider', '')}{AnsiColors.RESET}")
    if model_name:
        print(f"{AnsiColors.INFO}Using model: {model_name}{AnsiColors.RESET}")
    else:
         print(f"{AnsiColors.INFO}Using default model for the provider.{AnsiColors.RESET}")


    # --- Refactored Prompt Handling Function ---
    def handle_prompt(user_prompt: str):
        """Handles parsing mentions, adding messages to history, and calling AI."""
        logging.debug(f"Handling prompt: '{user_prompt}'")
        # Parse mentions and load file contents using the absolute working directory
        mentioned_files_content = parse_and_load_mentions(user_prompt, abs_working_dir)

        # --- Add mentioned file contents to history BEFORE the user prompt ---
        # Use USER role for this context injection for simplicity,
        # as it directly precedes the user's query that might refer to it.
        if mentioned_files_content:
            print(f"{AnsiColors.INFO}[Injecting content from {len(mentioned_files_content)} mentioned file(s) into history]{AnsiColors.RESET}")
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
        logging.info(f"User prompt added to history: '{user_prompt}'")
        # Log the full history before calling the AI (DEBUG level)
        logging.debug(f"Conversation History before generation: {conversation_history.conversation}")

        # --- Call the AI ---
        try:
            generate_with_tools(
                provider,
                model_name,
                conversation_history,
                TOOLS,
                call_tool_f, # Pass the closure
            )
            logging.debug("AI generation call completed.")
        except Exception as gen_err:
            print(f"{AnsiColors.TOOLERROR}An error occurred during AI generation: {gen_err}{AnsiColors.RESET}")
            logging.exception("An error occurred during AI generation call.", exc_info=gen_err)
            # Decide how to handle this - maybe continue interactive loop or exit?
            # For interactive mode, we probably want to allow the user to try again.
    # --- End Prompt Handling Function ---


    # --- Main Execution Logic (Interactive vs Non-interactive) ---
    if args.prompt:
        # Non-interactive mode
        print(f"{AnsiColors.USER}Prompt:{AnsiColors.RESET} {args.prompt}")
        handle_prompt(args.prompt)
        logging.info("Non-interactive mode finished.")
    else:
        # Interactive mode
        print(f"{AnsiColors.INFO}Entering interactive mode. Type 'exit' or press Ctrl+C/Ctrl+D to quit.{AnsiColors.RESET}")
        while True:
            try:
                user_input = input(f"{AnsiColors.USER}You:{AnsiColors.RESET} ")
                if user_input.lower() == "exit":
                    logging.info("User requested exit.")
                    break
                if not user_input.strip(): # Handle empty or whitespace-only input
                    continue

                handle_prompt(user_input) # Process the valid input

            except EOFError: # Graceful exit on Ctrl+D
                 print("\nExiting.")
                 logging.info("Exiting due to EOF.")
                 break
            except KeyboardInterrupt: # Graceful exit on Ctrl+C
                 print("\nExiting.")
                 logging.info("Exiting due to KeyboardInterrupt.")
                 break
            except Exception as loop_err:
                # Catch unexpected errors in the loop/input handling
                print(f"{AnsiColors.TOOLERROR}\nAn unexpected error occurred: {loop_err}{AnsiColors.RESET}")
                logging.exception("Unexpected error in interactive loop.", exc_info=loop_err)
                # Optional: break here or allow continuing? Let's allow continue for now.


if __name__ == "__main__":
    main()
