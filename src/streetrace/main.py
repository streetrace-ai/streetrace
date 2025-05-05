"""StreetRace🚗💨 CLI entry point."""

import argparse
import logging
import sys
from pathlib import Path

import litellm

# Core application components
from streetrace.application import Application, ApplicationConfig
from streetrace.commands.command_executor import CommandExecutor

# Import specific command classes
from streetrace.commands.definitions import (
    ClearCommand,
    CompactCommand,
    ExitCommand,
    HistoryCommand,
)
from streetrace.completer import CommandCompleter, PathCompleter, PromptCompleter
from streetrace.history_manager import HistoryManager
from streetrace.interaction_manager import InteractionManager
from streetrace.prompt_processor import PromptProcessor
from streetrace.system_context import SystemContext
from streetrace.tools.fs_tool import TOOL_IMPL, TOOLS
from streetrace.tools.tools import ToolCall
from streetrace.ui.console_ui import ConsoleUI

litellm.suppress_debug_info = True

# --- Logging Configuration ---
# Basic config for file logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="streetrace.log",
    filemode="w",
)

# Console handler for user-facing logs
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(levelname)s: %(message)s")
console_handler.setFormatter(console_formatter)


def configure_3p_loggers() -> None:
    """Configure the litellm logger to use the same handlers as the root logger."""
    for name in logging.root.manager.loggerDict:
        if name.startswith("streetrace"):
            continue  # Skip our own loggers
        # Disable console output for a specific third-party logger
        third_party_logger = logging.getLogger(
            name,
        )  # Replace with the actual logger name
        third_party_logger.handlers.clear()  # Remove any existing handlers


configure_3p_loggers()

# Root logger setup
root_logger = logging.getLogger()
# Set root logger level to DEBUG initially to capture everything
root_logger.setLevel(logging.DEBUG)
# --- End Logging Configuration ---

logger = logging.getLogger(__name__)

_CONTEXT_DIR = ".streetrace"


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run AI assistant with different models",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["anthropic", "gemini", "ollama", "openai"],
        help="Choose AI provider (anthropic, gemini, ollama, or openai)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Specific model name to use (e.g., anthropic-3-opus-20240229, gemini-1.5-flash, llama3:8b, or gpt-4o)",
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


def init_working_directory(args_path: str) -> Path:
    """Initialize and validate the working directory."""
    if args_path:
        work_dir = Path(args_path)
        if not work_dir.is_absolute():
            work_dir = Path.cwd().joinpath(work_dir).resolve()
    else:
        work_dir = Path.cwd().resolve()

    if not work_dir.is_dir():
        msg = f"Specified path '{args_path}' resolved to '{work_dir}' which is not a valid directory."
        raise ValueError(
            msg,
        )

    return work_dir


def main() -> None:
    """Run StreetRace🚗💨."""
    args = parse_arguments()

    # Configure Logging Level based on args
    if args.debug:
        # Add console handler only if debug is enabled
        console_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(console_handler)
        logger.info("Debug logging enabled for console.")

    try:
        abs_working_dir = init_working_directory(args.path)
        logger.info("Effective working directory: %s", abs_working_dir)
    except (ValueError, OSError):
        logger.exception("Working directory initialization failed")
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
    ui = ConsoleUI(completer=prompt_completer)

    # Initialize Core Application Components
    config_dir = abs_working_dir / _CONTEXT_DIR

    # Initialize SystemContext for handling system and project context
    system_context = SystemContext(ui=ui, config_dir=config_dir)

    # Initialize PromptProcessor for handling prompts and file mentions
    prompt_processor = PromptProcessor(ui=ui)

    # Determine Model and Provider
    model_name = args.model.strip().lower() if args.model else None

    # Tool Calling Setup
    tools = ToolCall(TOOLS, TOOL_IMPL, abs_working_dir)

    # Initialize Interaction Manager
    interaction_manager = InteractionManager(
        ui=ui,
    )

    # Create ApplicationConfig (needed for HistoryManager)
    app_config = ApplicationConfig(
        working_dir=abs_working_dir,
        non_interactive_prompt=args.prompt,
        initial_model=model_name,
        tools=tools,
    )

    # Initialize HistoryManager
    history_manager = HistoryManager(
        app_config=app_config,
        ui=ui,
        prompt_processor=prompt_processor,
        system_context=system_context,
        interaction_manager=interaction_manager,
    )

    # Initialize and Run Application
    app = Application(
        app_config=app_config,
        ui=ui,
        cmd_executor=cmd_executor,
        prompt_processor=prompt_processor,
        system_context=system_context,
        interaction_manager=interaction_manager,
        history_manager=history_manager,
    )

    # Start Application Execution
    try:
        app.run()
    except Exception as app_err:
        msg = f"Critical error during application execution: {app_err}"
        ui.display_error(msg)
        logger.exception(msg)
        sys.exit(1)
    finally:
        logger.info("Application exiting.")


if __name__ == "__main__":
    main()
