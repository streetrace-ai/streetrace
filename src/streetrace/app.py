"""Orchestrate the StreetRace🚗💨 application flow and manage component interactions.

This module contains the Application class which serves as the central
coordinator for the StreetRace🚗💨 application, handling the interaction between
components and managing the application lifecycle.
"""

# Core application components

import asyncio

from streetrace.agents.agent_manager import AgentManager
from streetrace.app_state import AppState
from streetrace.args import Args
from streetrace.bash_handler import BashHandler
from streetrace.commands.command_executor import CommandExecutor

# Import specific command classes
from streetrace.commands.definitions import (
    CompactCommand,
    ExitCommand,
    HelpCommand,
    HistoryCommand,
    ResetSessionCommand,
)
from streetrace.costs import UsageAndCost
from streetrace.input_handler import InputContext, InputHandler
from streetrace.list_agents import list_available_agents
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger, lazy_setup_litellm_logging
from streetrace.preload_deps import preload_dependencies
from streetrace.prompt_processor import PromptProcessor
from streetrace.session.session_manager import SessionManager
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.ui import ui_events
from streetrace.ui.completer import CommandCompleter, PathCompleter, PromptCompleter
from streetrace.ui.console_ui import ConsoleUI
from streetrace.ui.ui_bus import UiBus
from streetrace.workflow.supervisor import Supervisor

logger = get_logger(__name__)

CONTEXT_DIR = ".streetrace"


class Application:
    """Orchestrates the StreetRace application flow."""

    def __init__(  # noqa: PLR0913 - Many dependencies needed for orchestration
        self,
        args: Args,
        state: AppState,
        ui: ConsoleUI,
        ui_bus: UiBus,
        input_handling_pipeline: list[InputHandler],
        session_manager: "SessionManager",
    ) -> None:
        """Initialize the Application with necessary components and configuration.

        Args:
            args: App args.
            state: App State container.
            ui: ConsoleUI instance for handling user interaction and displaying output.
            ui_bus: UI event bus to exchange messages with the UI.
            input_handling_pipeline: Pipeline of input handlers.
            session_manager: SessionManager to manage conversation sessions.

        """
        self.args = args
        self.ui = ui
        self.ui_bus = ui_bus
        self.input_handling_pipeline = input_handling_pipeline
        self.session_manager = session_manager
        self.ui_bus.on_usage_data(self._on_usage_data)
        self.state = state
        logger.info("Application initialized.")

    def _on_usage_data(self, usage: UsageAndCost) -> None:
        self.state.usage_and_cost.add_usage(usage)
        self.update_state()

    def update_state(self) -> None:
        """Push app state updates.

        In leu of more versatile state management solution.
        """
        self.ui.update_state()

    async def run(self) -> None:
        """Start the application execution based on provided arguments."""
        # If only listing sessions, we don't need to run the input loop
        if self.args.list_sessions:
            await self.session_manager.display_sessions()
            raise SystemExit

        if self.args.prompt or self.args.arbitrary_prompt:
            await self._run_non_interactive()
        else:
            await self._run_interactive()

    async def _process_input(self, user_input: str) -> None:
        lazy_setup_litellm_logging()
        ctx: InputContext = InputContext(
            user_input=user_input,
            agent_name=self.args.agent,
        )
        for handler in self.input_handling_pipeline:
            if handler.long_running:
                with self.ui.status():
                    result = await handler.handle(ctx)
            else:
                result = await handler.handle(ctx)
            if result.handled:
                logger.debug("Input handled by %s", handler.__class__.__name__)
            if ctx.error:
                logger.error(
                    "%s error (will continue = %s): %s",
                    handler.__class__.__name__,
                    result.continue_,
                    ctx.error,
                )
                self.ui_bus.dispatch_ui_update(ui_events.Error(ctx.error))
                ctx.error = None
            if not result.continue_:
                return

    async def _run_non_interactive(self) -> None:
        """Handle non-interactive mode (single prompt execution)."""
        # According to coding guide, core components should be fail-fast.
        # Raise if non_interactive_prompt is unexpectedly None.
        return_code = 0
        try:
            user_input, confirm_with_user = self.args.non_interactive_prompt
            if not user_input or not user_input.strip():
                error_msg = (
                    "Non-interactive mode requires a prompt, but none was provided."
                )
                logger.error(error_msg)
                self.ui_bus.dispatch_ui_update(ui_events.Error(error_msg))
                return_code = 1
                return

            self.ui_bus.dispatch_ui_update(ui_events.UserInput(user_input))
            if confirm_with_user:
                confirmation = self.ui.confirm_with_user(
                    ":stop_sign: continue? ([underline]YES[/underline]/no) ",
                )
                if confirmation.lower() not in ["yes", "y"]:
                    return

            await self._process_input(user_input)
        except Exception as err:
            # in non-interactive we always leave the app when done or err.
            self.ui_bus.dispatch_ui_update(ui_events.Error(str(err)))
            raise SystemExit(1) from err
        finally:
            raise SystemExit(return_code)

    async def _run_interactive(self) -> None:
        """Handle interactive mode (conversation loop)."""
        splash = f"""
🏁 Welcome to [bold]StreetRace[/bold] 🚗💨

Quick commands:

    • /exit, /quit, /bye    → Exit the interactive session
    • /history              → Show conversation history
    • /compact              → Summarize and compact history
    • /reset                → Start a new conversation
    • /help, /h             → List all available commands

[dim][white]CWD: {self.args.working_dir}[/white][/dim]

Enjoy the ride! 🏁
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            """
        self.ui_bus.dispatch_ui_update(ui_events.Info(splash))

        while True:
            try:
                preload_task = asyncio.create_task(preload_dependencies())
                user_input = await self.ui.prompt_async()
                await preload_task  # Ensure dependencies are preloaded
                await self._process_input(user_input)
            except (EOFError, SystemExit):
                self.ui_bus.dispatch_ui_update(ui_events.Info("\nLeaving..."))
                raise
            except Exception as loop_err:
                self.ui_bus.dispatch_ui_update(
                    ui_events.Error(
                        f"\nAn unexpected error while processing input: {loop_err}",
                    ),
                )
                logger.exception(
                    "Unexpected error in interactive loop.",
                    exc_info=loop_err,
                )
                # Continue loop after displaying error


