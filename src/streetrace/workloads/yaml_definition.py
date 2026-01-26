"""YAML workload definition.

This module provides the YamlWorkloadDefinition class that represents a
parsed YAML agent specification. It wraps a YamlAgentSpec and creates
BasicAgentWorkload instances for execution.
"""

from typing import TYPE_CHECKING

from streetrace.agents.yaml_models import YamlAgentSpec
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.basic_workload import BasicAgentWorkload


class YamlWorkloadDefinition(WorkloadDefinition):
    """Parsed YAML workload definition.

    This class represents a YAML agent specification that has been parsed and
    validated. It wraps a YamlAgentSpec and can create BasicAgentWorkload
    instances for execution.

    The definition is immutable after creation and all parameters are REQUIRED.

    Attributes:
        metadata: Immutable metadata about this workload
        spec: The parsed YAML agent specification

    """

    def __init__(
        self,
        metadata: WorkloadMetadata,
        spec: YamlAgentSpec,
    ) -> None:
        """Initialize the YAML workload definition.

        All parameters are REQUIRED. This definition should only be created
        after successful YAML parsing and validation.

        Args:
            metadata: Immutable metadata describing this workload
            spec: The parsed YAML agent specification

        """
        super().__init__(metadata)
        self._spec = spec

    @property
    def spec(self) -> YamlAgentSpec:
        """Get the YAML agent specification.

        Returns:
            The YamlAgentSpec containing the agent definition

        """
        return self._spec

    def create_workload(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> "BasicAgentWorkload":
        """Create a runnable BasicAgentWorkload instance from this definition.

        Creates a YamlAgent from the spec and wraps it in a BasicAgentWorkload.

        Args:
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the workload
            system_context: System context containing project-level settings
            session_service: ADK session service for conversation persistence

        Returns:
            A BasicAgentWorkload instance ready to be executed

        """
        from streetrace.agents.yaml_agent import YamlAgent
        from streetrace.agents.yaml_models import YamlAgentDocument
        from streetrace.workloads.basic_workload import BasicAgentWorkload

        # Create YamlAgentDocument from spec
        doc = YamlAgentDocument(
            spec=self._spec,
            file_path=self._metadata.source_path,
        )

        # Create YamlAgent from document
        agent = YamlAgent(doc)

        return BasicAgentWorkload(
            agent_definition=agent,
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            session_service=session_service,
        )
