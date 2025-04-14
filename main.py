# Corrected code for main.py

import json
import logging
import os
import argparse
import sys

from llm.wrapper import ContentPartText, History, Role
from tools.fs_tool import TOOLS, TOOL_IMPL
from llm.llmapi_factory import get_ai_provider
from app.command_executor import CommandExecutor
from app.console_ui import ConsoleUI
from app.prompt_processor import PromptProcessor, PromptContext
# --- New Import ---
from app.interaction_manager import InteractionManager

# --- Logging configuration remains the same ---
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


# --- call_tool function remains the same ---
def call_tool(tool_name, args, original_call, work_dir, ui: ConsoleUI):
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
            ui.display_tool_result(display_result)
            logging.info(f"Tool '{tool_name}' result: {result_data}")

            final_result_payload = {}
            try:
                 json.dumps(result_data)
                 final_result_payload = {"success": True, "result": result_data}
            except TypeError as json_err:
                 logging.warning(f"Tool '{tool_name}' result is not fully JSON serializable: {json_err}. Returning string representation within result.")
                 final_result_payload = {"success": True, "result": str(result_data)}

            return final_result_payload

        except Exception as e:
            error_msg = f"Error executing tool '{tool_name}': {str(e)}"
            ui.display_error(error_msg)
            logging.exception(f"Error during tool call: {tool_name} with args {args}", exc_info=e)
            return {"error": True, "message": error_msg}
    else:
        error_msg = f"Tool not found: {tool_name}"
        ui.display_error(error_msg)
        logging.error(error_msg)
        return {"error": True, "message": error_msg}
# --- End call_tool ---


