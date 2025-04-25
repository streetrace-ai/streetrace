# main.py
import argparse
import logging
import os
import sys

# Core application components
from streetrace.application import Application
from streetrace.commands.command_executor import CommandExecutor

# Import specific command classes
from streetrace.commands.definitions import (
    ClearCommand,  # Added ClearCommand
    CompactCommand,
    ExitCommand,
    HistoryCommand,
)

# Completer imports
from streetrace.completer import CommandCompleter, PathCompleter, PromptCompleter
from streetrace.interaction_manager import InteractionManager
from streetrace.llm.llmapi_factory import get_ai_provider
from streetrace.prompt_processor import PromptProcessor
from streetrace.tools.fs_tool import TOOL_IMPL, TOOLS
from streetrace.tools.tools import ToolCall
from streetrace.ui.console_ui import ConsoleUI

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
        description="Run AI assistant with different models",
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
        "--debug",
        action="store_true",
        help="Enable debug logging to console and file.",
    )
    return parser.parse_args()


def init_working_directory(args_path: str) -> str:
    """Initializes and validates the working directory."""
    initial_cwd = os.getcwd()
    target_work_dir = args_path if args_path else initial_cwd
    abs_working_dir = os.path.abspath(target_work_dir)

    if not os.path.isdir(abs_working_dir):
        msg = f"Specified path '{target_work_dir}' resolved to '{abs_working_dir}' which is not a valid directory."
        raise ValueError(
            msg,
        )

    if abs_working_dir != initial_cwd:
        try:
            os.chdir(abs_working_dir)
            logging.info(f"Changed working directory to: {abs_working_dir}")
        except OSError as e:
            msg = f"Could not change working directory to '{abs_working_dir}': {e}"
            raise OSError(
                msg,
            ) from e

    return abs_working_dir


def main() -> None:
    """Main entry point for the application."""
    args = parse_arguments()

    # Configure Logging Level based on args
    if args.debug:
        # Add console handler only if debug is enabled
        console_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(console_handler)
        logging.info("Debug logging enabled for console.")

    try:
        abs_working_dir = init_working_directory(args.path)
        logging.info(f"Effective working directory: {abs_working_dir}")
    except (ValueError, OSError) as e:
        logging.critical(f"Working directory initialization failed: {e}")
        raise

    # Initialize CommandExecutor *before* completers that need command list
    cmd_executor = CommandExecutor()

    # Instantiate and register commands
    cmd_executor.register(ExitCommand())
    cmd_executor.register(HistoryCommand())
    cmd_executor.register(CompactCommand())
    cmd_executor.register(ClearCommand())  # Register ClearCommand
    # Add more command registrations here as needed

    # Get the list of command names *with* the prefix for the completer
    available_commands = cmd_executor.get_command_names_with_prefix()

    # Initialize Completers
    path_completer = PathCompleter(abs_working_dir)
    command_completer = CommandCompleter(available_commands)
    prompt_completer = PromptCompleter([path_completer, command_completer])

    # Initialize ConsoleUI
    ui = ConsoleUI(completer=prompt_completer, debug_enabled=args.debug)
    ui.display_info(f"Working directory: {abs_working_dir}")

    # Initialize other Core Application Components
    prompt_processor = PromptProcessor(ui=ui)

    # Determine Model and Provider
    model_name = args.model.strip().lower() if args.model else None
    provider_name = args.engine.strip().lower() if args.engine else None

    # Initialize AI Provider
    try:
        provider = get_ai_provider(provider_name)
        if not provider:
            msg = f"Provider '{provider_name or 'default'}' could not be loaded."
            raise ValueError(
                msg,
            )
        ui.display_info(
            f"Using provider: {type(provider).__name__.replace('Provider', '')}",
        )
        if model_name:
            ui.display_info(f"Using model: {model_name}")
        else:
            ui.display_info("Using default model for the provider.")
    except Exception as e:
        ui.display_error(f"Could not initialize AI provider: {e}")
        logging.critical(f"Failed to initialize AI provider: {e}", exc_info=True)
        sys.exit(1)

    # Tool Calling Setup
    tools = ToolCall(TOOLS, TOOL_IMPL, abs_working_dir)

    # Initialize Interaction Manager
    interaction_manager = InteractionManager(
        provider=provider,
        model_name=model_name,
        tools=tools,
        ui=ui,
    )

    # Initialize and Run Application
    app = Application(
        args=args,
        ui=ui,
        cmd_executor=cmd_executor,
        prompt_processor=prompt_processor,
        interaction_manager=interaction_manager,
        working_dir=abs_working_dir,
    )

    # Start Application Execution
    try:
        app.run()
    except Exception as app_err:
        ui.display_error(f"An critical error occurred: {app_err}")
        logging.critical(
            "Critical error during application execution.",
            exc_info=app_err,
        )
        sys.exit(1)
    finally:
        logging.info("Application exiting.")


if __name__ == "__main__":
    main()
