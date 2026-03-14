"""Tests for red team orchestrator coordination and threshold enforcement."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from streetrace.guardrails.redteam.metrics_collector import ProbeResult
from streetrace.guardrails.redteam.orchestrator import (
    RedTeamConfig,
    RedTeamOrchestrator,
    SuiteResult,
)
from streetrace.guardrails.types import GuardrailAction


def _passing_result() -> ProbeResult:
    return ProbeResult(
        probe_name="probe-1",
        expected_action=GuardrailAction.BLOCK,
        actual_action=GuardrailAction.BLOCK,
        latency_ms=5.0,
        proxy="prompt_proxy",
    )


def _failing_result() -> ProbeResult:
    return ProbeResult(
        probe_name="probe-2",
        expected_action=GuardrailAction.BLOCK,
        actual_action=GuardrailAction.ALLOW,
        latency_ms=5.0,
        proxy="prompt_proxy",
    )


class TestRedTeamConfig:
    """Verify red team configuration validation."""

    def test_default_thresholds(self) -> None:
        config = RedTeamConfig()
        assert config.max_asr == 0.10
        assert config.max_bypass_rate == 0.10

    def test_custom_thresholds(self) -> None:
        config = RedTeamConfig(max_asr=0.05, max_bypass_rate=0.05)
        assert config.max_asr == 0.05
        assert config.max_bypass_rate == 0.05

    def test_invalid_asr_raises(self) -> None:
        with pytest.raises(ValueError, match="max_asr"):
            RedTeamConfig(max_asr=-0.1)

    def test_invalid_bypass_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="max_bypass_rate"):
            RedTeamConfig(max_bypass_rate=1.5)


class TestRedTeamOrchestrator:
    """Verify runner coordination and threshold enforcement."""

    def test_run_suite_passes_when_below_threshold(self) -> None:
        runner_a = MagicMock()
        runner_a.run.return_value = [_passing_result()]
        runner_b = MagicMock()
        runner_b.run.return_value = [_passing_result()]

        config = RedTeamConfig(max_asr=0.10, max_bypass_rate=0.10)
        orchestrator = RedTeamOrchestrator(
            runners=[runner_a, runner_b],
            config=config,
        )
        result = orchestrator.run_suite()

        assert result.passed is True
        assert result.metrics.asr == 0.0
        assert len(result.results) == 2

    def test_run_suite_fails_when_asr_exceeds_threshold(self) -> None:
        runner = MagicMock()
        runner.run.return_value = [_failing_result()]

        config = RedTeamConfig(max_asr=0.05, max_bypass_rate=1.0)
        orchestrator = RedTeamOrchestrator(
            runners=[runner],
            config=config,
        )
        result = orchestrator.run_suite()

        assert result.passed is False
        assert result.metrics.asr == 1.0

    def test_run_suite_fails_when_bypass_exceeds_threshold(self) -> None:
        runner = MagicMock()
        runner.run.return_value = [
            _failing_result(),
            _passing_result(),
        ]

        config = RedTeamConfig(max_asr=1.0, max_bypass_rate=0.3)
        orchestrator = RedTeamOrchestrator(
            runners=[runner],
            config=config,
        )
        result = orchestrator.run_suite()

        assert result.passed is False

    def test_run_suite_aggregates_results_from_all_runners(self) -> None:
        runner_a = MagicMock()
        runner_a.run.return_value = [_passing_result()]
        runner_b = MagicMock()
        runner_b.run.return_value = [_passing_result(), _passing_result()]

        config = RedTeamConfig()
        orchestrator = RedTeamOrchestrator(
            runners=[runner_a, runner_b],
            config=config,
        )
        result = orchestrator.run_suite()

        assert len(result.results) == 3
        assert isinstance(result, SuiteResult)

    def test_run_suite_no_runners(self) -> None:
        config = RedTeamConfig()
        orchestrator = RedTeamOrchestrator(runners=[], config=config)
        result = orchestrator.run_suite()
        assert result.passed is True
        assert len(result.results) == 0

    def test_run_suite_calls_all_runners(self) -> None:
        runner_a = MagicMock()
        runner_a.run.return_value = []
        runner_b = MagicMock()
        runner_b.run.return_value = []

        config = RedTeamConfig()
        orchestrator = RedTeamOrchestrator(
            runners=[runner_a, runner_b],
            config=config,
        )
        orchestrator.run_suite()

        runner_a.run.assert_called_once()
        runner_b.run.assert_called_once()
