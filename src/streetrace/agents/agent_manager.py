"""Agent manager for the StreetRace application."""

import contextlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from google.adk.agents import BaseAgent

    from streetrace.agents.street_race_agent import StreetRaceAgent


from streetrace.agents.base_agent_loader import AgentInfo
from streetrace.agents.py_agent_loader import PythonAgentLoader
from streetrace.agents.yaml_agent_loader import YamlAgentLoader
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider

logger = get_logger(__name__)

_DEFAULT_AGENT = "Streetrace_Coding_Agent"

# Default search paths for agent autodiscovery
DEFAULT_AGENT_PATHS = [
    "./agents",
    ".",  # for *.agent.y{a,}ml files
    "~/.streetrace/agents",
    "/etc/streetrace/agents",  # Unix only
]


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

        # Initialize agent loaders
        agent_paths = [
            (self.work_dir / Path(p).expanduser()).resolve()
            for p in DEFAULT_AGENT_PATHS
        ]
        self.yaml_loader = YamlAgentLoader(agent_paths)
        self.python_loader = PythonAgentLoader(agent_paths)

    def discover(self) -> list[AgentInfo]:
        """Discover all known agents.

        Returns:
            List of AgentInfo objects representing available agents

        """
        return self.yaml_loader.discover() + self.python_loader.discover()

    @asynccontextmanager
    async def create_agent(self, agent_name: str) -> "AsyncGenerator[BaseAgent, None]":
        """Create an agent with the specified name and model.

        Args:
            agent_name: Name of the agent to create or path to YAML file

        Yields:
            The created agent

        Raises:
            ValueError: If agent creation fails

        """
        agent_name = _DEFAULT_AGENT if agent_name == "default" else agent_name

        agent_definition: StreetRaceAgent | None = None

        with contextlib.suppress(ValueError):
            agent_definition = self.yaml_loader.load_agent(agent_name)

        if not agent_definition:
            with contextlib.suppress(ValueError):
                agent_definition = self.python_loader.load_agent(agent_name)

        if not agent_definition:
            msg = (
                f"Specified agent not found ({agent_name}). "
                "Try --list-agents to see available agents."
            )
            raise ValueError(msg)

        agent: BaseAgent | None = None
        try:
            agent = await agent_definition.create_agent(
                self.model_factory,
                self.tool_provider,
                self.system_context,
            )
            yield agent
        finally:
            if agent:
                await agent_definition.close(agent)
