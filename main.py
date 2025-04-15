# main.py
import json
import logging
import os
import argparse
import sys

# Core application components
from app.application import Application # <-- Added import
from app.command_executor import CommandExecutor
from app.console_ui import ConsoleUI
from app.interaction_manager import InteractionManager
from app.prompt_processor import PromptProcessor

# LLM and Tooling
from llm.llmapi_factory import get_ai_provider
from llm.wrapper import History, Role, ContentPartText # Kept for call_tool, though not directly used in main loop
from tools.fs_tool import TOOLS, TOOL_IMPL

# --- Logging Configuration ---
# Basic config for file logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='generation.log',
                    filemode='a') # Append mode

# Console handler for user-facing logs
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)

# Root logger setup
root_logger = logging.getLogger()
# Set root logger level to DEBUG initially to capture everything
root_logger.setLevel(logging.DEBUG)
# --- End Logging Configuration ---

def parse_arguments():
    """Parses command line arguments."""
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


def call_tool(tool_name, args, original_call, work_dir, ui: ConsoleUI):
    """
    Calls the appropriate tool function based on the tool name, using UI for output.

    Args:
        tool_name: Name of the tool to call.
        args: Dictionary of arguments to pass to the function.
        original_call: The original function call object from the model (if available).
        work_dir: Path to use as the working directory for file operations.
        ui: The ConsoleUI instance for displaying messages.

    Returns:
        dict: A dictionary representing the tool result (success or error).
    """
    # Tool call display and logging (unchanged)
    args_display = json.dumps(args)
    if len(args_display) > 100:
        args_display = args_display[:97] + "..."
    ui.display_tool_call(tool_name, args_display)
    logging.info(f"Tool call: {tool_name} with args: {args}")

    if tool_name in TOOL_IMPL:
        tool_func = TOOL_IMPL[tool_name]
        tool_result = None
        try:
            # Inspect and call tool function, handling work_dir injection (unchanged)
            import inspect
            sig = inspect.signature(tool_func)
            tool_params = sig.parameters
            if 'work_dir' in tool_params:
                args_with_workdir = { **args, 'work_dir': work_dir }
                tool_result = tool_func(**args_with_workdir)
            else:
                tool_result = tool_func(**args)

            # Format result for display and logging (unchanged)
            if not isinstance(tool_result, dict):
                 result_data = {"result": tool_result}
            else:
                 result_data = tool_result
            display_result = str(result_data)
            ui.display_tool_result(display_result)
            logging.info(f"Tool '{tool_name}' result: {result_data}")

            # Prepare final result payload, handling non-serializable data (unchanged)
            final_result_payload = {}
            try:
                 json.dumps(result_data)
                 final_result_payload = {"success": True, "result": result_data}
            except TypeError as json_err:
                 logging.warning(f"Tool '{tool_name}' result is not fully JSON serializable: {json_err}. Returning string representation within result.")
                 final_result_payload = {"success": True, "result": str(result_data)}
            return final_result_payload

        except Exception as e:
            # Handle tool execution errors (unchanged)
            error_msg = f"Error executing tool '{tool_name}': {str(e)}"
            ui.display_error(error_msg)
            logging.exception(f"Error during tool call: {tool_name} with args {args}", exc_info=e)
            return {"error": True, "message": error_msg}
    else:
        # Handle tool not found errors (unchanged)
        error_msg = f"Tool not found: {tool_name}"
        ui.display_error(error_msg)
        logging.error(error_msg)
        return {"error": True, "message": error_msg}
# --- End call_tool ---


