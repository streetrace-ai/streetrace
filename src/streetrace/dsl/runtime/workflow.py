"""Base workflow class for Streetrace DSL.

Provide the base class that all generated workflows extend.
This class implements the Workload protocol for unified execution.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from streetrace.dsl.runtime.context import WorkflowContext
from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.dsl_agent_factory import DslAgentFactory

logger = get_logger(__name__)


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
            return EntryPoint(type="agent", name=(self._agents.items()[0][0].name))

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

    async def _execute_flow(
        self,
        flow_name: str,
        session: "Session",
        message: "Content | None",
    ) -> None:
        """Execute a flow.

        Args:
            flow_name: Name of the flow to execute.
            session: ADK session (reserved for future event forwarding).
            message: User message (reserved for future event forwarding).

        """
        # Reserved for future event forwarding (Option 2/3 in design doc)
        _ = session, message

        flow_method = getattr(self, f"flow_{flow_name}", None)
        if flow_method is None:
            msg = f"Flow '{flow_name}' not found"
            raise ValueError(msg)

        ctx = self.create_context()
        await flow_method(ctx)

    async def run_async(
        self,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Execute the workload based on DSL definition.

        Entry point selection:
        1. If DSL defines a 'main' flow -> run_flow('main')
        2. Else if DSL defines a 'default' agent -> run_agent('default')
        3. Else run first defined agent

        Args:
            session: ADK session for conversation persistence.
            message: User message to process.

        Yields:
            ADK events from execution.

        """
        entry_point = self._determine_entry_point()

        if entry_point.type == "flow":
            # For now, flows don't yield events
            await self._execute_flow(entry_point.name, session, message)
            return
        else:
            async for event in self._execute_agent(entry_point.name, session, message):
                yield event

    async def run_agent(self, agent_name: str, *args: object) -> object:
        """Run an agent from within a flow.

        Called by generated flow code via ctx.run_agent().
        Uses _create_agent() which delegates to DslAgentFactory.

        Args:
            agent_name: Name of the agent to run.
            *args: Arguments to pass to the agent.

        Returns:
            Final response from the agent.

        Raises:
            ValueError: If agent_factory not set.

        """
        agent = await self._create_agent(agent_name)

        # Build prompt from args
        prompt_text = " ".join(str(arg) for arg in args) if args else ""
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
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response = event.content.parts[0].text
                break

        return final_response

    async def run_flow(self, flow_name: str, *args: object) -> object:
        """Run a flow from within another flow.

        Args:
            flow_name: Name of the flow to run.
            *args: Arguments to pass to the flow.

        Returns:
            Result from the flow.

        Raises:
            ValueError: If flow not found.

        """
        _ = args  # Available for future use
        flow_method = getattr(self, f"flow_{flow_name}", None)
        if flow_method is None:
            msg = f"Flow '{flow_name}' not found"
            raise ValueError(msg)

        ctx = self.create_context()
        return await flow_method(ctx)

    async def close(self) -> None:
        """Clean up all created agents.

        This method is called when the workload context manager exits.
        It closes all agents that were created during execution.
        """
        for agent in self._created_agents:
            if self._agent_factory:
                await self._agent_factory.close(agent)
        self._created_agents.clear()

    def create_context(self) -> WorkflowContext:
        """Create a new workflow context.

        Returns:
            A fresh WorkflowContext connected to this workflow.

        """
        ctx = WorkflowContext(workflow=self)
        ctx.set_models(self._models)
        ctx.set_prompts(self._prompts)
        ctx.set_agents(self._agents)
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
