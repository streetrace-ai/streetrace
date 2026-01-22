"""Workload protocol for unified agent execution.

This module defines the Workload protocol that all executable units (agents, flows)
must implement. It provides a single execution interface for the Supervisor.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.genai.types import Content


@runtime_checkable
class Workload(Protocol):
    """Protocol for all executable workloads.

    A Workload represents any unit of work that can be executed by the Supervisor.
    This includes DSL agents, Python agents, YAML agents, and flows.

    The protocol defines two methods:
    - run_async: Execute the workload and yield events
    - close: Clean up any resources allocated during execution
    """

    def run_async(
        self,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Execute the workload and yield events.

        Args:
            session: ADK session for conversation persistence
            message: User message to process, or None for initial runs

        Yields:
            ADK events from execution

        """
        ...

    async def close(self) -> None:
        """Clean up all resources allocated by this workload.

        This method is called when the workload context manager exits,
        either normally or due to an exception. Implementations should
        release any resources such as created agents, connections, etc.
        """
        ...
