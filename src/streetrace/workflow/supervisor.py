"""Runs agents and implements the core user<->agent interaction loop."""

from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from datetime import datetime

from google.adk import Runner
from google.adk.agents import Agent, BaseAgent
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types  # For creating message Content/Parts
from rich.panel import Panel
from tzlocal import get_localzone

from streetrace.app_name import APP_NAME
from streetrace.llm_interface import LlmInterface
from streetrace.prompt_processor import ProcessedPrompt
from streetrace.tools.tool_provider import ToolProvider
from streetrace.ui.console_ui import ConsoleUI
from streetrace.utils.uid import get_user_identity

# TODO(krmrn42): display AI response using Console UI -> Events?
# TODO(krmrn42): usage stats, costs -> Events?
# TODO(krmrn42): persist session state, restore sessions
# TODO(krmrn42): maintain global history for the project


class Supervisor:
    """Workflow supervisor manages and executes available workflows."""

    def __init__(
        self,
        ui: ConsoleUI,
        llm_interface: LlmInterface,
        tool_provider: ToolProvider,
    ) -> None:
        """Initialize a new instance of workflow supervisor."""
        self.ui = ui
        self.llm_interface = llm_interface
        self.session_service = InMemorySessionService()
        self.session_id = datetime.now(tz=get_localzone()).strftime("%Y-%m-%d_%H-%M")
        self.session_user_id = get_user_identity()
        self.session: Session = None
        self.tool_provider = tool_provider

    def get_or_create_session(self) -> Session:
        """Create the ADK agent session with empty state."""
        session = self.session_service.get_session(
            app_name=APP_NAME, user_id=self.session_user_id, session_id=self.session_id,
        )
        if not session:
            session = self.session_service.create_session(
                app_name=APP_NAME,  # Use the consistent app name
                user_id=self.session_user_id,
                session_id=self.session_id,
                state={},  # <<< Initialize state during creation
            )
        self.session = session
        return session

    @asynccontextmanager
    async def _create_agent(self, agent_type: str) -> AsyncGenerator[BaseAgent, None]:
        """Create an agent of a given type, and identify tools it needs.

        Args:
            agent_type: the agent library name to construct (only 'default' for now).

        Returns:
            tuple[BaseAgent, list[str]]:
                - BaseAgent: Root MCP agent.
                - list[str]: List of required tool references (e.g., server_name::tool_name).

        """
        if agent_type != "default":
            msg = "Only default agent definition is currently supported"
            raise NotImplementedError(msg)

        required_tools = ["get_weather", "get_current_time"]
        async with self.tool_provider.get_tools(required_tools) as tools:
            root_agent = Agent(
                name="weather_time_agent",
                model=self.llm_interface.llm,
                description=(
                    "Agent to answer questions about the time and weather in a city."
                ),
                instruction=(
                    "You are a helpful agent who can answer user questions about the time and weather in a city."
                ),
                tools=tools,
            )
            yield root_agent

    async def run_async(self, payload: ProcessedPrompt | None) -> None:
        """Run the payload choosing the right workflow.

        run_async called to start one full turn, so it starts from
        user's message (or other initiation event)

        The result of one turn is:
            - turn history of all messages (agent tree?..)
            - changes made by all agents

        Agents cannot make changes simultaneously, because we are working on a single
        external state (e.g., modifying local fiels).

        messages from agents and tools need to land in the global history that acts as a
        "long term memory", BUT instead of storing all messages exhausting the context window,
        we can introduce events, and each agent implementation will invoke the even letting us
        know that a certain message needs to be saved. So an agent can choose to
        auto-summarize before persisting in the "long term memory".

        Since we are using ADK, we could use it's own BaseSessionService as the persistent
        history. Problem with it is that session state needs to contain everything happening
        in the session, while the global history only needs conversational summaries. With that,
        we could use the global history as a historical KB of what's going on in the project.

        The general architecture can be:
        - streetrace will start from a blank or existing BaseSessionService
        - streetrace will maintain a global history of all conversations on a working directory
            basis. I.e., all facts will be stored in one place, independently of which session
            they belong to.
        - we'll need to experiment with how teams of agents store data in sessions. I.e., we
            don't want a sub-agent to just flush it's entire history into the root agent's
            state.
        - we don't need a workflow router for now, the root agent is our router.
        """
        self.ui.display_info(f"Payload: {payload}")

        parts = []
        if payload:
            if payload.prompt:
                parts.append(types.Part(text=payload.prompt))
            if payload.mentions:
                parts.extend([
                    types.Part.from_text(f"\nAttached file `{mention[0]!s}:\n\n```\n{mention[1]}\n```\n")
                    for mention in payload.mentions
                ])

        # Prepare the user's message in ADK format
        content = types.Content(role="user", parts=parts)

        final_response_text = "Agent did not produce a final response."  # Default

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
                user_id=session.user_id, session_id=session.id, new_message=content,
            ):
                # You can uncomment the line below to see *all* events during execution
                self.ui.display(Supervisor._render_event(event))

                # Key Concept: is_final_response() marks the concluding message for the turn.
                if event.is_final_response():
                    if event.content and event.content.parts:
                        # Assuming text response in the first part
                        final_response_text = event.content.parts[0].text
                    elif (
                        event.actions and event.actions.escalate
                    ):  # Handle potential errors/escalations
                        final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
                    # Add more checks here if needed (e.g., specific error codes)
                    break  # Stop processing events once the final response is found

        self.ui.display_info(final_response_text)

        return final_response_text

        # https://google.github.io/adk-docs/runtime/#how-it-works-a-simplified-invocation
        # how do multiple agents work? https://google.github.io/adk-docs/agents/multi-agents/
        # how to use session state? https://google.github.io/adk-docs/sessions/
        #
        # agent.output_key: The key in session state to store the output of the agent.
        # Typically use cases:
        # - Extracts agent reply for later use, such as in tools, callbacks, etc.
        # - Connects agents to coordinate with each other.
        # - output_key (Auto-Save Agent Response): An Agent can be configured with
        #   an output_key="your_key". ADK will then automatically save the agent's
        #   final textual response for a turn into session.state["your_key"].
        #
        # agent.planner: Instructs the agent to make a plan and execute it step by step.
        # NOTE: to use model's built-in thinking features, set the `thinking_config`
        # field in `google.adk.planners.built_in_planner`.
        #
        # code_executor: Allow agent to execute code blocks from model responses using the provided
        # CodeExecutor.
        # Check out available code executions in `google.adk.code_executor` package.
        # NOTE: to use model's built-in code executor, don't set this field, add
        # `google.adk.tools.built_in_code_execution` to tools instead.

    @staticmethod
    def _render_event(event: Event) -> Panel:

        role = "role unknown"
        if event.content and event.content.role:
            role = event.content.role
        lines = [
            f"[bold]{event.author} ({role}):[/bold] ",
        ]
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    lines.append(f"↳ {part.text}")

                if part.function_call:
                    fn = part.function_call
                    lines.append(
                        f"[bold cyan]↳ Call:[/bold cyan] {fn.name}({fn.args})",
                    )

                if part.function_response:
                    fn = part.function_response
                    lines.append(
                        f"[bold cyan]↳ {fn.name}[/bold cyan]:",
                    )
                    lines.extend([
                        f"  ↳ [grey]{key}[/grey]: {fn.response[key]}"
                        for key in fn.response
                    ])

        return Panel("\n".join(lines), title="Event Summary")
