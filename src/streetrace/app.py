"""Orchestrate the StreetRace🚗💨 application flow and manage component interactions.

This module contains the Application class which serves as the central
coordinator for the StreetRace🚗💨 application, handling the interaction between
components and managing the application lifecycle.
"""

# Core application components
from streetrace.args import Args
from streetrace.commands.command_executor import CommandExecutor

# Import specific command classes
from streetrace.commands.definitions import (
    ClearCommand,
    CompactCommand,
    ExitCommand,
    HistoryCommand,
)
from streetrace.history import HistoryManager
from streetrace.llm_interface import LlmInterface, get_llm_interface
from streetrace.log import get_logger
from streetrace.prompt_processor import PromptProcessor
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.ui.completer import CommandCompleter, PathCompleter, PromptCompleter
from streetrace.ui.console_ui import ConsoleUI
from streetrace.workflow.supervisor import Supervisor

logger = get_logger(__name__)

# TODO(krmrn42): replace ApplicationConfig with args.Args
# TODO(krmrn42): rename non_interactive_prompt -> args.prompt
# TODO(krmrn42): rename initial_model -> args.model
# TODO(krmrn42): remove tools (does not belong to config)


async def run_app(args: Args) -> None:
    """Run StreetRace🚗💨."""
    # Initialize CommandExecutor *before* completers that need command list
    cmd_executor = CommandExecutor()

    # Initialize Completers
    path_completer = PathCompleter(args.working_dir)
    command_completer = CommandCompleter(cmd_executor)
    prompt_completer = PromptCompleter([path_completer, command_completer])

    # Initialize ConsoleUI
    ui = ConsoleUI(completer=prompt_completer)

    # Initialize SystemContext for handling system and project context
    system_context = SystemContext(ui=ui, args=args)

    # Initialize PromptProcessor for handling prompts and file mentions
    prompt_processor = PromptProcessor(ui=ui, args=args)

    llm_interface = get_llm_interface(args.model, ui)

    tool_provider = ToolProvider()

    # Initialize Interaction Manager
    workflow_supervisor = Supervisor(
        ui=ui, llm_interface=llm_interface, tool_provider=tool_provider,
    )

    # Initialize HistoryManager
    history_manager = HistoryManager(
        app_args=args,
        ui=ui,
        system_context=system_context,
    )

    # Register commands
    cmd_executor.register(ExitCommand())
    cmd_executor.register(HistoryCommand(ui=ui, history_manager=history_manager))
    cmd_executor.register(CompactCommand(ui=ui, history_manager=history_manager, llm_interface=llm_interface))
    cmd_executor.register(ClearCommand(ui=ui, history_manager=history_manager))

    # Initialize and Run Application
    app = Application(
        args=args,
        ui=ui,
        cmd_executor=cmd_executor,
        prompt_processor=prompt_processor,
        history_manager=history_manager,
        workflow_supervisor=workflow_supervisor,
    )
    await app.run()


class Application:
    """Orchestrates the StreetRace application flow."""

    def __init__(  # noqa: PLR0913 - Many dependencies needed for orchestration
        self,
        args: Args,
        ui: ConsoleUI,
        cmd_executor: CommandExecutor,
        prompt_processor: PromptProcessor,
        history_manager: HistoryManager,
        workflow_supervisor: Supervisor,
    ) -> None:
        """Initialize the Application with necessary components and configuration.

        Args:
            args: App args.
            ui: ConsoleUI instance for handling user interaction and displaying output.
            cmd_executor: CommandExecutor instance for processing internal commands.
            prompt_processor: PromptProcessor instance for processing prompts and file mentions.
            history_manager: HistoryManager instance for managing conversation history.
            workflow_supervisor: Supervisor to use for user<->agent interaction management.

        """
        self.args = args
        self.ui = ui
        self.cmd_executor = cmd_executor
        self.prompt_processor = prompt_processor
        self.history_manager = history_manager
        self.workflow_supervisor = workflow_supervisor
        logger.info("Application initialized.")

    async def run(self) -> None:
        """Start the application execution based on provided arguments."""
        self.history_manager.initialize_history()
        if self.args.prompt:
            await self._run_non_interactive()
        else:
            await self._run_interactive()

    async def _process_input(self, user_input: str) -> None:
        command_status = await self.cmd_executor.execute_async(
            user_input,
        )

        if command_status.command_executed:
            if command_status.error:
                self.ui.display_error(command_status.error)
            return

        processed_prompt = None

        # If not a command, process the input as a prompt
        if user_input.strip():
            # Build context mainly for mentions specific to this input
            processed_prompt = self.prompt_processor.build_context(user_input)

            # Add mentioned files and the user prompt via HistoryManager
            self.history_manager.add_mentions_to_history(
                processed_prompt.mentions,
            )
            self.history_manager.add_user_message(user_input)
            logger.debug(
                "User prompt added to history",
                extra={"user_input": user_input},
            )

        # Process with InteractionManager using the persistent history
        await self.workflow_supervisor.run_async(processed_prompt)

    async def _run_non_interactive(self) -> None:
        """Handle non-interactive mode (single prompt execution)."""
        user_input = self.args.prompt
        # According to coding guide, core components should be fail-fast.
        # Raise if non_interactive_prompt is unexpectedly None.
        if not user_input.strip():
            error_msg = "Non-interactive mode requires a prompt, but none was provided."
            logger.error(error_msg)
            raise ValueError(error_msg)

        self.ui.display_user_prompt(user_input)

        await self._process_input(user_input)

    async def _run_interactive(self) -> None:
        """Handle interactive mode (conversation loop)."""
        self.ui.display_info(
            "Entering interactive mode. Type '/history', '/compact', '/clear', '/exit', or press Ctrl+C/Ctrl+D to quit.",
        )

        while True:
            try:
                user_input = await self.ui.prompt_async()
                await self._process_input(user_input)
            except (EOFError, KeyboardInterrupt, SystemExit):
                self.ui.display_info("\nLeaving...")
                break
            except Exception as loop_err:
                self.ui.display_error(
                    f"\nAn unexpected error while processing input: {loop_err}",
                )
                logger.exception(
                    "Unexpected error in interactive loop.",
                    exc_info=loop_err,
                )
                # Continue loop after displaying error
