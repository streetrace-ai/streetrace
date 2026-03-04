"""DSL workload definition.

This module provides the DslWorkloadDefinition class that represents a
compiled DSL workload. It is created ONLY after successful DSL compilation
and contains the workflow class and source mappings.
"""

from typing import TYPE_CHECKING

from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.dsl.sourcemap import SourceMapping
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.dsl_agent_factory import DslAgentFactory
    from streetrace.workloads.dsl_workload import DslWorkload


class DslWorkloadDefinition(WorkloadDefinition):
    """Compiled DSL workload definition.

    This class represents a DSL workload that has been successfully compiled.
    It is created ONLY after the DSL source has been parsed, validated, and
    compiled to bytecode. The workflow_class is REQUIRED (not Optional) because
    this definition should never exist in an incomplete state.

    The definition is immutable after creation and can create DslWorkload
    instances for execution.

    Attributes:
        metadata: Immutable metadata about this workload
        workflow_class: The compiled workflow class (always populated)
        source_map: Source mappings for error translation
        agent_factory: Factory for creating ADK agents from this workflow

    """

    def __init__(
        self,
        metadata: WorkloadMetadata,
        workflow_class: type[DslAgentWorkflow],
        source_map: list[SourceMapping],
    ) -> None:
        """Initialize the DSL workload definition.

        All parameters are REQUIRED. This definition should only be created
        after successful DSL compilation.

        Args:
            metadata: Immutable metadata describing this workload
            workflow_class: The compiled workflow class from DSL
            source_map: Source mappings for translating generated code
                        positions back to original DSL source

        """
        super().__init__(metadata)
        self._workflow_class = workflow_class
        self._source_map = source_map
        self._agent_factory: DslAgentFactory | None = None

    @property
    def workflow_class(self) -> type[DslAgentWorkflow]:
        """Get the compiled workflow class.

        Returns:
            The workflow class generated from DSL compilation

        """
        return self._workflow_class

    @property
    def source_map(self) -> list[SourceMapping]:
        """Get the source mappings.

        Returns:
            List of source mappings for error translation

        """
        return self._source_map

    @property
    def agent_factory(self) -> "DslAgentFactory":
        """Get the agent factory for creating ADK agents.

        The factory is created lazily and cached for subsequent accesses.

        Returns:
            DslAgentFactory instance configured for this workflow

        """
        if self._agent_factory is None:
            from streetrace.workloads.dsl_agent_factory import DslAgentFactory

            self._agent_factory = DslAgentFactory(
                workflow_class=self._workflow_class,
                source_file=self._metadata.source_path,
                source_map=self._source_map,
            )
        return self._agent_factory

    def create_workload(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> "DslWorkload":
        """Create a runnable DslWorkload instance from this definition.

        Args:
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the workload
            system_context: System context containing project-level settings
            session_service: ADK session service for conversation persistence

        Returns:
            A DslWorkload instance ready to be executed

        """
        from streetrace.workloads.dsl_workload import DslWorkload

        return DslWorkload(
            definition=self,
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            session_service=session_service,
        )
