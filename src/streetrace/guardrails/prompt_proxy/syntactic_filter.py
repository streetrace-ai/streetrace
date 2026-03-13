"""Syntactic filter for pattern-based prompt injection detection.

Run all registered patterns against input text and return matches.
Designed for sub-2ms performance on typical inputs.
"""

from __future__ import annotations

from streetrace.guardrails.prompt_proxy.patterns import (
    PATTERN_REGISTRY,
    PatternMatch,
)
from streetrace.log import get_logger

logger = get_logger(__name__)

SEVERITY_LEVELS: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
}
"""Map severity names to numeric levels for threshold comparison."""


class SyntacticFilter:
    """Run regex patterns against text to detect injection attempts.

    Filter results by configurable severity threshold to control
    sensitivity. Default threshold is 'low' (return all matches).
    """

    def __init__(
        self,
        *,
        severity_threshold: str = "low",
    ) -> None:
        """Initialize the syntactic filter.

        Args:
            severity_threshold: Minimum severity to report.
                One of 'low', 'medium', 'high'.

        """
        self._threshold_level = SEVERITY_LEVELS.get(severity_threshold, 0)

    def check(self, text: str) -> list[PatternMatch]:
        """Check text against all registered patterns.

        Args:
            text: Input text to scan.

        Returns:
            List of pattern matches above the severity threshold.

        """
        matches: list[PatternMatch] = []

        for category, patterns in PATTERN_REGISTRY.items():
            for entry in patterns:
                entry_level = SEVERITY_LEVELS.get(entry.severity, 0)
                if entry_level < self._threshold_level:
                    continue

                m = entry.pattern.search(text)
                if m:
                    matches.append(
                        PatternMatch(
                            category=category,
                            pattern_name=entry.name,
                            severity=entry.severity,
                            matched_text=m.group(),
                        ),
                    )

        if matches:
            logger.warning(
                "Syntactic filter matched %d pattern(s): %s",
                len(matches),
                ", ".join(f"{m.category}/{m.pattern_name}" for m in matches),
            )

        return matches
