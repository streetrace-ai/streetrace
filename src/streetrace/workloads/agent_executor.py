"""Unified agent execution with proper async lifecycle management.

Provide a single execution path for running ADK agents regardless of
workload type (Python, YAML, DSL). Handle Runner creation, optional
mid-run compaction, and async generator cleanup.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.dsl.runtime.compacting_runner import CompactionStrategy

logger = get_logger(__name__)


@dataclass(frozen=True)
class CompactionParams:
    """Bundle compaction parameters for agent execution."""

    strategy: "CompactionStrategy"
    """Mid-run compaction strategy to apply."""

    max_tokens: int | None = None
    """Context window size, or None for auto-detect."""

    model: str | None = None
    """Model identifier, or None for default."""


class AgentExecutor:
    """Execute ADK agents with consistent lifecycle management.

    Provide a single, reusable execution path that:
    - Creates and manages ADK Runner instances
    - Wraps execution with CompactingRunner when compaction is configured
    - Properly closes async generators on completion or interruption
    """

    def __init__(
        self,
        *,
        session_service: "BaseSessionService",
    ) -> None:
        """Initialize the executor.

        Args:
            session_service: ADK session service for conversation persistence.

        """
        self._session_service = session_service

    async def run(
        self,
        *,
        agent: "BaseAgent",
        session: "Session",
        message: "Content | None",
        compaction: CompactionParams | None = None,
    ) -> AsyncGenerator["Event", None]:
        """Execute an agent and yield events with proper lifecycle cleanup.

        When compaction params are provided, use CompactingRunner for mid-run
        compaction. Otherwise use a standard ADK Runner.

        Args:
            agent: The ADK agent to execute.
            session: The session for conversation persistence.
            message: The user message to process, or None.
            compaction: Optional compaction parameters for mid-run compaction.

        Yields:
            ADK events from execution.

        """
        if compaction is not None:
            async for event in self._run_with_compaction(
                agent=agent,
                session=session,
                message=message,
                compaction=compaction,
            ):
                yield event
        else:
            async for event in self._run_standard(
                agent=agent,
                session=session,
                message=message,
            ):
                yield event

    async def _run_standard(
        self,
        *,
        agent: "BaseAgent",
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Execute agent with standard ADK Runner.

        Args:
            agent: The ADK agent to execute.
            session: The session for conversation persistence.
            message: The user message to process, or None.

        Yields:
            ADK events from execution.

        """
        from google.adk import Runner

        runner = Runner(
            app_name=session.app_name,
            session_service=self._session_service,
            agent=agent,
        )

        event_stream = runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=message,
        )

        try:
            async for event in event_stream:
                yield event
        finally:
            await event_stream.aclose()

    async def _run_with_compaction(
        self,
        *,
        agent: "BaseAgent",
        session: "Session",
        message: "Content | None",
        compaction: CompactionParams,
    ) -> AsyncGenerator["Event", None]:
        """Execute agent with mid-run compaction via CompactingRunner.

        Args:
            agent: The ADK agent to execute.
            session: The session for conversation persistence.
            message: The user message to process, or None.
            compaction: Compaction parameters (strategy, max_tokens, model).

        Yields:
            ADK events from execution.

        """
        from streetrace.dsl.runtime.compacting_runner import CompactingRunner

        compacting_runner = CompactingRunner(
            session_service=self._session_service,
            compaction_strategy=compaction.strategy,
            max_tokens=compaction.max_tokens,
            model=compaction.model or "",
        )

        event_stream = compacting_runner.run(
            agent=agent,
            session=session,
            message=message,
        )

        try:
            async for event in event_stream:
                yield event
        finally:
            await event_stream.aclose()
