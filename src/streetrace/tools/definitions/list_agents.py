"""list_agents tool implementation.

Discovers and lists available agents in the system from predefined directories.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import TypedDict

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

    output: list[AgentInfo] | None  # type: ignore[misc]


def import_agent_module(agent_dir: Path) -> ModuleType | None:
    """Import the agent module from the specified directory.

    Args:
        agent_dir: Path to the agent directory

    Returns:
        The imported module or None if import failed

    """
    agent_file = agent_dir / "agent.py"
    if not agent_file.exists() or not agent_file.is_file():
        msg = f"Agent definition not found: {agent_file}"
        raise FileNotFoundError(msg)

    try:
        # Create a unique module name to avoid conflicts
        module_name = f"agent_module_{agent_dir.name}"
        spec = importlib.util.spec_from_file_location(module_name, agent_file)
        if spec is None or spec.loader is None:
            logger.warning(
                "Failed to create module spec for agent",
                extra={"agent_dir": str(agent_dir)},
            )
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except (ImportError, AttributeError, TypeError) as ex:
        logger.warning(
            "Failed to import agent module",
            extra={"agent_dir": str(agent_dir), "error": str(ex)},
        )
        msg = f"Failed to import agent module from {agent_dir}: {ex!s}"
        raise ValueError(msg) from ex
    else:
        return module


def _validate_and_get_metadata(agent_dir: Path) -> dict[str, str]:
    """Get agent metadata from the agent directory.

    Args:
        agent_dir: Path to the agent directory

    Returns:
        Dictionary containing agent metadata

    Raises:
        ValueError: If metadata is not found or invalid

    """
    agent_module = import_agent_module(agent_dir)
    err_msg: str | None = None
    if agent_module is None:
        err_msg = f"Failed to import agent module from {agent_dir}"
    elif not hasattr(agent_module, "run_agent") or not callable(
        agent_module.run_agent,
    ):
        err_msg = f"Agent module {agent_dir} does not export run_agent function"
    elif not hasattr(agent_module, "get_agent_metadata") or not callable(
        agent_module.get_agent_metadata,
    ):
        err_msg = (
            f"Agent module {agent_dir} does not export get_agent_metadata function"
        )
    else:
        metadata = agent_module.get_agent_metadata()
        if not isinstance(metadata, dict):
            err_msg = f"Agent metadata from {agent_dir} is not a valid dictionary"
        elif "name" not in metadata or "description" not in metadata:
            err_msg = f"Agent metadata from {agent_dir} is missing required keys"
        else:
            return metadata

    raise ValueError(err_msg)


def discover_agents(base_dirs: list[Path]) -> list[AgentInfo]:
    """Discover valid agents in the specified directories.

    Args:
        base_dirs: List of base directories to search for agents

    Returns:
        List of AgentInfo for discovered agents

    """
    agents = []

    for base_dir in base_dirs:
        if not base_dir.exists() or not base_dir.is_dir():
            continue

        # Check each subdirectory in the base directory
        for item in base_dir.iterdir():
            if not item.is_dir():
                continue

            try:
                agent_metadata = _validate_and_get_metadata(item)
                agent_name = agent_metadata["name"]
                agent_description = agent_metadata["description"]
            except (KeyError, ValueError, TypeError, AttributeError):
                logger.exception(
                    "Failed to get agent name or description from %s",
                    item,
                )
            else:
                agents.append(
                    AgentInfo(
                        name=agent_name,
                        path=str(item.relative_to(base_dir.parent)),
                        description=agent_description,
                    ),
                )

    return agents


def list_agents(work_dir: Path) -> AgentListResult:
    """List all available agents in the system.

    Searches for agent directories in predefined locations and returns information
    about each valid agent found.

    Args:
        work_dir: Current working directory

    Returns:
        AgentListResult containing discovered agents

    """
    # Define paths to search for agents
    agent_paths = [
        work_dir / "agents",  # ./agents/ (relative to current working directory)
        # ../../agents/ (relative to src/streetrace/app.py)
        Path(__file__).parent.parent.parent.parent.parent / "agents",
    ]

    try:
        agents = discover_agents(agent_paths)

        return AgentListResult(
            tool_name="list_agents",
            result=OpResultCode.SUCCESS,
            output=agents,
            error=None,
        )
    except OSError as ex:
        error_message = f"Failed to list agents: {ex!s}"
        return AgentListResult(
            tool_name="list_agents",
            result=OpResultCode.FAILURE,
            output=None,
            error=error_message,
        )
