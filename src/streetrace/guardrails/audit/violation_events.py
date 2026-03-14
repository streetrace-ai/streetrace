"""Structured violation event models for guardrail audit trail.

Define Pydantic models for violation events emitted as OTEL span
events when guardrails trigger. Each event type carries proxy-specific
detection metadata alongside common audit fields.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from streetrace.guardrails.types import GuardrailAction  # noqa: TC001

OTEL_VIOLATION_PREFIX = "streetrace.guardrail.violation"
"""OTEL attribute namespace for violation event fields."""


class ViolationSeverity(StrEnum):
    """Severity level of a guardrail violation."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


def _generate_violation_id() -> str:
    """Generate a unique violation identifier."""
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(tz=UTC)


class ViolationEvent(BaseModel):
    """Base violation event emitted when a guardrail triggers.

    Carry common audit fields shared by all violation types.
    Subclasses add proxy-specific detection metadata.
    """

    violation_id: str = Field(default_factory=_generate_violation_id)
    timestamp: datetime = Field(default_factory=_now_utc)
    severity: ViolationSeverity
    action: GuardrailAction
    guardrail_name: str
    detail: str
    confidence: float = 0.0

    # Enrichment fields (populated by EventEnricher)
    agent_id: str = ""
    org_id: str = ""
    run_id: str = ""

    model_config = {"frozen": True}

    def to_otel_attributes(self) -> dict[str, str | float | bool]:
        """Map event fields to OTEL span event attributes.

        Return a flat dictionary with keys in the
        ``streetrace.guardrail.violation.*`` namespace.
        """
        attrs: dict[str, str | float | bool] = {
            f"{OTEL_VIOLATION_PREFIX}.id": self.violation_id,
            f"{OTEL_VIOLATION_PREFIX}.severity": str(self.severity),
            f"{OTEL_VIOLATION_PREFIX}.action": str(self.action),
            f"{OTEL_VIOLATION_PREFIX}.guardrail_name": self.guardrail_name,
            f"{OTEL_VIOLATION_PREFIX}.detail": self.detail,
            f"{OTEL_VIOLATION_PREFIX}.confidence": self.confidence,
        }
        if self.agent_id:
            attrs[f"{OTEL_VIOLATION_PREFIX}.agent_id"] = self.agent_id
        if self.org_id:
            attrs[f"{OTEL_VIOLATION_PREFIX}.org_id"] = self.org_id
        if self.run_id:
            attrs[f"{OTEL_VIOLATION_PREFIX}.run_id"] = self.run_id
        return attrs


class PromptViolation(ViolationEvent):
    """Violation event from the Prompt Proxy pipeline.

    Carry detection stage, matched pattern, and embedding similarity.
    """

    stage: str = ""
    pattern_matched: str = ""
    embedding_score: float = 0.0

    def to_otel_attributes(self) -> dict[str, str | float | bool]:
        """Extend base attributes with prompt-specific fields."""
        attrs = super().to_otel_attributes()
        attrs[f"{OTEL_VIOLATION_PREFIX}.stage"] = self.stage
        attrs[f"{OTEL_VIOLATION_PREFIX}.pattern_matched"] = (
            self.pattern_matched
        )
        attrs[f"{OTEL_VIOLATION_PREFIX}.embedding_score"] = (
            self.embedding_score
        )
        return attrs


class ToolViolation(ViolationEvent):
    """Violation event from MCP-Guard tool validation.

    Carry server identity, tool name, and trust score.
    """

    server_id: str = ""
    tool_name: str = ""
    trust_score: float = 0.0

    def to_otel_attributes(self) -> dict[str, str | float | bool]:
        """Extend base attributes with tool-specific fields."""
        attrs = super().to_otel_attributes()
        attrs[f"{OTEL_VIOLATION_PREFIX}.server_id"] = self.server_id
        attrs[f"{OTEL_VIOLATION_PREFIX}.tool_name"] = self.tool_name
        attrs[f"{OTEL_VIOLATION_PREFIX}.trust_score"] = self.trust_score
        return attrs


class DriftViolation(ViolationEvent):
    """Violation event from Cognitive Monitor drift detection.

    Carry session context, turn position, and risk score.
    """

    session_id: str = ""
    turn_number: int = 0
    risk_score: float = 0.0

    def to_otel_attributes(self) -> dict[str, str | float | bool]:
        """Extend base attributes with drift-specific fields."""
        attrs = super().to_otel_attributes()
        attrs[f"{OTEL_VIOLATION_PREFIX}.session_id"] = self.session_id
        attrs[f"{OTEL_VIOLATION_PREFIX}.turn_number"] = float(
            self.turn_number,
        )
        attrs[f"{OTEL_VIOLATION_PREFIX}.risk_score"] = self.risk_score
        return attrs


class RecoveryEvent(ViolationEvent):
    """Event recording recovery after a guardrail intervention.

    Carry MTTR-A metrics: recovery turns and wall-clock time.
    """

    session_id: str = ""
    recovery_turns: int = 0
    recovery_time_ms: int = 0

    def to_otel_attributes(self) -> dict[str, str | float | bool]:
        """Extend base attributes with recovery-specific fields."""
        attrs = super().to_otel_attributes()
        attrs[f"{OTEL_VIOLATION_PREFIX}.session_id"] = self.session_id
        attrs[f"{OTEL_VIOLATION_PREFIX}.recovery_turns"] = float(
            self.recovery_turns,
        )
        attrs[f"{OTEL_VIOLATION_PREFIX}.recovery_time_ms"] = float(
            self.recovery_time_ms,
        )
        return attrs
