"""Python definition loader.

This module provides the PythonDefinitionLoader class for loading Python
agent modules into PythonWorkloadDefinition instances.

After SourceResolver consolidation, this loader only handles loading.
Discovery and resolution are handled by SourceResolver.
"""

from streetrace.agents.py_agent_loader import (
    _get_streetrace_agent_class,
    _import_agent_module,
)
from streetrace.agents.resolver import SourceResolution
from streetrace.log import get_logger
from streetrace.workloads.metadata import WorkloadMetadata
from streetrace.workloads.python_definition import PythonWorkloadDefinition

logger = get_logger(__name__)


class PythonDefinitionLoader:
    """Loader for Python agent modules.

    Loads and validates Python agent modules during load() - no deferred loading.
    This ensures that invalid modules are rejected early during discovery
    rather than at execution time.

    This class implements the DefinitionLoader protocol. Discovery and
    resolution are handled by SourceResolver.

    Note: Python agents require file_path from SourceResolution because they
    need to be imported into the Python runtime. Content alone is not sufficient.
    """

    def load(self, resolution: SourceResolution) -> PythonWorkloadDefinition:
        """Load a Python agent module from a SourceResolution.

        Module import and agent discovery happens immediately. Invalid modules
        raise exceptions. This ensures that the returned PythonWorkloadDefinition
        always has a valid agent_class.

        Args:
            resolution: SourceResolution with file_path pointing to agent directory

        Returns:
            A fully populated PythonWorkloadDefinition with agent_class

        Raises:
            ValueError: If file_path is missing, module cannot be imported,
                or has no StreetRaceAgent

        """
        if resolution.file_path is None:
            msg = (
                f"Python agent requires file_path, but got None for {resolution.source}"
            )
            raise ValueError(msg)

        path = resolution.file_path

        # Ensure it's a directory with agent.py
        if not path.is_dir():
            msg = f"Python agent path must be a directory: {path}"
            raise ValueError(msg)

        agent_file = path / "agent.py"
        if not agent_file.exists():
            msg = f"Agent definition not found: {agent_file}"
            raise ValueError(msg)

        logger.debug("Loading Python agent from: %s", path)

        # Import the module
        try:
            module = _import_agent_module(path)
        except (ValueError, FileNotFoundError, SyntaxError) as e:
            msg = f"Failed to import agent module from {path}: {e}"
            raise ValueError(msg) from e

        if module is None:
            msg = f"Failed to import agent module from {path}"
            raise ValueError(msg)

        # Find the StreetRaceAgent class
        agent_class = _get_streetrace_agent_class(module)
        if agent_class is None:
            msg = f"No StreetRaceAgent implementation found in {path}"
            raise ValueError(msg)

        # Get agent card for metadata
        try:
            agent_instance = agent_class()
            agent_card = agent_instance.get_agent_card()
            name = agent_card.name
            description = agent_card.description
        except Exception as e:
            msg = f"Failed to get agent card from {path}: {e}"
            raise ValueError(msg) from e

        # Create metadata
        metadata = WorkloadMetadata(
            name=name,
            description=description,
            source_path=path,
            format="python",
        )

        logger.debug(
            "Loaded Python definition '%s' from %s with class %s",
            metadata.name,
            path,
            agent_class.__name__,
        )

        return PythonWorkloadDefinition(
            metadata=metadata,
            agent_class=agent_class,
            module=module,
        )
