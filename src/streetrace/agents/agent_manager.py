"""Agent manager for the StreetRace application."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from google.adk.agents import BaseAgent

    from streetrace.agents.yaml_models import AgentDocument

from streetrace.agents.agent_loader import (
    AgentInfo,
    get_agent_impl,
    get_available_agents,
)
from streetrace.agents.yaml_agent import YamlAgent
from streetrace.agents.yaml_loader import (
    AgentValidationError,
    discover_agents,
    find_agent_by_name,
    load_agent_from_file,
)
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AdkTool, ToolProvider

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
        """List all available Python-based agents in the system.

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

    def list_yaml_agents(self) -> list[str]:
        """List all available YAML agents with their descriptions.

        Returns:
            List of agent info strings in format "name: description (path)"

        """
        try:
            yaml_agents = discover_agents()
            agent_info = []
            for agent_doc in yaml_agents:
                path_info = f" ({agent_doc.file_path})" if agent_doc.file_path else ""
                info = (
                    f"{agent_doc.get_name()}: {agent_doc.get_description()}{path_info}"
                )
                agent_info.append(info)
        except AgentValidationError:
            logger.exception("Failed to discover YAML agents")
            return []
        else:
            return agent_info

    def validate_yaml_agent(self, file_path: Path) -> tuple[bool, str]:
        """Validate a YAML agent file.

        Args:
            file_path: Path to YAML agent file to validate

        Returns:
            Tuple of (is_valid, message)

        """
        try:
            from streetrace.agents.yaml_loader import validate_agent_file
            validate_agent_file(file_path)
        except AgentValidationError as e:
            error_msg = f"Validation failed for {file_path}: {e}"
            if e.cause:
                error_msg += f" (caused by: {e.cause})"
            return False, error_msg
        except (OSError, ImportError) as e:
            return False, f"Unexpected error validating {file_path}: {e}"
        else:
            return True, f"Agent file {file_path} is valid"

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

        # Check if agent_name is a path to a YAML file
        if "/" in agent_name or agent_name.endswith((".yml", ".yaml")):
            try:
                yaml_path = Path(agent_name).expanduser().resolve()
                if yaml_path.exists():
                    yield await self._create_yaml_agent_from_file(yaml_path)
                    return
                else:
                    msg = f"YAML agent file not found: {yaml_path}"
                    raise ValueError(msg)
            except AgentValidationError as e:
                msg = f"Failed to load YAML agent from {agent_name}: {e}"
                raise ValueError(msg) from e

        # Try to find YAML agent by name first
        yaml_agent_doc = find_agent_by_name(agent_name)
        if yaml_agent_doc:
            yield await self._create_yaml_agent_from_doc(yaml_agent_doc)
            return

        # Fall back to Python agents
        agent_info = next(
            (
                agent_info
                for agent_info in self.list_available_agents()
                if agent_info.agent_card.name == agent_name
            ),
            None,
        )
        if not agent_info:
            msg = (
                f"Specified agent not found ({agent_name}). "
                "Try --list-agents to see available agents."
            )
            raise ValueError(msg)

        agent_type = get_agent_impl(agent_info)
        agent_definition = agent_type()
        required_tools = await agent_definition.get_required_tools()
        tools: list[AdkTool] = []
        try:
            tools = await self.tool_provider.get_tools(required_tools)
            agent = await agent_definition.create_agent(
                self.model_factory,
                tools,
                self.system_context,
            )
            yield agent
        except:
            if tools:
                try:
                    await self.tool_provider.release_tools(tools)
                except:  # noqa: E722
                    logger.exception("Failed to release tools after previous exception")
            raise
        else:
            if tools:
                await self.tool_provider.release_tools(tools)

    async def _create_yaml_agent_from_file(self, file_path: Path) -> "BaseAgent":
        """Create a YAML agent from file path."""
        agent_doc = load_agent_from_file(file_path)
        return await self._create_yaml_agent_from_doc(agent_doc)

    async def _create_yaml_agent_from_doc(
        self, agent_doc: "AgentDocument",
    ) -> "BaseAgent":
        """Create a YAML agent from agent document."""
        yaml_agent = YamlAgent(agent_doc)
        required_tools = await yaml_agent.get_required_tools()
        tools: list[AdkTool] = []
        try:
            tools = await self.tool_provider.get_tools(required_tools)
            agent = await yaml_agent.create_agent(
                self.model_factory,
                tools,
                self.system_context,
            )
            return agent
        except:
            if tools:
                try:
                    await self.tool_provider.release_tools(tools)
                except:  # noqa: E722
                    logger.exception("Failed to release tools after previous exception")
            raise
