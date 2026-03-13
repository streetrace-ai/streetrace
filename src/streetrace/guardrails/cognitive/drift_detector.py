"""Drift detector for threshold comparison and action decisions.

Compare per-turn risk scores against configurable warn/block
thresholds, respecting min_turns_before_alert.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from streetrace.guardrails.types import GuardrailAction
from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.guardrails.config import CognitiveMonitorConfig

logger = get_logger(__name__)


@dataclass(frozen=True)
class DriftResult:
    """Result of drift detection evaluation.

    Attributes:
        action: Guardrail action decision.
        risk_score: Computed risk score.
        turn_number: Turn number evaluated.

    """

    action: GuardrailAction
    risk_score: float
    turn_number: int


class DriftDetector:
    """Compare risk scores against thresholds.

    Produce action decisions (allow/warn/block) based on
    configured thresholds and minimum turn requirements.
    """

    def __init__(self, *, config: CognitiveMonitorConfig) -> None:
        """Initialize with configuration.

        Args:
            config: Cognitive monitor configuration.

        """
        self._config = config

    def evaluate(
        self, *, risk_score: float, turn_number: int,
    ) -> DriftResult:
        """Evaluate risk score against thresholds.

        If turn_number is below min_turns_before_alert, always
        return ALLOW regardless of risk score.

        Args:
            risk_score: Current risk score (0.0-1.0).
            turn_number: Current conversation turn number.

        Returns:
            DriftResult with action and metadata.

        """
        if turn_number < self._config.min_turns_before_alert:
            logger.debug(
                "Turn %d below min_turns %d, allowing",
                turn_number, self._config.min_turns_before_alert,
            )
            return DriftResult(
                action=GuardrailAction.ALLOW,
                risk_score=risk_score,
                turn_number=turn_number,
            )

        if risk_score >= self._config.block_threshold:
            action = GuardrailAction.BLOCK
        elif risk_score >= self._config.warn_threshold:
            action = GuardrailAction.WARN
        else:
            action = GuardrailAction.ALLOW

        logger.debug(
            "Turn %d risk=%.4f action=%s",
            turn_number, risk_score, action.value,
        )
        return DriftResult(
            action=action,
            risk_score=risk_score,
            turn_number=turn_number,
        )
