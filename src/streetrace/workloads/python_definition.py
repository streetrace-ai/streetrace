"""Python workload definition.

This module provides the PythonWorkloadDefinition class that represents a
Python module containing a StreetRaceAgent class. It wraps the agent class
and module, creating BasicAgentWorkload instances for execution.
"""

from types import ModuleType
from typing import TYPE_CHECKING

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.basic_workload import BasicAgentWorkload


class PythonWorkloadDefinition(WorkloadDefinition):
    """Python module workload definition.

    This class represents a Python agent module that has been loaded and
    validated. It wraps a StreetRaceAgent class and its module, and can
    create BasicAgentWorkload instances for execution.

    The definition is immutable after creation and all parameters are REQUIRED.

    Attributes:
        metadata: Immutable metadata about this workload
        agent_class: The StreetRaceAgent subclass from the module
        module: The Python module containing the agent class

    """

    def __init__(
        self,
        metadata: WorkloadMetadata,
        agent_class: type[StreetRaceAgent],
        module: ModuleType,
    ) -> None:
        """Initialize the Python workload definition.

        All parameters are REQUIRED. This definition should only be created
        after successful module import and agent class discovery.

        Args:
            metadata: Immutable metadata describing this workload
            agent_class: The StreetRaceAgent subclass found in the module
            module: The Python module containing the agent class

        """
        super().__init__(metadata)
        self._agent_class = agent_class
        self._module = module

    @property
    def agent_class(self) -> type[StreetRaceAgent]:
        """Get the agent class.

        Returns:
            The StreetRaceAgent subclass from the module

        """
        return self._agent_class

    @property
    def module(self) -> ModuleType:
        """Get the module.

        Returns:
            The Python module containing the agent class

        """
        return self._module

    def create_workload(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> "BasicAgentWorkload":
        """Create a runnable BasicAgentWorkload instance from this definition.

        Instantiates the agent class and wraps it in a BasicAgentWorkload.

        Args:
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the workload
            system_context: System context containing project-level settings
            session_service: ADK session service for conversation persistence

        Returns:
            A BasicAgentWorkload instance ready to be executed

        """
        from streetrace.workloads.basic_workload import BasicAgentWorkload

        # Instantiate the agent class
        agent = self._agent_class()

        return BasicAgentWorkload(
            agent_definition=agent,
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            session_service=session_service,
        )
