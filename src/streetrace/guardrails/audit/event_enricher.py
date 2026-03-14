"""Enrich violation events with run context before OTEL export.

Add agent identity, organization, and run metadata to violation
events so that downstream analytics can correlate violations with
their execution context.
"""

from __future__ import annotations

from streetrace.guardrails.audit.violation_events import ViolationEvent  # noqa: TC001


class EventEnricher:
    """Add run context to violation events before OTEL export.

    Accept a context dictionary at construction containing keys
    like ``agent_id``, ``org_id``, and ``run_id``. The ``enrich``
    method returns a new event with those fields populated.
    """

    def __init__(self, *, context: dict[str, str]) -> None:
        """Initialize with run context.

        Args:
            context: Dictionary with keys ``agent_id``, ``org_id``,
                ``run_id``. Missing keys default to empty string.

        """
        self._context = context

    def enrich(self, event: ViolationEvent) -> ViolationEvent:
        """Return a new event with run context fields populated.

        Preserve the original event's type and all fields.

        Args:
            event: Violation event to enrich.

        Returns:
            New event instance with context fields set.

        """
        return event.model_copy(
            update={
                "agent_id": self._context.get("agent_id", ""),
                "org_id": self._context.get("org_id", ""),
                "run_id": self._context.get("run_id", ""),
            },
        )
