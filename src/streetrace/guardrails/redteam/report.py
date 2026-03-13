"""Report generator for red team results.

Generate PR comment and detailed report formats from suite results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from streetrace.guardrails.redteam.orchestrator import SuiteResult

PERCENTAGE_MULTIPLIER = 100.0
"""Multiplier to convert rate (0.0-1.0) to percentage (0-100)."""


class ReportGenerator:
    """Generate formatted reports from red team suite results."""

    @staticmethod
    def generate_pr_comment(suite_result: SuiteResult) -> str:
        """Generate a concise PR comment summarizing results.

        Args:
            suite_result: The completed suite result.

        Returns:
            Formatted PR comment string.

        """
        status = "PASSED" if suite_result.passed else "FAILED"
        asr_pct = suite_result.metrics.asr * PERCENTAGE_MULTIPLIER
        fp_pct = (
            suite_result.metrics.false_positive_rate
            * PERCENTAGE_MULTIPLIER
        )
        fn_pct = (
            suite_result.metrics.false_negative_rate
            * PERCENTAGE_MULTIPLIER
        )
        total = len(suite_result.results)

        lines = [
            f"## Red Team Validation: {status}",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Status | {status} |",
            f"| Total Probes | {total} |",
            f"| ASR | {asr_pct:.1f}% |",
            f"| False Positive Rate | {fp_pct:.1f}% |",
            f"| False Negative Rate | {fn_pct:.1f}% |",
        ]

        return "\n".join(lines)

    @staticmethod
    def generate_detailed_report(suite_result: SuiteResult) -> str:
        """Generate a detailed per-probe report.

        Args:
            suite_result: The completed suite result.

        Returns:
            Formatted detailed report string.

        """
        asr_pct = suite_result.metrics.asr * PERCENTAGE_MULTIPLIER
        fp_pct = (
            suite_result.metrics.false_positive_rate
            * PERCENTAGE_MULTIPLIER
        )
        fn_pct = (
            suite_result.metrics.false_negative_rate
            * PERCENTAGE_MULTIPLIER
        )

        lines = [
            "# Red Team Detailed Report",
            "",
            "## Metrics",
            "",
            f"- ASR: {asr_pct:.1f}%",
            f"- False Positive Rate: {fp_pct:.1f}%",
            f"- False Negative Rate: {fn_pct:.1f}%",
            "",
            "## Per-Probe Results",
            "",
            "| Probe | Expected | Actual | Latency (ms) | Proxy |",
            "|-------|----------|--------|-------------|-------|",
        ]

        lines.extend(
            f"| {r.probe_name} "
            f"| {r.expected_action} "
            f"| {r.actual_action} "
            f"| {r.latency_ms:.1f} "
            f"| {r.proxy} |"
            for r in suite_result.results
        )

        return "\n".join(lines)
