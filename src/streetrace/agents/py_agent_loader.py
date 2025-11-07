"""Agent manager for the StreetRace application."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast

from streetrace.agents.base_agent_loader import AgentInfo, AgentLoader
from streetrace.log import get_logger
from streetrace.utils.file_discovery import find_files

if TYPE_CHECKING:
    from streetrace.agents.street_race_agent import StreetRaceAgent

logger = get_logger(__name__)


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
            name=agent_card.name,
            description=agent_card.description,
            module=agent_module,
        )


class PythonAgentLoader(AgentLoader):
    """Python agent loader with location-first support."""

    def __init__(
        self,
        base_paths: list[Path | str] | list[Path] | list[str] | None = None,
    ) -> None:
        """Initialize the PythonAgentLoader.

        Args:
            base_paths: List of base paths to search for agents (for legacy discover())

        """
        self.base_paths = (
            [p if isinstance(p, Path) else Path(p) for p in base_paths]
            if base_paths
            else []
        )

    def discover_in_paths(self, paths: list[Path]) -> list[AgentInfo]:
        """Discover Python agents in specific paths only.

        Args:
            paths: Specific paths to search in

        Returns:
            List of discovered Python agents in these paths

        """
        agents = []

        # Find all agent.py files in these paths and get their parent directories
        agent_py_files = find_files(paths, "agent.py")
        agent_dirs = [f.parent for f in agent_py_files]

        for agent_dir in agent_dirs:
            if not agent_dir.exists() or not agent_dir.is_dir():
                continue

            try:
                agent_metadata = _validate_impl(agent_dir)
                agents.append(agent_metadata)
            except (
                KeyError,
                ValueError,
                TypeError,
                AttributeError,
                FileNotFoundError,
            ):
                logger.debug(
                    "Failed to load Python agent from %s",
                    agent_dir,
                )

        return agents

    def load_from_path(self, path: Path) -> "StreetRaceAgent":
        """Load Python agent from directory path.

        Args:
            path: Directory containing agent.py

        Returns:
            Loaded Python agent

        Raises:
            ValueError: If not a directory or cannot load

        """
        if not path.is_dir():
            msg = f"Not a directory: {path}"
            raise ValueError(msg)

        try:
            agent_info = _validate_impl(path)
            return self.load_agent(agent_info)
        except (ValueError, FileNotFoundError) as e:
            msg = f"Failed to load Python agent from {path}: {e}"
            raise ValueError(msg) from e

    def load_from_url(self, url: str) -> "StreetRaceAgent":  # noqa: ARG002
        """Load Python agent from HTTP URL.

        Python agents cannot be loaded from URLs.

        Args:
            url: HTTP(S) URL

        Raises:
            ValueError: Always, as Python agents cannot be loaded from URLs

        """
        msg = "Python agents cannot be loaded from HTTP URLs"
        raise ValueError(msg)

    def load_agent(self, agent_info: AgentInfo) -> "StreetRaceAgent":
        """Load agent from AgentInfo.

        Args:
            agent_info: Previously discovered agent info

        Returns:
            Loaded agent

        Raises:
            ValueError: If AgentInfo is not a Python agent

        """
        if not agent_info.module:
            msg = f"AgentInfo {agent_info.name} is not a Python agent"
            raise ValueError(msg)

        agent_class = _get_streetrace_agent_class(agent_info.module)
        if agent_class is None:
            msg = f"No StreetRaceAgent implementation found for {agent_info.name}"
            raise ValueError(msg)

        return cast("StreetRaceAgent", agent_class())

    def discover(self) -> list[AgentInfo]:
        """Discover Python agents in configured base paths (legacy method).

        Returns:
            List of discovered Python agents

        """
        return self.discover_in_paths(self.base_paths)
