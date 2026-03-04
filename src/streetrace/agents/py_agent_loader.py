"""Python agent module import and discovery helpers.

This module provides helper functions for importing Python agent modules
and discovering StreetRaceAgent classes. These functions are used by
PythonDefinitionLoader.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from streetrace.log import get_logger

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