def main():
    """Main entry point for the application."""
    args = parse_arguments()
    ui = ConsoleUI(debug_enabled=args.debug)

    # --- Configure Logging Level based on args ---
    if args.debug:
        console_handler.setLevel(logging.DEBUG)
        # Keep root logger at DEBUG to allow file handler to capture everything
        logging.debug("Debug logging enabled for console.")
    else:
        console_handler.setLevel(logging.WARNING)
        # Root logger stays DEBUG, file handler is INFO, console handler is INFO
    # Add the console handler *after* setting its level based on debug flag
    root_logger.addHandler(console_handler)
    # --- End Logging Configuration ---

    # --- Initialize Core Application Components ---
    cmd_executor = CommandExecutor()
    prompt_processor = PromptProcessor(ui=ui)
    # --- End Component Initialization ---

    # --- Register Base Commands ---
    # Commands handled by the application loop or require app instance
    cmd_executor.register("exit", lambda: False, "Exit the interactive session.")
    cmd_executor.register("quit", lambda: False, "Quit the interactive session.")
    # Register history - the action expects the app_instance passed by execute
    cmd_executor.register("history",
                          lambda app: app._display_history() if app else False,
                          "Display the conversation history.")
    # Add help command (can now be implemented better)
    # def display_help(ui_instance, executor_instance):
    #     ui_instance.display_info("Available commands:")
    #     descriptions = executor_instance.get_command_descriptions()
    #     for name, desc in sorted(descriptions.items()):
    #         ui_instance.display_info(f"  {name}: {desc}")
    #     return True # Continue running
    # cmd_executor.register("help", lambda app: display_help(ui, cmd_executor), "Show available commands.")
    # --- End Command Registration ---

    # --- Determine Model and Provider ---
    model_name = args.model.strip().lower() if args.model else None
    provider_name = args.engine.strip().lower() if args.engine else None
    # --- End Model/Provider Determination ---

    # --- Determine and Validate Working Directory ---
    initial_cwd = os.getcwd()
    target_work_dir = args.path if args.path else initial_cwd
    abs_working_dir = os.path.abspath(target_work_dir)

    if not os.path.isdir(abs_working_dir):
        ui.display_error(f"Specified path '{target_work_dir}' is not a valid directory. Using current directory '{initial_cwd}'.")
        logging.error(f"Specified path '{target_work_dir}' resolved to '{abs_working_dir}' which is not a valid directory.")
        abs_working_dir = os.path.abspath(initial_cwd)
    else:
         if args.path: # Only try to change dir if --path was specified
             try:
                 # Attempt to change the CWD for consistency, though tools use abs_working_dir
                 os.chdir(abs_working_dir)
                 logging.info(f"Changed current working directory to: {abs_working_dir}")
             except Exception as e:
                 ui.display_error(f"Failed to change directory to '{abs_working_dir}': {e}")
                 logging.exception(f"Failed to change directory to '{abs_working_dir}': {e}")
                 # Keep using the resolved absolute path even if chdir failed
                 ui.display_warning(f"Proceeding with resolved path: {abs_working_dir}")

    ui.display_info(f"Working directory: {abs_working_dir}")
    logging.info(f"Effective working directory set to: {abs_working_dir}")
    # --- End Working Directory Setup ---

    # --- Initialize AI Provider ---
    try:
        provider = get_ai_provider(provider_name)
        if not provider:
             raise ValueError(f"Provider '{provider_name or 'default'}' could not be loaded.") # More specific error
        ui.display_info(f"Using provider: {type(provider).__name__.replace('Provider', '')}")
        if model_name:
            ui.display_info(f"Using model: {model_name}")
        else:
             ui.display_info("Using default model for the provider.")
    except Exception as e:
        ui.display_error(f"Could not initialize AI provider: {e}")
        logging.critical(f"Failed to initialize AI provider: {e}", exc_info=True)
        sys.exit(1)
    # --- End AI Provider Setup ---

    # --- Tool Calling Closure ---
    # Define a closure that captures the current working directory and UI instance
    # This is passed to the InteractionManager so it can invoke tools correctly.
    def call_tool_f(tool_name, tool_args, original_call=None):
        return call_tool(tool_name, tool_args, original_call, abs_working_dir, ui)
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

    # --- Initialize and Run Application ---
    # All components are now ready, instantiate the main Application object.
    app = Application(
        args=args,
        ui=ui,
        cmd_executor=cmd_executor,
        prompt_processor=prompt_processor,
        interaction_manager=interaction_manager,
        working_dir=abs_working_dir  # Pass the validated absolute path
    )

    # --- Optional: Add commands that require the app instance AFTER it's created ---
    # Example: If we wanted to register history *here* instead of above:
    # cmd_executor.register("history", app._display_history, "Display conversation history.")
    # The initial registration method is preferred as it keeps registrations together.

    # Start the application execution (handles interactive/non-interactive modes)
    try:
        app.run()
    except Exception as app_err:
         # Catch unexpected errors from the Application run loop
         ui.display_error(f"An critical error occurred: {app_err}")
         logging.critical("Critical error during application execution.", exc_info=app_err)
         sys.exit(1)
    # --- End Application Execution ---

if __name__ == "__main__":
    main()
