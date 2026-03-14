"""Tests for metrics collector ASR, FP, FN, and bypass rate computation."""

from __future__ import annotations

from streetrace.guardrails.redteam.metrics_collector import (
    MetricsCollector,
    MetricsSummary,
    ProbeResult,
)
from streetrace.guardrails.types import GuardrailAction


def _attack_result(
    *,
    probe_name: str = "probe",
    expected: GuardrailAction = GuardrailAction.BLOCK,
    actual: GuardrailAction = GuardrailAction.BLOCK,
    latency_ms: float = 10.0,
    proxy: str = "prompt_proxy",
) -> ProbeResult:
    """Create a ProbeResult for testing."""
    return ProbeResult(
        probe_name=probe_name,
        expected_action=expected,
        actual_action=actual,
        latency_ms=latency_ms,
        proxy=proxy,
    )


class TestMetricsCollector:
    """Verify metrics computation from probe results."""

    def test_asr_all_blocked(self) -> None:
        results = [
            _attack_result(actual=GuardrailAction.BLOCK),
            _attack_result(actual=GuardrailAction.BLOCK),
        ]
        summary = MetricsCollector.compute(results)
        assert summary.asr == 0.0

    def test_asr_all_bypassed(self) -> None:
        results = [
            _attack_result(actual=GuardrailAction.ALLOW),
            _attack_result(actual=GuardrailAction.ALLOW),
        ]
        summary = MetricsCollector.compute(results)
        assert summary.asr == 1.0

    def test_asr_partial_bypass(self) -> None:
        results = [
            _attack_result(actual=GuardrailAction.BLOCK),
            _attack_result(actual=GuardrailAction.ALLOW),
            _attack_result(actual=GuardrailAction.BLOCK),
            _attack_result(actual=GuardrailAction.ALLOW),
        ]
        summary = MetricsCollector.compute(results)
        assert summary.asr == 0.5

    def test_asr_warn_counts_as_detected(self) -> None:
        results = [
            _attack_result(actual=GuardrailAction.WARN),
            _attack_result(actual=GuardrailAction.BLOCK),
        ]
        summary = MetricsCollector.compute(results)
        assert summary.asr == 0.0

    def test_false_positive_rate(self) -> None:
        results = [
            _attack_result(
                expected=GuardrailAction.ALLOW,
                actual=GuardrailAction.BLOCK,
            ),
            _attack_result(
                expected=GuardrailAction.ALLOW,
                actual=GuardrailAction.ALLOW,
            ),
            _attack_result(
                expected=GuardrailAction.ALLOW,
                actual=GuardrailAction.ALLOW,
            ),
        ]
        summary = MetricsCollector.compute(results)
        assert abs(summary.false_positive_rate - 1.0 / 3.0) < 1e-9

    def test_false_negative_rate(self) -> None:
        results = [
            _attack_result(
                expected=GuardrailAction.BLOCK,
                actual=GuardrailAction.ALLOW,
            ),
            _attack_result(
                expected=GuardrailAction.BLOCK,
                actual=GuardrailAction.BLOCK,
            ),
        ]
        summary = MetricsCollector.compute(results)
        assert summary.false_negative_rate == 0.5

    def test_bypass_rate_per_proxy(self) -> None:
        results = [
            _attack_result(
                proxy="prompt_proxy",
                actual=GuardrailAction.ALLOW,
            ),
            _attack_result(
                proxy="prompt_proxy",
                actual=GuardrailAction.BLOCK,
            ),
            _attack_result(
                proxy="mcp_guard",
                actual=GuardrailAction.ALLOW,
            ),
        ]
        summary = MetricsCollector.compute(results)
        assert summary.bypass_rate_per_proxy["prompt_proxy"] == 0.5
        assert summary.bypass_rate_per_proxy["mcp_guard"] == 1.0

    def test_empty_results(self) -> None:
        summary = MetricsCollector.compute([])
        assert summary.asr == 0.0
        assert summary.false_positive_rate == 0.0
        assert summary.false_negative_rate == 0.0
        assert summary.bypass_rate_per_proxy == {}

    def test_no_benign_probes(self) -> None:
        results = [
            _attack_result(
                expected=GuardrailAction.BLOCK,
                actual=GuardrailAction.BLOCK,
            ),
        ]
        summary = MetricsCollector.compute(results)
        assert summary.false_positive_rate == 0.0

    def test_no_attack_probes(self) -> None:
        results = [
            _attack_result(
                expected=GuardrailAction.ALLOW,
                actual=GuardrailAction.ALLOW,
            ),
        ]
        summary = MetricsCollector.compute(results)
        assert summary.false_negative_rate == 0.0

    def test_summary_is_dataclass(self) -> None:
        summary = MetricsCollector.compute([])
        assert isinstance(summary, MetricsSummary)