def main():
    """Main entry point for the application"""
    args = parse_arguments()
    ui = ConsoleUI(debug_enabled=args.debug)

    # --- Logging Config ---
    if args.debug:
        console_handler.setLevel(logging.DEBUG)
        root_logger.setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled.")
    else:
        console_handler.setLevel(logging.INFO)
        root_logger.setLevel(logging.INFO)
    # --- End Logging Config ---

    # --- Initialize Core Components ---
    cmd_executor = CommandExecutor()
    prompt_processor = PromptProcessor(ui=ui)
    # --- End Initialize Core Components ---

    # --- Register Commands ---
    cmd_executor.register("exit", lambda: False)
    cmd_executor.register("quit", lambda: False)
    # cmd_executor.register("help", lambda: ui.display_help(cmd_executor.get_commands()))
    # --- End Register Commands ---

    model_name = args.model.strip().lower() if args.model else None
    provider_name = args.engine.strip().lower() if args.engine else None

    # --- Determine and Validate Working Directory ---
    initial_cwd = os.getcwd()
    target_work_dir = args.path if args.path else initial_cwd
    abs_working_dir = os.path.abspath(target_work_dir)
    # (Validation logic remains the same)
    if not os.path.isdir(abs_working_dir):
        ui.display_error(f"Specified path '{target_work_dir}' is not a valid directory. Using current directory '{initial_cwd}'.")
        logging.error(f"Specified path '{target_work_dir}' resolved to '{abs_working_dir}' which is not a valid directory.")
        abs_working_dir = os.path.abspath(initial_cwd)
    else:
         if args.path:
             try:
                 os.chdir(abs_working_dir)
                 logging.info(f"Changed current working directory to: {abs_working_dir}")
             except Exception as e:
                 ui.display_error(f"Failed to change directory to '{abs_working_dir}': {e}")
                 logging.exception(f"Failed to change directory to '{abs_working_dir}': {e}")
                 abs_working_dir = os.path.abspath(initial_cwd)
                 ui.display_warning(f"Continuing from directory: {abs_working_dir}")

    ui.display_info(f"Working directory: {abs_working_dir}")
    logging.info(f"Final working directory set to: {abs_working_dir}")
    # --- End Working Directory Setup ---

    # --- Initialize AI Provider ---
    provider = get_ai_provider(provider_name)
    if not provider:
        ui.display_error(f"Could not initialize AI provider: {provider_name or 'default'}. Please check configuration and API keys.")
        logging.critical(f"Failed to initialize AI provider: {provider_name or 'default'}")
        sys.exit(1)

    ui.display_info(f"Using provider: {type(provider).__name__.replace('Provider', '')}")
    if model_name:
        ui.display_info(f"Using model: {model_name}")
    else:
         ui.display_info("Using default model for the provider.")
    # --- End AI Provider Setup ---

    # --- Tool calling closure ---
    # This needs to be defined before InteractionManager uses it
    def call_tool_f(tool_name, args, original_call=None):
        return call_tool(tool_name, args, original_call, abs_working_dir, ui)
    # --- End Tool Calling Closure ---

    # --- Initialize Interaction Manager ---
    interaction_manager = InteractionManager(
        provider=provider,
        model_name=model_name,
        tools=TOOLS,
        tool_callback=call_tool_f,
        ui=ui
    )
    # --- End Initialize Interaction Manager ---


    # --- Conversation History Initialization (for interactive mode) ---
    initial_context = prompt_processor.build_context("", abs_working_dir)
    conversation_history = History(
        system_message=initial_context.system_message,
        context=initial_context.project_context
    )
    # --- End History Initialization ---


    # --- Modified Prompt Handling Function (using InteractionManager) ---
    # Now accepts interaction_manager and prompt_processor
    def handle_prompt(user_prompt: str,
                      current_history: History,
                      proc: PromptProcessor, # Renamed for clarity
                      im: InteractionManager): # Renamed for clarity
        """Processes prompt, updates history, and triggers AI interaction."""
        logging.debug(f"Handling prompt: '{user_prompt}'")

        # Use PromptProcessor to parse mentions for the current prompt
        prompt_specific_context = proc.build_context(user_prompt, abs_working_dir)

        # Add mentioned file contents to history
        for filepath, content in prompt_specific_context.mentioned_files:
            context_message = f"Content of mentioned file '@{filepath}':\n---\n{content}\n---"
            MAX_MENTION_CONTENT_LENGTH = 10000
            if len(content) > MAX_MENTION_CONTENT_LENGTH:
                context_message = f"Content of mentioned file '@{filepath}' (truncated):\n---\n{content[:MAX_MENTION_CONTENT_LENGTH]}\n...\n---"
                logging.warning(f"Truncated content for mentioned file @{filepath} due to size.")
            current_history.add_message(role=Role.USER, content=[ContentPartText(text=context_message)])
            logging.debug(f"Added context from @{filepath} to history.")

        # Add the actual user prompt to history
        current_history.add_message(role=Role.USER, content=[ContentPartText(text=user_prompt)])
        logging.debug(f"User prompt added to history: '{user_prompt}'")
        logging.debug(f"Conversation History before generation: {current_history.conversation}")

        # Call the Interaction Manager to handle the AI call
        # Error handling is now done inside the interaction_manager
        im.process_prompt(current_history)
    # --- End Prompt Handling Function ---


    # --- Main Execution Logic (using InteractionManager) ---
    if args.prompt:
        # Non-interactive mode
        prompt_input = args.prompt
        ui.display_user_prompt(prompt_input)

        command_executed, should_continue = cmd_executor.execute(prompt_input)

        if command_executed:
            logging.info(f"Non-interactive prompt was command: '{prompt_input}'. Exiting: {not should_continue}")
            sys.exit(0)
        else:
            # Create history for single prompt run
            prompt_context = prompt_processor.build_context(prompt_input, abs_working_dir)
            single_prompt_history = History(
                system_message=prompt_context.system_message,
                context=prompt_context.project_context
            )
            # Call handle_prompt with the single-use history and managers
            handle_prompt(prompt_input,
                          single_prompt_history,
                          prompt_processor,
                          interaction_manager)
            logging.info("Non-interactive mode finished.")
    else:
        # Interactive mode (uses the persistent conversation_history)
        ui.display_info("Entering interactive mode. Type 'exit', 'quit' or press Ctrl+C/Ctrl+D to quit.")
        while True:
            try:
                user_input = ui.get_user_input()

                command_executed, should_continue = cmd_executor.execute(user_input)

                if command_executed:
                    if not should_continue:
                        ui.display_info("Exiting.")
                        logging.info("Exit command executed.")
                        break
                    else:
                        continue

                if not user_input.strip():
                    continue

                # Pass persistent history and managers to handle_prompt
                handle_prompt(user_input,
                              conversation_history,
                              prompt_processor,
                              interaction_manager)

            except EOFError:
                 ui.display_info("\nExiting.")
                 logging.info("Exiting due to EOF.")
                 break
            except KeyboardInterrupt:
                 ui.display_info("\nExiting.")
                 logging.info("Exiting due to KeyboardInterrupt.")
                 break
            except Exception as loop_err:
                ui.display_error(f"\nAn unexpected error occurred: {loop_err}")
                logging.exception("Unexpected error in interactive loop.", exc_info=loop_err)


if __name__ == "__main__":
    main()
