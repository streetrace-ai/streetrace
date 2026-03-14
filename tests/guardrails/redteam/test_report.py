"""Tests for report generator output formats."""

from __future__ import annotations

from streetrace.guardrails.redteam.metrics_collector import (
    MetricsSummary,
    ProbeResult,
)
from streetrace.guardrails.redteam.orchestrator import SuiteResult
from streetrace.guardrails.redteam.report import ReportGenerator
from streetrace.guardrails.types import GuardrailAction


def _make_suite_result(
    *,
    passed: bool = True,
    asr: float = 0.05,
    fp_rate: float = 0.02,
    fn_rate: float = 0.03,
) -> SuiteResult:
    metrics = MetricsSummary(
        asr=asr,
        false_positive_rate=fp_rate,
        false_negative_rate=fn_rate,
        bypass_rate_per_proxy={"prompt_proxy": 0.04},
    )
    results = [
        ProbeResult(
            probe_name="sql-injection",
            expected_action=GuardrailAction.BLOCK,
            actual_action=GuardrailAction.BLOCK,
            latency_ms=12.5,
            proxy="prompt_proxy",
        ),
        ProbeResult(
            probe_name="encoding-bypass",
            expected_action=GuardrailAction.BLOCK,
            actual_action=GuardrailAction.ALLOW,
            latency_ms=8.3,
            proxy="prompt_proxy",
        ),
    ]
    return SuiteResult(passed=passed, metrics=metrics, results=results)


class TestReportGenerator:
    """Verify report generation formats."""

    def test_pr_comment_includes_pass_status(self) -> None:
        suite_result = _make_suite_result(passed=True)
        comment = ReportGenerator.generate_pr_comment(suite_result)
        assert "PASSED" in comment

    def test_pr_comment_includes_fail_status(self) -> None:
        suite_result = _make_suite_result(passed=False)
        comment = ReportGenerator.generate_pr_comment(suite_result)
        assert "FAILED" in comment

    def test_pr_comment_includes_asr(self) -> None:
        suite_result = _make_suite_result(asr=0.05)
        comment = ReportGenerator.generate_pr_comment(suite_result)
        assert "5.0%" in comment

    def test_pr_comment_includes_fp_rate(self) -> None:
        suite_result = _make_suite_result(fp_rate=0.02)
        comment = ReportGenerator.generate_pr_comment(suite_result)
        assert "2.0%" in comment

    def test_detailed_report_includes_per_probe_results(self) -> None:
        suite_result = _make_suite_result()
        report = ReportGenerator.generate_detailed_report(suite_result)
        assert "sql-injection" in report
        assert "encoding-bypass" in report

    def test_detailed_report_includes_expected_and_actual(self) -> None:
        suite_result = _make_suite_result()
        report = ReportGenerator.generate_detailed_report(suite_result)
        assert "block" in report
        assert "allow" in report

    def test_detailed_report_includes_metrics_section(self) -> None:
        suite_result = _make_suite_result()
        report = ReportGenerator.generate_detailed_report(suite_result)
        assert "ASR" in report
        assert "False Positive" in report
        assert "False Negative" in report

    def test_pr_comment_returns_string(self) -> None:
        suite_result = _make_suite_result()
        comment = ReportGenerator.generate_pr_comment(suite_result)
        assert isinstance(comment, str)
        assert len(comment) > 0

    def test_detailed_report_returns_string(self) -> None:
        suite_result = _make_suite_result()
        report = ReportGenerator.generate_detailed_report(suite_result)
        assert isinstance(report, str)
        assert len(report) > 0
