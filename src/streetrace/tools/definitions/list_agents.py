"""list_agents tool implementation.

Discovers and lists available agents in the system from predefined directories.
"""

from pathlib import Path
from typing import Literal, TypedDict

from streetrace.log import get_logger
from streetrace.tools.definitions.result import OpResult, OpResultCode

logger = get_logger(__name__)


class AgentInfo(TypedDict):
    """Information about a discovered agent."""

    name: str
    description: str | None
    definition_type: Literal["yaml", "python"]
    definition_path: str


class AgentListResult(OpResult):
    """Result containing the list of available agents."""

    output: list[AgentInfo]  # type: ignore[misc]


def list_agents(work_dir: Path) -> AgentListResult:
    """List all available agents in the system.

    Searches for agent directories in predefined locations and returns information
    about each valid agent found. Only agents implementing the StreetRaceAgent
    interface are discovered.

    Args:
        work_dir: Current working directory

    Returns:
        AgentListResult containing discovered agents

    """
    from streetrace.agents.agent_manager import DEFAULT_AGENT_PATHS
    from streetrace.agents.py_agent_loader import PythonAgentLoader
    from streetrace.agents.yaml_agent_loader import YamlAgentLoader

    agent_paths = [work_dir / p for p in DEFAULT_AGENT_PATHS]

    yaml_loader = YamlAgentLoader(agent_paths)
    python_loader = PythonAgentLoader(agent_paths)
    agents = yaml_loader.discover() + python_loader.discover()
    return AgentListResult(
        tool_name="list_agents",
        result=OpResultCode.SUCCESS,
        output=[
            AgentInfo(
                name=agent.name,
                description=agent.description,
                definition_type=agent.kind,
                definition_path=agent.path,
            )
            for agent in agents
        ],
        error="",
    )
