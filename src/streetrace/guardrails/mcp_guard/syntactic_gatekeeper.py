"""Syntactic gatekeeper for MCP tool call validation.

Run 6 parallel pattern detectors against tool names and arguments
to detect shell injection, SQL injection, sensitive file access,
shadow hijack, important tag abuse, and cross-origin attacks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from streetrace.log import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Detection:
    """Single detection from a pattern detector.

    Attributes:
        detector_name: Name of the detector that matched.
        matched_text: The text that triggered the match.
        severity: Severity level ('high', 'medium', 'low').

    """

    detector_name: str
    matched_text: str
    severity: str


@dataclass(frozen=True)
class GatekeeperResult:
    """Result of syntactic gatekeeper analysis.

    Attributes:
        triggered: Whether any detector matched.
        detections: List of individual detections.
        severity: Highest severity among detections.

    """

    triggered: bool
    detections: list[Detection] = field(default_factory=list)
    severity: str = ""


# ---------------------------------------------------------------------------
# Pattern definitions for each detector
# ---------------------------------------------------------------------------

_SHELL_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("rm_rf", re.compile(r"\brm\s+-[a-z]*r[a-z]*f[a-z]*\s", re.IGNORECASE)),
    ("curl_pipe_shell", re.compile(
        r"\bcurl\b.*\|\s*(?:ba)?sh\b", re.IGNORECASE,
    )),
    ("eval_command", re.compile(
        r"\beval\s+\$?\(", re.IGNORECASE,
    )),
    ("backtick_exec", re.compile(
        r"`[^`]*(?:curl|wget|rm|chmod|chown|cat)\b[^`]*`", re.IGNORECASE,
    )),
    ("wget_exec", re.compile(
        r"\bwget\b.*\|\s*(?:ba)?sh\b", re.IGNORECASE,
    )),
    ("chmod_exec", re.compile(
        r"\bchmod\s+[+0-7]*[xst]\S*\s", re.IGNORECASE,
    )),
]

_SQL_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("union_select", re.compile(
        r"(?:\d+|['\"])\s*\bUNION\s+(?:ALL\s+)?SELECT\b", re.IGNORECASE,
    )),
    ("or_tautology", re.compile(
        r"['\"]\s*OR\s+\d+\s*=\s*\d+", re.IGNORECASE,
    )),
    ("drop_table", re.compile(
        r"\bDROP\s+TABLE\b", re.IGNORECASE,
    )),
    ("sql_comment", re.compile(
        r";\s*--\s*$", re.MULTILINE,
    )),
]

_SENSITIVE_FILE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("etc_passwd", re.compile(r"/etc/(?:passwd|shadow|hosts)\b")),
    ("dot_env", re.compile(r"(?:^|/|\\)\.env(?:\s|$|/)", re.MULTILINE)),
    ("ssh_dir", re.compile(r"\.ssh/")),
    ("git_dir", re.compile(r"\.git/")),
    ("aws_credentials", re.compile(
        r"\.aws/(?:credentials|config)\b",
    )),
    ("docker_env", re.compile(r"\.docker/config\.json\b")),
    ("kube_config", re.compile(r"\.kube/config\b")),
]

_SHADOW_HIJACK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("spoofed_call", re.compile(
        r"\bspoofed?_?call\b", re.IGNORECASE,
    )),
    ("fake_server", re.compile(
        r"\bfake_?server\b", re.IGNORECASE,
    )),
    ("instruction_override", re.compile(
        r"\boverride\s+(?:the\s+)?(?:previous\s+)?(?:tool\s+)?instructions?\b",
        re.IGNORECASE,
    )),
    ("instruction_tampering", re.compile(
        r"\btamper(?:ing|ed)?\s+(?:with\s+)?instructions?\b",
        re.IGNORECASE,
    )),
]

_IMPORTANT_TAG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("important_tag", re.compile(
        r"<important\b[^>]*>", re.IGNORECASE,
    )),
    ("system_tag", re.compile(
        r"<system\b[^>]*>", re.IGNORECASE,
    )),
    ("priority_tag", re.compile(
        r"<(?:priority|urgent|critical)\b[^>]*>", re.IGNORECASE,
    )),
]

_CROSS_ORIGIN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("metadata_endpoint", re.compile(
        r"169\.254\.169\.254",
    )),
    ("localhost_access", re.compile(
        r"(?:localhost|127\.0\.0\.1)(?::\d+)?",
    )),
    ("internal_ip_10", re.compile(
        r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    )),
    ("internal_ip_172", re.compile(
        r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b",
    )),
    ("internal_ip_192", re.compile(
        r"\b192\.168\.\d{1,3}\.\d{1,3}\b",
    )),
]

_DETECTOR_REGISTRY: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "shell_injection": _SHELL_INJECTION_PATTERNS,
    "sql_injection": _SQL_INJECTION_PATTERNS,
    "sensitive_file": _SENSITIVE_FILE_PATTERNS,
    "shadow_hijack": _SHADOW_HIJACK_PATTERNS,
    "important_tag": _IMPORTANT_TAG_PATTERNS,
    "cross_origin": _CROSS_ORIGIN_PATTERNS,
}

SEVERITY_MAP: dict[str, str] = {
    "shell_injection": "high",
    "sql_injection": "high",
    "sensitive_file": "high",
    "shadow_hijack": "high",
    "important_tag": "medium",
    "cross_origin": "high",
}
"""Map detector names to severity levels."""

_SEVERITY_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
}
"""Numeric ordering for severity comparison."""


class SyntacticGatekeeper:
    """Run 6 pattern detectors against tool call data.

    Serialize tool name and arguments to text, then scan for
    attack patterns across all detector categories.
    """

    def check(
        self,
        tool_name: str,
        args: dict[str, object],
    ) -> GatekeeperResult:
        """Check tool call against all pattern detectors.

        Args:
            tool_name: Name of the MCP tool being called.
            args: Tool call arguments as a dictionary.

        Returns:
            GatekeeperResult with triggered status and detections.

        """
        text = _serialize_for_scanning(tool_name, args)
        detections: list[Detection] = []

        for detector_name, patterns in _DETECTOR_REGISTRY.items():
            severity = SEVERITY_MAP.get(detector_name, "medium")
            for pattern_name, pattern in patterns:
                match = pattern.search(text)
                if match:
                    detections.append(Detection(
                        detector_name=detector_name,
                        matched_text=match.group(),
                        severity=severity,
                    ))
                    logger.warning(
                        "MCP gatekeeper %s/%s matched: %s",
                        detector_name,
                        pattern_name,
                        match.group(),
                    )

        if not detections:
            return GatekeeperResult(triggered=False)

        highest = _highest_severity(detections)
        return GatekeeperResult(
            triggered=True,
            detections=detections,
            severity=highest,
        )


def _serialize_for_scanning(
    tool_name: str,
    args: dict[str, object],
) -> str:
    """Serialize tool name and args into scannable text.

    Args:
        tool_name: Tool name.
        args: Tool arguments.

    Returns:
        Concatenated string for pattern matching.

    """
    parts = [tool_name]
    for value in args.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            parts.append(json.dumps(value, default=str))
        else:
            parts.append(str(value))
    return "\n".join(parts)


def _highest_severity(detections: list[Detection]) -> str:
    """Return the highest severity among detections.

    Args:
        detections: List of detections to compare.

    Returns:
        Highest severity string.

    """
    max_level = -1
    max_severity = ""
    for d in detections:
        level = _SEVERITY_ORDER.get(d.severity, 0)
        if level > max_level:
            max_level = level
            max_severity = d.severity
    return max_severity
