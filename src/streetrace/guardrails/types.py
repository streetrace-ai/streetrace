"""Guardrail result types and enums.

Define the structured return types used by all guardrail components
in the Triple-Proxy architecture.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GuardrailAction(StrEnum):
    """Action determined by a guardrail check."""

    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class GuardrailResult:
    """Structured result from a guardrail check.

    Carry the action decision, confidence score, and provenance
    (which stage and proxy produced the result).

    Args:
        action: The guardrail decision (allow, warn, block).
        confidence: Confidence score clamped to [0.0, 1.0].
        detail: Human-readable explanation of the decision.
        stage: Detection stage that produced the result.
        proxy: Proxy that produced the result.

    """

    action: GuardrailAction
    confidence: float = 0.0
    detail: str = ""
    stage: str = ""
    proxy: str = ""

    def __post_init__(self) -> None:
        """Clamp confidence to [0.0, 1.0]."""
        clamped = max(0.0, min(1.0, self.confidence))
        object.__setattr__(self, "confidence", clamped)

    @property
    def is_triggered(self) -> bool:
        """Return True if the action is warn or block."""
        return self.action != GuardrailAction.ALLOW
