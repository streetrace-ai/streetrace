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
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


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
        ui_bus: UiBus,
        work_dir: Path,
    ) -> None:
        """Initialize the AgentManager.

        Args:
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the agents
            system_context: Agent's access to System Context
            ui_bus: UI event bus for displaying messages to the user
            work_dir: Current working directory

        """
        self.model_factory = model_factory
        self.tool_provider = tool_provider
        self.system_context = system_context
        self.ui_bus = ui_bus
        self.work_dir = work_dir

    def list_available_agents(self) -> list[AgentInfo]:
        """List all available agents in the system.

        Returns:
            List of AgentInfo objects representing available agents

        """
        base_dirs = [
            self.work_dir / "agents",  # ./agents/ (relative to working directory)
            # ../../agents/ (relative to src/streetrace/agents/agent_manager.py)
            Path(__file__).parent.parent.parent.parent / "agents",
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
        agent_info = next(
            (
                agent_info
                for agent_info in self.list_available_agents()
                if agent_info.agent_card.name == agent_name
            ),
            None,
        )
        if not agent_info:
            msg = "Specified agent not found."
            raise ValueError(msg)
        agent_type = get_agent_impl(agent_info)
        agent_definition = agent_type()
        required_tools = await agent_definition.get_required_tools()
        async with self.tool_provider.get_tools(required_tools) as tools:
            yield await agent_definition.create_agent(self.model_factory, tools)
