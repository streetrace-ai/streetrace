"""Base workflow class for Streetrace DSL.

Provide the base class that all generated workflows extend.
This class implements the Workload protocol for unified execution.
"""

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from streetrace.dsl.runtime.context import WorkflowContext
from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content
    from pydantic import BaseModel

    from streetrace.dsl.runtime.events import FlowEvent
    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.dsl_agent_factory import DslAgentFactory

logger = get_logger(__name__)


def _try_parse_json(value: object) -> object:
    """Try to parse a string value as JSON.

    Agent results are often JSON-formatted text. Parse them into
    native Python objects (lists, dicts) so flow code can operate
    on structured data. Return the original value if parsing fails.

    Args:
        value: Value to try parsing.

    Returns:
        Parsed JSON object, or original value if not JSON.

    """
    if not isinstance(value, str):
        return value
    import json

    # Strip markdown code fences if present (opening + content + closing)
    min_fenced_lines = 3
    text = value.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) >= min_fenced_lines and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return value


@dataclass
class EscalationSpec:
    """Escalation specification for prompt outputs.

    Define the condition under which a prompt's output triggers escalation.
    Used with PromptSpec to specify when an agent should escalate.
    """

    op: str
    """Comparison operator: '~', '==', '!=', 'contains'."""

    value: str
    """Value to compare against."""


@dataclass
class PromptSpec:
    """Prompt specification with optional schema and escalation.

    Wrap a prompt body lambda with optional model, schema, and escalation
    configuration. This allows prompts to define expected output structure
    and when their output should trigger escalation.
    """

    body: Callable[[object], str]
    """Lambda that takes context and returns the prompt text."""

    model: str | None = None
    """Optional model name for this prompt."""

    schema: str | None = None
    """Optional schema name for structured output validation."""

    escalation: EscalationSpec | None = None
    """Optional escalation condition."""


@dataclass
class EntryPoint:
    """Represent an entry point for workflow execution."""

    type: str
    """Entry point type: 'flow' or 'agent'."""

    name: str
    """Name of the flow or agent."""


