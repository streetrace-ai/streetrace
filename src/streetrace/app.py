"""Orchestrate the StreetRace🚗💨 application flow and manage component interactions.

This module contains the Application class which serves as the central
coordinator for the StreetRace🚗💨 application, handling the interaction between
components and managing the application lifecycle.
"""

# Core application components

from streetrace.agents.agent_manager import AgentManager
from streetrace.app_state import AppState
from streetrace.args import Args
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
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.prompt_processor import PromptProcessor
from streetrace.session_service import JSONSessionService, SessionManager
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
        cmd_executor: CommandExecutor,
        prompt_processor: PromptProcessor,
        session_manager: SessionManager,
        workflow_supervisor: Supervisor,
    ) -> None:
        """Initialize the Application with necessary components and configuration.

        Args:
            args: App args.
            state: App State container.
            ui: ConsoleUI instance for handling user interaction and displaying output.
            ui_bus: UI event bus to exchange messages with the UI.
            cmd_executor: CommandExecutor instance for processing internal commands.
            prompt_processor: PromptProcessor instance for processing prompts and file
                mentions.
            session_manager: SessionManager to manage conversation sessions.
            workflow_supervisor: Supervisor to use for user<->agent interaction
                management.

        """
        if not workflow_supervisor and not args.list_sessions:
            msg = "workflow_supervisor was not created but required."
            raise ValueError(msg)
        self.args = args
        self.ui = ui
        self.ui_bus = ui_bus
        self.cmd_executor = cmd_executor
        self.prompt_processor = prompt_processor
        self.session_manager = session_manager
        self.workflow_supervisor = workflow_supervisor
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
            self.session_manager.display_sessions()
            raise SystemExit

        if self.args.prompt or self.args.arbitrary_prompt:
            await self._run_non_interactive()
        else:
            await self._run_interactive()

    async def _process_input(self, user_input: str) -> None:
        command_status = await self.cmd_executor.execute_async(
            user_input,
        )

        if command_status.command_executed:
            if command_status.error:
                self.ui_bus.dispatch_ui_update(ui_events.Error(command_status.error))
            return

        processed_prompt = None

        # If not a command, process the input as a prompt

        if user_input.strip():
            # Extract mentions from this prompt
            processed_prompt = self.prompt_processor.build_context(user_input)

        # Process with InteractionManager using the persistent history
        await self.workflow_supervisor.run_async(processed_prompt)

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
        self.ui_bus.dispatch_ui_update(
            ui_events.Info(
                "Entering interactive mode. Type '/bye' to exit, '/help' for etc., "
                "or press Ctrl+C/Ctrl+D to quit.",
            ),
        )

        while True:
            try:
                user_input = await self.ui.prompt_async()
                with self.ui.status():
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

    session_service = JSONSessionService(context_dir / "sessions")

    session_manager = SessionManager(
        args=args,
        session_service=session_service,
        system_context=system_context,
        ui_bus=ui_bus,
    )

    # Create model factory
    model_factory = ModelFactory(args.model, ui_bus)

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

    # Initialize the Application
    return Application(
        args=args,
        state=state,
        ui=ui,
        ui_bus=ui_bus,
        cmd_executor=cmd_executor,
        prompt_processor=prompt_processor,
        session_manager=session_manager,
        workflow_supervisor=workflow_supervisor,
    )
