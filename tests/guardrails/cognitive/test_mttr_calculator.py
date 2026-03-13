"""Tests for MttrCalculator: recovery measurement."""

from __future__ import annotations

from streetrace.guardrails.cognitive.mttr_calculator import MttrCalculator


class TestRecoveryMeasurement:
    """Verify recovery turn and time measurement."""

    def test_no_intervention_no_recovery(self) -> None:
        """No recovery data when no intervention recorded."""
        calc = MttrCalculator()
        assert calc.recovery_turns is None
        assert calc.recovery_time_ms is None

    def test_record_intervention(self) -> None:
        """Record an intervention event."""
        calc = MttrCalculator()
        calc.record_intervention(turn_number=5, risk_score=0.90)

        assert calc.intervention_turn == 5
        assert calc.is_recovering is True

    def test_record_recovery(self) -> None:
        """Record recovery after intervention."""
        calc = MttrCalculator()
        calc.record_intervention(turn_number=5, risk_score=0.90)
        calc.record_recovery(turn_number=7, risk_score=0.25)

        assert calc.recovery_turns == 2
        assert calc.is_recovering is False

    def test_recovery_time_measured(self) -> None:
        """Recovery time in ms is measured between events."""
        calc = MttrCalculator()
        calc.record_intervention(turn_number=5, risk_score=0.90)
        calc.record_recovery(turn_number=7, risk_score=0.25)

        # recovery_time_ms should be >= 0
        assert calc.recovery_time_ms is not None
        assert calc.recovery_time_ms >= 0.0

    def test_multiple_interventions(self) -> None:
        """Track the most recent intervention/recovery pair."""
        calc = MttrCalculator()

        calc.record_intervention(turn_number=3, risk_score=0.85)
        calc.record_recovery(turn_number=5, risk_score=0.20)

        calc.record_intervention(turn_number=8, risk_score=0.92)
        calc.record_recovery(turn_number=11, risk_score=0.15)

        assert calc.recovery_turns == 3
        assert calc.intervention_turn == 8

    def test_recovery_without_intervention_ignored(self) -> None:
        """Recovery without prior intervention does nothing."""
        calc = MttrCalculator()
        calc.record_recovery(turn_number=5, risk_score=0.20)

        assert calc.recovery_turns is None
        assert calc.is_recovering is False
