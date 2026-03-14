"""Tests for DriftDetector: threshold comparison, decisions."""

from __future__ import annotations

import pytest

from streetrace.guardrails.cognitive.drift_detector import (
    DriftDetector,
)
from streetrace.guardrails.config import CognitiveMonitorConfig
from streetrace.guardrails.types import GuardrailAction


@pytest.fixture
def config() -> CognitiveMonitorConfig:
    """Create a default config."""
    return CognitiveMonitorConfig(
        warn_threshold=0.60,
        block_threshold=0.85,
        min_turns_before_alert=3,
    )


class TestThresholdComparison:
    """Verify risk score vs threshold comparison."""

    def test_below_warn_allows(self, config: CognitiveMonitorConfig) -> None:
        """Risk below warn_threshold produces ALLOW."""
        detector = DriftDetector(config=config)
        result = detector.evaluate(risk_score=0.30, turn_number=5)

        assert result.action == GuardrailAction.ALLOW
        assert result.risk_score == pytest.approx(0.30)

    def test_above_warn_below_block_warns(
        self, config: CognitiveMonitorConfig,
    ) -> None:
        """Risk between warn and block produces WARN."""
        detector = DriftDetector(config=config)
        result = detector.evaluate(risk_score=0.70, turn_number=5)

        assert result.action == GuardrailAction.WARN

    def test_above_block_blocks(
        self, config: CognitiveMonitorConfig,
    ) -> None:
        """Risk above block_threshold produces BLOCK."""
        detector = DriftDetector(config=config)
        result = detector.evaluate(risk_score=0.90, turn_number=5)

        assert result.action == GuardrailAction.BLOCK

    def test_exact_warn_threshold_warns(
        self, config: CognitiveMonitorConfig,
    ) -> None:
        """Risk equal to warn_threshold produces WARN."""
        detector = DriftDetector(config=config)
        result = detector.evaluate(risk_score=0.60, turn_number=5)

        assert result.action == GuardrailAction.WARN

    def test_exact_block_threshold_blocks(
        self, config: CognitiveMonitorConfig,
    ) -> None:
        """Risk equal to block_threshold produces BLOCK."""
        detector = DriftDetector(config=config)
        result = detector.evaluate(risk_score=0.85, turn_number=5)

        assert result.action == GuardrailAction.BLOCK


class TestMinTurnsEnforcement:
    """Verify min_turns_before_alert is respected."""

    def test_high_risk_before_min_turns_allows(
        self, config: CognitiveMonitorConfig,
    ) -> None:
        """High risk before min_turns produces ALLOW."""
        detector = DriftDetector(config=config)
        # min_turns is 3, turn_number is 2
        result = detector.evaluate(risk_score=0.90, turn_number=2)

        assert result.action == GuardrailAction.ALLOW

    def test_high_risk_at_min_turns_blocks(
        self, config: CognitiveMonitorConfig,
    ) -> None:
        """High risk at min_turns produces BLOCK."""
        detector = DriftDetector(config=config)
        result = detector.evaluate(risk_score=0.90, turn_number=3)

        assert result.action == GuardrailAction.BLOCK

    def test_high_risk_after_min_turns_blocks(
        self, config: CognitiveMonitorConfig,
    ) -> None:
        """High risk after min_turns produces BLOCK."""
        detector = DriftDetector(config=config)
        result = detector.evaluate(risk_score=0.90, turn_number=10)

        assert result.action == GuardrailAction.BLOCK


class TestDriftResult:
    """Verify DriftResult carries expected fields."""

    def test_result_has_turn_number(
        self, config: CognitiveMonitorConfig,
    ) -> None:
        """DriftResult includes turn_number."""
        detector = DriftDetector(config=config)
        result = detector.evaluate(risk_score=0.50, turn_number=7)

        assert result.turn_number == 7

    def test_result_has_risk_score(
        self, config: CognitiveMonitorConfig,
    ) -> None:
        """DriftResult includes risk_score."""
        detector = DriftDetector(config=config)
        result = detector.evaluate(risk_score=0.42, turn_number=5)

        assert result.risk_score == pytest.approx(0.42)