class DslAgentWorkflow:
    """Base class for generated DSL workflows.

    Generated workflows extend this class and override
    the class attributes and event handler methods.

    This class implements the Workload protocol for unified execution
    and uses composition to delegate agent creation to DslAgentFactory.

    All runtime dependencies are provided via constructor. Generated subclasses
    must NOT override __init__ - they only define class attributes and methods.
    """

    _models: ClassVar[dict[str, str]] = {}
    """Model definitions for this workflow."""

    _schemas: ClassVar[dict[str, "type[BaseModel]"]] = {}
    """Schema definitions for this workflow as Pydantic models."""

    _prompts: ClassVar[dict[str, object]] = {}
    """Prompt definitions for this workflow."""

    _tools: ClassVar[dict[str, dict[str, object]]] = {}
    """Tool definitions for this workflow."""

    _agents: ClassVar[dict[str, dict[str, object]]] = {}
    """Agent definitions for this workflow."""

    def __init__(
        self,
        *,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
        agent_factory: "DslAgentFactory | None" = None,
    ) -> None:
        """Initialize the workflow with all required dependencies.

        Args:
            model_factory: Factory for creating LLM models.
            tool_provider: Provider for tools.
            system_context: System context.
            session_service: Session service for Runner.
            agent_factory: DslAgentFactory for agent creation.

        """
        self._model_factory = model_factory
        self._tool_provider = tool_provider
        self._system_context = system_context
        self._session_service = session_service
        self._agent_factory = agent_factory
        self._context: WorkflowContext | None = None
        self._created_agents: list[BaseAgent] = []

        logger.debug("Created %s", self.__class__.__name__)

    def _determine_entry_point(self) -> EntryPoint:
        """Determine the entry point for workflow execution.

        Priority:
        1. 'main' flow if defined
        2. 'default' flow if defined
        3. 'default' agent if defined

        Returns:
            EntryPoint with type and name.

        Raises:
            ValueError: If no entry point found.

        """
        # Check for main flow
        flow_main = getattr(self, "flow_main", None)
        if flow_main is not None and callable(flow_main):
            return EntryPoint(type="flow", name="main")

        # Check for default flow
        flow_default = getattr(self, "flow_default", None)
        if flow_default is not None and callable(flow_default):
            return EntryPoint(type="flow", name="default")

        # Check for main agent
        if "main" in self._agents:
            return EntryPoint(type="agent", name="main")

        # Check for default agent
        if "default" in self._agents:
            return EntryPoint(type="agent", name="default")

        # Check for default agent
        if len(self._agents) == 1:
            agent_name = next(iter(self._agents.keys()))
            return EntryPoint(type="agent", name=agent_name)

        # If main/default flow and default agent not found, we can't run
        # anything as it introduces ambiguity.

        msg = "No entry point found in workflow"
        raise ValueError(msg)

    async def _create_agent(self, agent_name: str) -> "BaseAgent":
        """Create fully-configured ADK agent from DSL definition.

        Delegate to DslAgentFactory for agent creation.

        Args:
            agent_name: Name of the agent to create.

        Returns:
            Created ADK BaseAgent.

        Raises:
            ValueError: If agent_factory is not set.

        """
        if not self._agent_factory:
            msg = "DslAgentWorkflow requires agent_factory"
            raise ValueError(msg)

        agent = await self._agent_factory.create_agent(
            agent_name=agent_name,
            model_factory=self._model_factory,
            tool_provider=self._tool_provider,
            system_context=self._system_context,
        )
        self._created_agents.append(agent)
        return agent

    async def _execute_agent(
        self,
        agent_name: str,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Execute an agent and yield events.

        Args:
            agent_name: Name of the agent to execute.
            session: ADK session for conversation persistence.
            message: User message to process.

        Yields:
            ADK events from execution.

        """
        from google.adk import Runner

        agent = await self._create_agent(agent_name)

        # Use the provided session service
        if not self._session_service:
            msg = "Session service not available for agent execution"
            raise ValueError(msg)

        runner = Runner(
            app_name=session.app_name,
            session_service=self._session_service,
            agent=agent,
        )

        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=message,
        ):
            yield event

    def _extract_message_text(self, message: "Content | None") -> str:
        """Extract text content from a message.

        Args:
            message: User message content, or None.

        Returns:
            The text content of the message, or empty string if None.

        """
        if message is None:
            return ""
        if message.parts:
            # Concatenate text from all parts
            texts = [
                part.text
                for part in message.parts
                if hasattr(part, "text") and part.text
            ]
            return " ".join(texts)
        return ""

    async def _execute_flow(
        self,
        flow_name: str,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event | FlowEvent", None]:
        """Execute a flow, yielding events.

        Args:
            flow_name: Name of the flow to execute.
            session: ADK session (reserved for future event forwarding).
            message: User message to process.

        Yields:
            Events from all operations within the flow.

        """
        # Reserved for future event forwarding (Option 2/3 in design doc)
        _ = session

        flow_method = getattr(self, f"flow_{flow_name}", None)
        if flow_method is None:
            msg = f"Flow '{flow_name}' not found"
            raise ValueError(msg)

        # Extract user input and create context with built-in variables
        input_text = self._extract_message_text(message)
        ctx = self.create_context(input_prompt=input_text)

        # Flow method is now a generator - iterate and yield events
        async for event in flow_method(ctx):
            yield event

        # Yield flow result if return statement was executed
        if "_return_value" in ctx.vars:
            from streetrace.dsl.runtime.events import FlowResultEvent

            yield FlowResultEvent(result=ctx.vars["_return_value"])

    async def run_async(
        self,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event | FlowEvent", None]:
        """Execute the workload based on DSL definition.

        Entry point selection:
        1. If DSL defines a 'main' flow -> run_flow('main')
        2. Else if DSL defines a 'default' agent -> run_agent('default')
        3. Else run first defined agent

        Args:
            session: ADK session for conversation persistence.
            message: User message to process.

        Yields:
            Events from execution (ADK events or FlowEvents).

        """
        entry_point = self._determine_entry_point()

        if entry_point.type == "flow":
            async for event in self._execute_flow(entry_point.name, session, message):
                yield event
        else:
            async for event in self._execute_agent(entry_point.name, session, message):
                yield event

    async def run_agent(
        self,
        agent_name: str,
        *args: object,
    ) -> AsyncGenerator["Event", None]:
        """Run an agent from within a flow, yielding events.

        Called by generated flow code via ctx.run_agent().
        Uses _create_agent() which delegates to DslAgentFactory.

        Args:
            agent_name: Name of the agent to run.
            *args: Arguments to pass to the agent.

        Yields:
            ADK events from agent execution.

        Raises:
            ValueError: If agent_factory not set.

        """
        from google.adk import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types

        agent = await self._create_agent(agent_name)

        # Build prompt from args
        prompt_text = "\n---\n".join(str(arg) for arg in args) if args else ""
        content = None
        if prompt_text:
            parts = [genai_types.Part.from_text(text=prompt_text)]
            content = genai_types.Content(role="user", parts=parts)

        # Use InMemorySessionService for nested runs (isolated context)
        nested_session_service = InMemorySessionService()  # type: ignore[no-untyped-call]

        # Create session before running (InMemorySessionService requires this)
        await nested_session_service.create_session(
            app_name="dsl_workflow",
            user_id="workflow_user",
            session_id="nested_session",
            state={},
        )

        runner = Runner(
            app_name="dsl_workflow",
            session_service=nested_session_service,
            agent=agent,
        )

        final_response: object = None
        async for event in runner.run_async(
            user_id="workflow_user",
            session_id="nested_session",
            new_message=content,
        ):
            yield event  # Forward event to caller
            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text

        # Store result for context retrieval
        if self._context:
            self._context._last_call_result = _try_parse_json(  # noqa: SLF001
                final_response,
            )

    async def run_flow(
        self,
        flow_name: str,
        *args: object,
        caller_ctx: "WorkflowContext | None" = None,
    ) -> AsyncGenerator["Event | FlowEvent", None]:
        """Run a flow from within another flow, yielding events.

        Sub-flows share the caller's variable scope so they can access
        and modify variables set by the parent flow.

        Args:
            flow_name: Name of the flow to run.
            *args: Arguments to pass to the flow.
            caller_ctx: Parent context to share. Creates a new one if None.

        Yields:
            Events from flow execution.

        Raises:
            ValueError: If flow not found.

        """
        _ = args  # Available for future use
        flow_method = getattr(self, f"flow_{flow_name}", None)
        if flow_method is None:
            msg = f"Flow '{flow_name}' not found"
            raise ValueError(msg)

        ctx = caller_ctx if caller_ctx is not None else self.create_context()
        async for event in flow_method(ctx):
            yield event

    async def _execute_parallel_agents(
        self,
        ctx: WorkflowContext,
        specs: list[tuple[str, list[object], str | None]],
    ) -> AsyncGenerator["Event", None]:
        """Execute multiple agents in parallel using ADK ParallelAgent.

        Create sub-agents with output_key for result storage in session state,
        wrap them in a ParallelAgent, and execute using Runner. Events are
        yielded as they occur, and results are stored directly in ctx.vars.

        The order of events and results from parallel execution is non-deterministic.

        Args:
            ctx: Workflow context for variable access and result storage.
            specs: List of (agent_name, args, target_var) tuples. The target_var
                may be None if no result assignment is needed.

        Yields:
            ADK events from parallel agent execution.

        """
        from google.adk import Runner
        from google.adk.agents import ParallelAgent
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types

        if not specs:
            return

        if not self._agent_factory:
            msg = "DslAgentWorkflow requires agent_factory for parallel execution"
            raise ValueError(msg)

        # Create sub-agents with output_keys for result storage
        sub_agents = []
        output_key_mapping: dict[str, str] = {}  # target_var -> output_key

        for agent_name, _, target_var in specs:
            # Generate unique output_key for session state storage
            output_key = f"_parallel_{agent_name}_{id(specs)}"
            if target_var is not None:
                output_key_mapping[target_var] = output_key

            agent = await self._agent_factory.create_agent(
                agent_name=agent_name,
                model_factory=self._model_factory,
                tool_provider=self._tool_provider,
                system_context=self._system_context,
                output_key=output_key,
            )
            sub_agents.append(agent)

        # Create ParallelAgent to orchestrate concurrent execution
        parallel_agent = ParallelAgent(
            name=f"parallel_block_{id(specs)}",
            sub_agents=sub_agents,
        )

        # Build input message from first agent's args
        # All parallel agents receive the same initial context
        first_args = specs[0][1] if specs else []
        prompt_text = " ".join(str(arg) for arg in first_args) if first_args else ""
        content = None
        if prompt_text:
            parts = [genai_types.Part.from_text(text=prompt_text)]
            content = genai_types.Content(role="user", parts=parts)

        # Use InMemorySessionService for parallel execution (isolated context)
        session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
        app_name = "dsl_parallel"
        user_id = "workflow_user"
        session_id = f"parallel_session_{id(specs)}"

        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state={},
        )

        runner = Runner(
            app_name=app_name,
            session_service=session_service,
            agent=parallel_agent,
        )

        # Execute ParallelAgent and yield events as they occur
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            yield event

        # Get session and extract results from state
        session = await session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        # Store results directly in ctx.vars (parse JSON if possible)
        logger.debug(
            "Parallel execution complete. Session state keys: %s, "
            "output_key_mapping: %s",
            list(session.state.keys()) if session and session.state else "None",
            output_key_mapping,
        )
        if session and session.state:
            for target_var, output_key in output_key_mapping.items():
                if output_key in session.state:
                    raw = session.state[output_key]
                    parsed = _try_parse_json(raw)
                    logger.debug(
                        "Parallel result for %s: type=%s",
                        target_var,
                        type(parsed).__name__,
                    )
                    ctx.vars[target_var] = parsed

    async def close(self) -> None:
        """Clean up all created agents.

        This method is called when the workload context manager exits.
        It closes all agents that were created during execution.
        """
        for agent in self._created_agents:
            if self._agent_factory:
                await self._agent_factory.close(agent)
        self._created_agents.clear()

    def create_context(
        self,
        *,
        input_prompt: str = "",
    ) -> WorkflowContext:
        """Create a new workflow context.

        Args:
            input_prompt: The user's input prompt (built-in variable).

        Returns:
            A fresh WorkflowContext connected to this workflow.

        """
        ctx = WorkflowContext(workflow=self)
        ctx.set_models(self._models)
        ctx.set_prompts(self._prompts)
        ctx.set_agents(self._agents)
        ctx.set_schemas(self._schemas)

        # Set built-in variables
        ctx.vars["input_prompt"] = input_prompt

        self._context = ctx
        return ctx

    async def on_start(self, ctx: WorkflowContext) -> None:
        """Handle workflow start event.

        Override this method to initialize global variables.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_input(self, ctx: WorkflowContext) -> None:
        """Handle input event.

        Override this method to process/guard input.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_output(self, ctx: WorkflowContext) -> None:
        """Handle output event.

        Override this method to process/guard output.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_tool_call(self, ctx: WorkflowContext) -> None:
        """Handle tool call event.

        Override this method to intercept tool calls.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_tool_result(self, ctx: WorkflowContext) -> None:
        """Handle tool result event.

        Override this method to process tool results.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_start(self, ctx: WorkflowContext) -> None:
        """Handle after start event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_input(self, ctx: WorkflowContext) -> None:
        """Handle after input event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_output(self, ctx: WorkflowContext) -> None:
        """Handle after output event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_tool_call(self, ctx: WorkflowContext) -> None:
        """Handle after tool call event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_tool_result(self, ctx: WorkflowContext) -> None:
        """Handle after tool result event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use
