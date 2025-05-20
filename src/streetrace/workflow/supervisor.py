"""Runs agents and implements the core user<->agent interaction loop."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from google.adk import Runner
from google.adk.agents import Agent, BaseAgent
from google.adk.events import Event
from google.adk.sessions import BaseSessionService, Session
from google.genai import types  # For creating message Content/Parts

from streetrace.args import Args
from streetrace.history import HistoryManager
from streetrace.llm_interface import LlmInterface
from streetrace.prompt_processor import ProcessedPrompt
from streetrace.tools.tool_provider import ToolProvider
from streetrace.ui import ui_events
from streetrace.ui.adk_event_renderer import render_event as _  # noqa: F401
from streetrace.ui.ui_bus import UiBus


class Supervisor:
    """Workflow supervisor manages and executes available workflows."""

    def __init__(  # noqa: PLR0913
        self,
        ui_bus: UiBus,
        llm_interface: LlmInterface,
        tool_provider: ToolProvider,
        history_manager: HistoryManager,
        session_service: BaseSessionService,
        args: Args,
    ) -> None:
        """Initialize a new instance of workflow supervisor.

        Args:
            ui_bus: UI event bus for displaying messages to the user
            llm_interface: Interface to the LLM
            tool_provider: Provider of tools for the agent
            history_manager: Manager of conversation history
            session_service: Service for managing ADK sessions
            args: Application arguments containing session information

        """
        self.ui_bus = ui_bus
        self.llm_interface = llm_interface
        self.session_service = session_service
        self.app_name = args.effective_app_name
        self.session_user_id = args.effective_user_id
        self.session_id = args.effective_session_id
        self.session: Session | None = None
        self.tool_provider = tool_provider
        self.history_manager = history_manager

        if args.list_sessions:
            self._list_available_sessions()

    def _list_available_sessions(self) -> None:
        """List all available sessions for the current user and app."""
        sessions_response = self.session_service.list_sessions(
            app_name=self.app_name,
            user_id=self.session_user_id,
        )

        if not sessions_response.sessions:
            msg = f"No sessions found for app '{self.app_name}' and user '{self.session_user_id}'"
            self.ui_bus.dispatch_ui_update(
                ui_events.Info(msg),
            )
            return

        self.ui_bus.dispatch_ui_update(sessions_response.sessions)

    def get_or_create_session(self) -> Session:
        """Create the ADK agent session with empty state or get existing session."""
        session = self.session_service.get_session(
            app_name=self.app_name,
            user_id=self.session_user_id,
            session_id=self.session_id,
        )
        if not session:
            session = self.session_service.create_session(
                app_name=self.app_name,
                user_id=self.session_user_id,
                session_id=self.session_id,
                state={},  # Initialize state during creation
            )
            context = self.history_manager.system_context.get_project_context()
            context_event = Event(
                author="user",
                content=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="\n".join(context))],
                ),
            )
            self.session_service.append_event(session, context_event)
            session = self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.session_user_id,
                session_id=self.session_id,
            )
            if session is None:
                msg = "session is None"
                raise AssertionError(msg)

        self.session = session
        return session

    @asynccontextmanager
    async def _create_agent(self, agent_type: str) -> AsyncGenerator[BaseAgent, None]:
        """Create an agent of a given type, and identify tools it needs.

        Args:
            agent_type: the agent library name to construct (only 'default' for now).

        Returns:
            An async generator yielding the created agent.

        """
        if agent_type != "default":
            msg = "Only default agent definition is currently supported"
            raise NotImplementedError(msg)

        required_tools = [
            "streetrace:fs_tool::create_directory",
            "streetrace:fs_tool::find_in_files",
            "streetrace:fs_tool::list_directory",
            "streetrace:fs_tool::read_file",
            "streetrace:fs_tool::write_file",
            "streetrace:cli_tool::execute_cli_command",
        ]
        async with self.tool_provider.get_tools(required_tools) as tools:
            root_agent = Agent(
                name="StreetRace",
                model=self.llm_interface.get_adk_llm(),
                description=f"StreetRace - Session: {self.session_id}",
                instruction=self.history_manager.system_context.get_system_message(),
                tools=tools,
            )
            yield root_agent

    async def run_async(self, payload: ProcessedPrompt | None) -> None:
        """Run the payload through the workflow.

        Args:
            payload: Processed user prompt to be sent to the agent.

        This method orchestrates the full interaction cycle between the user and agent:
        1. Prepares the user's message with any attached file contents
        2. Creates a session if needed or retrieves an existing one
        3. Creates an agent with appropriate tools
        4. Runs the agent with the message and captures all events
        5. Extracts the final response and adds it to global history

        """
        parts = []
        if payload:
            if payload.prompt:
                parts.append(types.Part.from_text(text=payload.prompt))
            if payload.mentions:
                for mention in payload.mentions:
                    mention_text = (
                        f"\nAttached file `{mention[0]!s}:\n\n```\n{mention[1]}\n```\n"
                    )
                    parts.append(types.Part.from_text(text=mention_text))

        # Prepare the user's message in ADK format
        content = types.Content(role="user", parts=parts) if parts else None

        final_response_text = "Agent did not produce a final response."  # Default

        event_counter = 0
        session = self.get_or_create_session()
        async with self._create_agent("default") as root_agent:
            runner = Runner(
                app_name=session.app_name,
                session_service=self.session_service,
                agent=root_agent,
            )
            # Key Concept: run_async executes the agent logic and yields Events.
            # We iterate through events to find the final answer.
            async for event in runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=content,  # type: ignore[not-assignable]: wrong declaration in adk
            ):
                self.ui_bus.dispatch_ui_update(event)

                # Check if this is the final response from the agent
                if event.is_final_response():
                    if event.content and event.content.parts:
                        # Assuming text response in the first part
                        final_response_text = event.content.parts[0].text
                    elif (
                        event.actions and event.actions.escalate
                    ):  # Handle potential errors/escalations
                        error_msg = event.error_message or "No specific message."
                        final_response_text = f"Agent escalated: {error_msg}"
                    # Add more checks here if needed (e.g., specific error codes)
                    break  # Stop processing events once the final response is found
                event_counter += 1

        # Add the agent's final message to the history
        if final_response_text:
            history = self.history_manager.get_history()
            if not history:
                msg = "History is not initialized"
                raise ValueError(msg)
            history.add_assistant_message(final_response_text)
