"""list_agents tool implementation.

Discovers and lists available agents in the system from predefined directories.
"""

from pathlib import Path
from typing import Any, TypedDict

from streetrace.agents.agent_loader import get_available_agents
from streetrace.log import get_logger
from streetrace.tools.definitions.result import OpResult, OpResultCode

logger = get_logger(__name__)


class AgentInfo(TypedDict):
    """Information about a discovered agent."""

    name: str
    path: str
    description: str | None


class AgentListResult(OpResult):
    """Result containing the list of available agents."""

    output: list[dict[str, Any]] | None  # type: ignore[misc]


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
    # Define paths to search for agents
    base_dirs = [
        # ./agents/ (relative to current working directory)
        work_dir / "agents",
        # ../../agents/ (relative to src/streetrace/app.py)
        Path(__file__).parent / "../../agents",
    ]
    agents = get_available_agents(base_dirs)
    return AgentListResult(
        tool_name="list_agents",
        result=OpResultCode.SUCCESS,
        output=[agent.agent_card.model_dump() for agent in agents],
        error="",
    )
