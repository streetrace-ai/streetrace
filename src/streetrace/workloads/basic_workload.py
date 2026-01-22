"""Basic agent workload implementation.

This module provides the BasicAgentWorkload class that wraps Python and YAML
agent definitions for execution through the Workload protocol.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from google.adk import Runner

from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.agents.street_race_agent import StreetRaceAgent
    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider

logger = get_logger(__name__)


class BasicAgentWorkload:
    """Workload wrapper for Python and YAML agents.

    This class adapts traditional StreetRaceAgent implementations to the
    Workload protocol, enabling them to be executed by the Supervisor through
    a unified interface.

    The workload manages agent lifecycle:
    1. Creates the agent on first run_async call
    2. Reuses the created agent for subsequent calls
    3. Cleans up the agent on close()
    """

    def __init__(
        self,
        agent_definition: "StreetRaceAgent",
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> None:
        """Initialize the basic agent workload.

        Args:
            agent_definition: The StreetRaceAgent definition to wrap
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the agent
            system_context: System context containing project-level instructions
            session_service: ADK session service for conversation persistence

        """
        self._agent_def = agent_definition
        self._model_factory = model_factory
        self._tool_provider = tool_provider
        self._system_context = system_context
        self._session_service = session_service
        self._agent: BaseAgent | None = None

    async def run_async(
        self,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Execute the agent and yield events.

        Create the agent if not already created, then run it via ADK Runner
        using the provided session. All events from the Runner are yielded.

        Args:
            session: ADK session for conversation persistence
            message: User message to process, or None for initial runs

        Yields:
            ADK events from execution

        """
        # Create the agent if not already created
        if self._agent is None:
            logger.debug("Creating agent from definition")
            self._agent = await self._agent_def.create_agent(
                self._model_factory,
                self._tool_provider,
                self._system_context,
            )

        # Create Runner with the session's service
        runner = Runner(
            app_name=session.app_name,
            session_service=self._session_service,
            agent=self._agent,
        )

        # Run the agent and yield all events
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=message,
        ):
            yield event

    async def close(self) -> None:
        """Clean up all resources allocated by this workload.

        Call the agent definition's close method if an agent was created,
        then set the agent reference to None.
        """
        if self._agent:
            logger.debug("Closing agent")
            await self._agent_def.close(self._agent)
            self._agent = None

    @property
    def agent(self) -> "BaseAgent | None":
        """Get the created agent instance.

        Returns:
            The BaseAgent instance if created, None otherwise

        """
        return self._agent
