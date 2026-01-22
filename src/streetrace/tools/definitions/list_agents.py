"""list_agents tool implementation.

Discovers and lists available agents in the system from predefined directories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from pathlib import Path

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider

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
    from typing import cast

    from streetrace.workloads import WorkloadManager

    # Create a minimal WorkloadManager instance for discovery
    # We don't need actual model_factory, tool_provider, or system_context for discovery
    # We cast None to the required types since discovery doesn't use them
    workload_manager = WorkloadManager(
        model_factory=cast("ModelFactory", None),
        tool_provider=cast("ToolProvider", None),
        system_context=cast("SystemContext", None),
        work_dir=work_dir,
    )

    agents = workload_manager.discover()
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
