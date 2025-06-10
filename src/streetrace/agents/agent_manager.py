"""Agent manager for the StreetRace application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from google.adk.agents import BaseAgent

from streetrace.agents.agent_loader import (
    AgentInfo,
    get_agent_impl,
    get_available_agents,
)
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider

logger = get_logger(__name__)

_DEFAULT_AGENT = "Streetrace Coding Agent"


class AgentManager:
    """Manages agent discovery, validation, and creation.

    The AgentManager is responsible for:
    1. Discovering agents in standard locations
    2. Validating that agents implement the required interface
    3. Creating agent instances with necessary dependencies
    4. Managing the lifecycle of agents
    """

    def __init__(
        self,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
        work_dir: Path,
    ) -> None:
        """Initialize the AgentManager.

        Args:
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the agents
            system_context: System context containing project-level instructions
            work_dir: Current working directory

        """
        self.model_factory = model_factory
        self.tool_provider = tool_provider
        self.system_context = system_context
        self.work_dir = work_dir

    def list_available_agents(self) -> list[AgentInfo]:
        """List all available agents in the system.

        Returns:
            List of AgentInfo objects representing available agents

        """
        base_dirs = [
            # ./agents/ (relative to working directory)
            self.work_dir / "agents",
            # /agents/ (relative to repo root)
            Path(__file__).parent,
        ]

        return get_available_agents(base_dirs)

    @asynccontextmanager
    async def create_agent(self, agent_name: str) -> AsyncGenerator[BaseAgent, None]:
        """Create an agent with the specified name and model.

        Args:
            agent_name: Name of the agent to create
            model_name: Name of the model to use (default: "default")

        Yields:
            The created agent

        Raises:
            ValueError: If agent creation fails

        """
        agent_name = _DEFAULT_AGENT if agent_name == "default" else agent_name
        agent_info = next(
            (
                agent_info
                for agent_info in self.list_available_agents()
                if agent_info.agent_card.name == agent_name
            ),
            None,
        )
        if not agent_info:
            msg = f"Specified agent not found ({agent_name})."
            raise ValueError(msg)
        agent_type = get_agent_impl(agent_info)
        agent_definition = agent_type()
        required_tools = await agent_definition.get_required_tools()
        async with self.tool_provider.get_tools(required_tools) as tools:
            yield await agent_definition.create_agent(
                self.model_factory,
                tools,
                self.system_context,
            )
