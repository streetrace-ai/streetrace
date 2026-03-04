"""DSL workload runtime.

This module provides the DslWorkload class that implements the Workload
protocol for executing DSL-based workflows.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.dsl.runtime.events import FlowEvent
    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.dsl_definition import DslWorkloadDefinition

logger = get_logger(__name__)


class DslWorkload:
    """Runnable DSL workload implementing the Workload protocol.

    This class wraps a compiled DSL workflow definition and executes it.
    All dependencies are REQUIRED at construction time - there are no
    optional parameters.

    The workload manages the workflow lifecycle:
    1. Creates workflow instance from definition.workflow_class
    2. Passes dependencies to the workflow for agent creation
    3. Delegates run_async() to the workflow
    4. Cleans up resources on close()

    """

    def __init__(
        self,
        definition: "DslWorkloadDefinition",
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> None:
        """Initialize the DSL workload.

        All parameters are REQUIRED. This workload should only be created
        through DslWorkloadDefinition.create_workload().

        Args:
            definition: The compiled DSL workload definition
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the workload
            system_context: System context containing project-level settings
            session_service: ADK session service for conversation persistence

        """
        self._definition = definition
        self._model_factory = model_factory
        self._tool_provider = tool_provider
        self._system_context = system_context
        self._session_service = session_service

        # Create workflow instance with all dependencies via constructor
        # Pass agent_factory from definition for agent creation
        self._workflow: DslAgentWorkflow = definition.workflow_class(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            session_service=session_service,
            agent_factory=definition.agent_factory,
        )

        logger.debug(
            "Created DslWorkload for %s with workflow %s",
            definition.name,
            self._workflow.__class__.__name__,
        )

    async def run_async(
        self,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event | FlowEvent", None]:
        """Execute the workload and yield events.

        Delegates to the underlying DslAgentWorkflow's run_async method.

        Args:
            session: ADK session for conversation persistence
            message: User message to process, or None for initial runs

        Yields:
            ADK events or FlowEvents from execution

        """
        async for event in self._workflow.run_async(session, message):
            yield event

    async def close(self) -> None:
        """Clean up all resources allocated by this workload.

        Delegates to the underlying DslAgentWorkflow's close method
        to clean up any created agents.
        """
        logger.debug("Closing DslWorkload for %s", self._definition.name)
        await self._workflow.close()

    @property
    def definition(self) -> "DslWorkloadDefinition":
        """Get the workload definition.

        Returns:
            The DslWorkloadDefinition that created this workload

        """
        return self._definition

    @property
    def workflow(self) -> DslAgentWorkflow:
        """Get the underlying workflow instance.

        Returns:
            The DslAgentWorkflow instance

        """
        return self._workflow
