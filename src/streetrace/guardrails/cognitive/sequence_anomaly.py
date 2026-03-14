"""Sequence anomaly detector for suspicious tool-use patterns.

Detect suspicious sequences of tool calls that individually appear
benign but collectively suggest adversarial intent (e.g., data
exfiltration: read_file -> encode -> send_email).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

from streetrace.log import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SequencePattern:
    """Define a suspicious tool-use sequence pattern.

    Attributes:
        name: Pattern identifier (e.g., 'data_exfiltration').
        sequence: Ordered list of tool names. Supports '*' wildcard
            and glob patterns like 'encode_*'.

    """

    name: str
    sequence: list[str]


@dataclass(frozen=True)
class SequenceResult:
    """Result of sequence anomaly check.

    Attributes:
        detected: Whether a suspicious sequence was found.
        pattern_name: Name of the matched pattern, empty if none.
        sequence: The tool call sequence that matched.

    """

    detected: bool
    pattern_name: str = ""
    sequence: list[str] = field(default_factory=list)


_NO_MATCH = SequenceResult(detected=False)


class SequenceAnomalyDetector:
    """Detect suspicious tool-use sequences.

    Maintain a sliding window of recent tool calls and check
    against configured suspicious patterns.
    """

    def __init__(
        self, *, patterns: list[SequencePattern],
    ) -> None:
        """Initialize with pattern definitions.

        Args:
            patterns: List of suspicious sequence patterns.

        """
        self._patterns = patterns
        self._history: list[str] = []
        # Maximum sequence length to track
        self._max_window = max(
            (len(p.sequence) for p in patterns), default=0,
        )

    def record_tool_call(self, tool_name: str) -> SequenceResult:
        """Record a tool call and check for suspicious sequences.

        Args:
            tool_name: Name of the tool that was called.

        Returns:
            SequenceResult indicating whether a pattern was matched.

        """
        self._history.append(tool_name)

        # Trim history to max window size
        if self._max_window > 0 and len(self._history) > self._max_window:
            self._history = self._history[-self._max_window:]

        for pattern in self._patterns:
            if self._matches_pattern(pattern):
                logger.warning(
                    "Suspicious sequence detected: %s", pattern.name,
                )
                seq_len = len(pattern.sequence)
                matched_seq = self._history[-seq_len:]
                return SequenceResult(
                    detected=True,
                    pattern_name=pattern.name,
                    sequence=list(matched_seq),
                )

        return _NO_MATCH

    def reset(self) -> None:
        """Clear tool call history."""
        self._history.clear()

    def _matches_pattern(self, pattern: SequencePattern) -> bool:
        """Check if recent history matches a pattern.

        Args:
            pattern: Pattern to check against.

        Returns:
            True if the pattern matches the tail of history.

        """
        seq = pattern.sequence
        if len(self._history) < len(seq):
            return False

        tail = self._history[-len(seq):]
        return all(
            _tool_matches(actual, expected)
            for actual, expected in zip(tail, seq, strict=True)
        )


def _tool_matches(actual: str, pattern: str) -> bool:
    """Check if a tool name matches a pattern element.

    Supports exact match, '*' wildcard (any tool), and glob
    patterns like 'encode_*'.

    Args:
        actual: Actual tool name.
        pattern: Pattern element from sequence definition.

    Returns:
        True if actual matches pattern.

    """
    if pattern == "*":
        return True
    if "*" in pattern or "?" in pattern:
        return fnmatch.fnmatch(actual, pattern)
    return actual == pattern