def create_app(args: Args) -> Application:
    """Run StreetRace🚗💨."""
    state = AppState(current_model=args.model)

    ui_bus = UiBus()

    ui_bus.dispatch_ui_update(ui_events.Info(f"Starting in {args.working_dir}"))

    # Initialize CommandExecutor *before* completers that need command list
    cmd_executor = CommandExecutor()

    # Initialize Completers
    path_completer = PathCompleter(args.working_dir)
    command_completer = CommandCompleter(cmd_executor)
    prompt_completer = PromptCompleter([path_completer, command_completer])

    # Initialize ConsoleUI as soon as possible, so we can start showing something
    ui = ConsoleUI(app_state=state, completer=prompt_completer, ui_bus=ui_bus)

    context_dir = args.working_dir / CONTEXT_DIR

    # Initialize SystemContext for handling system and project context
    system_context = SystemContext(ui_bus=ui_bus, context_dir=context_dir)

    # Initialize PromptProcessor for handling prompts and file mentions
    prompt_processor = PromptProcessor(ui_bus=ui_bus, args=args)

    tool_provider = ToolProvider(args.working_dir)

    session_manager = SessionManager(
        args=args,
        system_context=system_context,
        ui_bus=ui_bus,
    )

    # Create model factory
    model_factory = ModelFactory(args.model, ui_bus, args)

    # Create agent manager
    agent_manager = AgentManager(
        model_factory,
        tool_provider,
        system_context,
        args.working_dir,
    )

    # Initialize Workflow Supervisor, passing the args
    workflow_supervisor = Supervisor(
        agent_manager=agent_manager,
        session_manager=session_manager,
        ui_bus=ui_bus,
    )

    # Register commands
    cmd_executor.register(ExitCommand())
    cmd_executor.register(
        HistoryCommand(
            ui_bus=ui_bus,
            system_context=system_context,
            session_manager=session_manager,
        ),
    )
    cmd_executor.register(
        CompactCommand(
            ui_bus=ui_bus,
            args=args,
            session_manager=session_manager,
            system_context=system_context,
            model_factory=model_factory,
        ),
    )
    cmd_executor.register(
        ResetSessionCommand(ui_bus=ui_bus, session_manager=session_manager),
    )
    cmd_executor.register(
        HelpCommand(ui_bus=ui_bus, cmd_executor=cmd_executor),
    )

    input_handling_pipeline = [
        cmd_executor,
        BashHandler(work_dir=args.working_dir),
        prompt_processor,
        workflow_supervisor,
    ]

    if args.list_agents:
        list_available_agents(agent_manager, ui_bus)
        raise SystemExit

    # Initialize the Application
    return Application(
        args=args,
        state=state,
        ui=ui,
        ui_bus=ui_bus,
        input_handling_pipeline=input_handling_pipeline,
        session_manager=session_manager,
    )
