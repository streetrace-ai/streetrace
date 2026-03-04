"""Workload definition abstract base class.

This module provides the WorkloadDefinition abstract base class that serves
as the contract for all compiled workload definitions. Definitions are
immutable artifacts that can create runnable Workload instances.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.protocol import Workload


class WorkloadDefinition(ABC):
    """Abstract base class for compiled workload definitions.

    A WorkloadDefinition represents a compiled artifact that describes a
    workload. It contains all the information needed to create a runnable
    Workload instance. Definitions are created during the discovery/loading
    phase and are immutable once created.

    The key distinction is:
    - WorkloadDefinition: Compiled artifact describing what to run
    - Workload: Running instance that executes the definition

    Subclasses must implement the create_workload() method to provide
    format-specific workload creation logic.

    Attributes:
        metadata: Immutable metadata about this workload definition

    """

    def __init__(self, metadata: WorkloadMetadata) -> None:
        """Initialize the workload definition.

        Args:
            metadata: Immutable metadata describing this workload

        """
        self._metadata = metadata

    @property
    def metadata(self) -> WorkloadMetadata:
        """Get the workload metadata.

        Returns:
            The immutable metadata for this workload definition

        """
        return self._metadata

    @property
    def name(self) -> str:
        """Get the workload name.

        Convenience property that delegates to metadata.name.

        Returns:
            The name of this workload

        """
        return self._metadata.name

    @abstractmethod
    def create_workload(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> "Workload":
        """Create a runnable workload instance from this definition.

        This method is called when the workload needs to be executed.
        Implementations should create and return a Workload instance
        configured with the provided dependencies.

        Args:
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the workload
            system_context: System context containing project-level settings
            session_service: ADK session service for conversation persistence

        Returns:
            A Workload instance ready to be executed

        """
        ...
