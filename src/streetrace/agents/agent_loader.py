"""Agent manager for the StreetRace application."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.log import get_logger

logger = get_logger(__name__)


class AgentInfo:
    """Agent card and module references."""

    agent_card: StreetRaceAgentCard
    module: ModuleType

    def __init__(self, agent_card: StreetRaceAgentCard, module: ModuleType) -> None:
        """Initialize with the provided Agent Card and Module."""
        self.agent_card = agent_card
        self.module = module


def _import_agent_module(agent_dir: Path) -> ModuleType | None:
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


def _get_streetrace_agent_class(module: ModuleType) -> type[Any] | None:
    """Get the StreetRaceAgent class from the module if it exists.

    Args:
        module: The module to extract the agent class from

    Returns:
        The StreetRaceAgent class or None if not found

    """
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if not isinstance(attr, type) or attr.__module__ != module.__name__:
            continue

        # Check if it's a StreetRaceAgent subclass
        # We use string comparison to avoid importing StreetRaceAgent here
        # which could create circular imports
        for base in attr.__mro__[1:]:  # Skip the class itself
            if (
                base.__name__ == "StreetRaceAgent"
                and "street_race_agent" in base.__module__
            ):
                return attr

    return None


def _validate_impl(agent_dir: Path) -> AgentInfo:
    """Get agent metadata from the agent directory.

    Args:
        agent_dir: Path to the agent directory

    Returns:
        Dictionary containing agent metadata

    Raises:
        ValueError: If metadata is not found or invalid

    """
    agent_module = _import_agent_module(agent_dir)

    if agent_module is None:
        err_msg = f"Failed to import agent module from {agent_dir}"
        raise ValueError(err_msg)

    # Get StreetRaceAgent class
    agent_class = _get_streetrace_agent_class(agent_module)
    if agent_class is None:
        err_msg = f"No StreetRaceAgent implementation found in {agent_dir}"
        raise ValueError(err_msg)

    try:
        # Create an instance and get the agent card
        agent_instance = agent_class()
        agent_card = agent_instance.get_agent_card()
    except Exception as ex:
        logger.warning(
            "Failed to get agent card from StreetRaceAgent class",
            extra={"agent_dir": str(agent_dir), "error": str(ex)},
        )
        err_msg = f"Failed to get agent card from {agent_dir}: {ex!s}"
        raise ValueError(err_msg) from ex
    else:
        return AgentInfo(
            agent_card=agent_card,
            module=agent_module,
        )


def get_available_agents(base_dirs: list[Path]) -> list[AgentInfo]:
    """Discover and retrieve the list of available agents."""
    agents = []

    for base_dir in base_dirs:
        if not base_dir.exists() or not base_dir.is_dir():
            continue

        # Check each subdirectory in the base directory
        for item in base_dir.iterdir():
            if not item.is_dir():
                continue

            try:
                agent_metadata = _validate_impl(item)
            except (
                KeyError,
                ValueError,
                TypeError,
                AttributeError,
                FileNotFoundError,
            ):
                logger.exception(
                    "Failed to get agent name or description from %s",
                    item,
                )
            else:
                agents.append(agent_metadata)

    return agents


def get_agent_impl(agent_details: AgentInfo) -> type[StreetRaceAgent]:
    """Get class implementing the agent."""
    agent_class = _get_streetrace_agent_class(agent_details.module)
    if agent_class is None:
        err_msg = (
            "No StreetRaceAgent implementation found for "
            f"{agent_details.agent_card.name}"
        )
        raise ValueError(err_msg)
    return agent_class
