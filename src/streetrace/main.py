# main.py
import argparse
import logging
import os
import sys

# Updated completer import
from streetrace.completer import PromptCompleter, PathCompleter, CommandCompleter
from streetrace.prompt_processor import PromptProcessor

# Core application components
from streetrace.application import Application
from streetrace.commands.command_executor import CommandExecutor
from streetrace.llm.llmapi_factory import get_ai_provider
from streetrace.tools.fs_tool import TOOL_IMPL, TOOLS
from streetrace.tools.tools import ToolCall
from streetrace.ui.console_ui import ConsoleUI
from streetrace.ui.interaction_manager import InteractionManager

# --- Logging Configuration ---
# Basic config for file logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="generation.log",
    filemode="a",
)  # Append mode

# Console handler for user-facing logs
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(levelname)s: %(message)s")
console_handler.setFormatter(console_formatter)

# Root logger setup
root_logger = logging.getLogger()
# Set root logger level to DEBUG initially to capture everything
root_logger.setLevel(logging.DEBUG)
# --- End Logging Configuration ---


def parse_arguments():
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run AI assistant with different models"
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=["claude", "gemini", "ollama", "openai"],
        help="Choose AI engine (claude, gemini, ollama, or openai)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Specific model name to use (e.g., claude-3-opus-20240229, gemini-1.5-flash, llama3:8b, or gpt-4o)",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Prompt to send to the AI model (skips interactive mode if provided)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Specify which path to use as the working directory for all file operations",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging to console and file."
    )
    return parser.parse_args()

def init_working_directory(args_path: str) -> str:
    initial_cwd = os.getcwd()
    target_work_dir = args_path if args_path else initial_cwd
    abs_working_dir = os.path.abspath(target_work_dir)

    # Basic validation before UI initialization
    is_valid_dir = os.path.isdir(abs_working_dir)
    if not is_valid_dir:
        raise ValueError(
            f"Specified path '{target_work_dir}' resolved to '{abs_working_dir}' which is not a valid directory."
        )
    # --- End Initial Working Directory Setup ---

    # --- Refine Working Directory and Change CWD (if applicable) ---
    if abs_working_dir != initial_cwd:
        os.chdir(abs_working_dir)

    return abs_working_dir

def main():
    """Main entry point for the application."""
    args = parse_arguments()

    # --- Configure Logging Level based on args ---
    if args.debug:
        root_logger.addHandler(console_handler)
        logging.info("Debug logging enabled for console.")
    # --- End Logging Configuration ---

    abs_working_dir = init_working_directory(args.path)
    logging.info(f"Effective working directory: {abs_working_dir}")

    # --- Initialize Completers ---
    available_commands = ["/exit", "/quit", "/history"] # Add other commands here if needed
    path_completer = PathCompleter(abs_working_dir)
    command_completer = CommandCompleter(available_commands)

    # Instantiate the composite completer with a list of delegates
    prompt_completer = PromptCompleter([path_completer, command_completer])
    # --- End Completer Initialization ---

    # --- Initialize ConsoleUI with the composite completer ---
    ui = ConsoleUI(completer=prompt_completer, debug_enabled=args.debug)
    # --- End UI Initialization ---

    ui.display_info(f"Working directory: {abs_working_dir}")
    # --- End Refined Working Directory Setup ---

    # --- Initialize Core Application Components ---
    cmd_executor = CommandExecutor()
    prompt_processor = PromptProcessor(ui=ui)
    # --- End Component Initialization ---

    # --- Register Base Commands ---
    cmd_executor.register("/exit", lambda: False, "Exit the interactive session.")
    cmd_executor.register("/quit", lambda: False, "Quit the interactive session.")
    cmd_executor.register(
        "/history",
        lambda app: app._display_history() if app else False,
        "Display the conversation history.",
    )
    # --- End Command Registration ---

    # --- Determine Model and Provider ---
    model_name = args.model.strip().lower() if args.model else None
    provider_name = args.engine.strip().lower() if args.engine else None
    # --- End Model/Provider Determination ---

    # --- Initialize AI Provider ---
    try:
        provider = get_ai_provider(provider_name)
        if not provider:
            raise ValueError(
                f"Provider '{provider_name or 'default'}' could not be loaded."
            )
        ui.display_info(
            f"Using provider: {type(provider).__name__.replace('Provider', '')}"
        )
        if model_name:
            ui.display_info(f"Using model: {model_name}")
        else:
            ui.display_info("Using default model for the provider.")
    except Exception as e:
        ui.display_error(f"Could not initialize AI provider: {e}")
        logging.critical(f"Failed to initialize AI provider: {e}", exc_info=True)
        sys.exit(1)
    # --- End AI Provider Setup ---

    # --- Tool Calling ---
    tools = ToolCall(TOOLS, TOOL_IMPL, abs_working_dir)
    # --- End Tool Calling ---

    # --- Initialize Interaction Manager ---
    interaction_manager = InteractionManager(
        provider=provider,
        model_name=model_name,
        tools=tools,
        ui=ui,
    )
    # --- End Initialize Interaction Manager ---

    # --- Initialize and Run Application ---
    app = Application(
        args=args,
        ui=ui,
        cmd_executor=cmd_executor,
        prompt_processor=prompt_processor,
        interaction_manager=interaction_manager,
        working_dir=abs_working_dir,
    )

    # --- Start Application Execution ---
    try:
        app.run()
    except Exception as app_err:
        ui.display_error(f"An critical error occurred: {app_err}")
        logging.critical(
            "Critical error during application execution.", exc_info=app_err
        )
        sys.exit(1)
    # --- End Application Execution ---


if __name__ == "__main__":
    main()
