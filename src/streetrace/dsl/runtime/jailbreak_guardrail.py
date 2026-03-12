"""Jailbreak detection guardrail.

Detect common prompt injection attempts using regex patterns.
This is a check-only guardrail — masking returns text unchanged.
"""

from __future__ import annotations

import re

from streetrace.log import get_logger

logger = get_logger(__name__)

_JAILBREAK_PATTERNS = [
    re.compile(r"ignore.*(?:previous|all).*instructions", re.IGNORECASE),
    re.compile(r"(?:you are|act as).*(?:DAN|do anything)", re.IGNORECASE),
    re.compile(r"pretend.*(?:no|without).*(?:restrictions|rules)", re.IGNORECASE),
    re.compile(
        r"(?:show|reveal|what is).*(?:system|initial).*(?:prompt|instruction)",
        re.IGNORECASE,
    ),
    re.compile(r"bypass.*(?:safety|security|restrictions)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"ignore.*(?:ethics|guidelines|policies)", re.IGNORECASE),
]
"""Patterns to detect common jailbreak attempts."""


class JailbreakGuardrail:
    """Detect jailbreak attempts using regex patterns.

    This is a check-only guardrail. ``mask_str`` returns text unchanged;
    ``check_str`` returns ``(True, detail)`` on pattern match.
    """

    @property
    def name(self) -> str:
        """Return the guardrail name."""
        return "jailbreak"

    def mask_str(self, text: str) -> str:
        """Return text unchanged — jailbreak is check-only.

        Args:
            text: Input text.

        Returns:
            The input text unmodified.

        """
        return text

    def check_str(self, text: str) -> tuple[bool, str]:
        """Check if *text* contains a jailbreak pattern.

        Args:
            text: Input text to check.

        Returns:
            Tuple of (triggered, detail) where detail includes
            the matched pattern.

        """
        for pattern in _JAILBREAK_PATTERNS:
            if pattern.search(text):
                logger.warning(
                    "Jailbreak attempt detected: pattern=%s",
                    pattern.pattern,
                )
                return True, (
                    f"triggered: pattern match "
                    f"({pattern.pattern})"
                )
        return False, ""
