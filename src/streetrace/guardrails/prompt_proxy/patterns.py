"""Pattern registry for syntactic prompt injection detection.

Organize compiled regex patterns by attack category with severity
levels. Patterns are designed to minimize false positives on
documentation and technical discussion text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PatternMatch:
    """Result of a pattern match against input text.

    Attributes:
        category: Attack category (e.g., 'shell_injection').
        pattern_name: Name of the matched pattern.
        severity: Severity level ('high', 'medium', 'low').
        matched_text: The text that triggered the match.

    """

    category: str
    pattern_name: str
    severity: str
    matched_text: str


@dataclass(frozen=True)
class PatternEntry:
    """A single pattern in the registry.

    Attributes:
        name: Human-readable pattern identifier.
        pattern: Compiled regex pattern.
        severity: Severity level ('high', 'medium', 'low').

    """

    name: str
    pattern: re.Pattern[str]
    severity: str


# ---------------------------------------------------------------------------
# Instruction override patterns
#
# These patterns detect direct prompt injection attempts that try to
# override system instructions. They are tightened compared to the
# original 7 patterns in jailbreak_guardrail.py to reduce false
# positives on documentation text that *discusses* these attacks.
#
# Key design: require imperative/directive phrasing rather than
# descriptive/documentary phrasing. For example, "ignore previous
# instructions" as a command triggers, but "patterns like 'ignore
# previous instructions'" does not (because it's inside quotes or
# preceded by documentary context).
# ---------------------------------------------------------------------------

_INSTRUCTION_OVERRIDE_PATTERNS: list[PatternEntry] = [
    PatternEntry(
        name="ignore_instructions",
        pattern=re.compile(
            r"(?<!['\"])"  # not preceded by a quote
            r"\bignore\s+"
            r"(?:"
            r"(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions?"
            r"|"
            r"all\s+instructions?"
            r"|"
            r"instructions?\s+(?:above|below|previously|given)"
            r")\b",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="dan_jailbreak",
        pattern=re.compile(
            r"(?:you\s+are\s+(?:now\s+)?|act\s+as\s+)"
            r"(?:DAN|do\s+anything\s+now)",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="pretend_no_restrictions",
        pattern=re.compile(
            r"\bpretend\s+(?:you\s+)?(?:have\s+)?no\s+"
            r"(?:restrictions?|rules?|limits?|boundaries)\b",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="reveal_system_prompt",
        pattern=re.compile(
            r"\b(?:show|reveal|display|print|output|give|what\s+is)\s+"
            r"(?:me\s+)?(?:your\s+)?(?:the\s+)?"
            r"(?:system|initial|original|hidden)\s+"
            r"(?:prompt|instructions?|message)s?\b",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="bypass_safety",
        pattern=re.compile(
            r"(?<!['\"])\bbypass\s+(?:the\s+)?(?:your\s+)?"
            r"(?:safety|security|content|restriction|filter)s?\b",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="ignore_ethics",
        pattern=re.compile(
            r"(?<!['\"])\bignore\s+(?:your\s+)?(?:the\s+)?"
            r"(?:ethic(?:al|s)?|guideline|polic(?:y|ies))\b",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="new_instructions",
        pattern=re.compile(
            r"(?:^|\n)\s*(?:new|updated|revised|override)\s+"
            r"instructions?\s*:",
            re.IGNORECASE,
        ),
        severity="high",
    ),
]

# ---------------------------------------------------------------------------
# Shell injection patterns
# ---------------------------------------------------------------------------

_SHELL_INJECTION_PATTERNS: list[PatternEntry] = [
    PatternEntry(
        name="rm_rf",
        pattern=re.compile(
            r"\brm\s+-[a-z]*r[a-z]*f[a-z]*\s",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="curl_pipe_shell",
        pattern=re.compile(
            r"\bcurl\b.*\|\s*(?:ba)?sh\b",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="backtick_execution",
        pattern=re.compile(
            r"`[^`]*(?:cat|curl|wget|rm|chmod|chown|dd|mkfs)\b[^`]*`",
            re.IGNORECASE,
        ),
        severity="medium",
    ),
    PatternEntry(
        name="dollar_command_sub",
        pattern=re.compile(
            r"\$\([^)]*(?:cat|curl|wget|rm|chmod|chown)\b[^)]*\)",
            re.IGNORECASE,
        ),
        severity="medium",
    ),
]

# ---------------------------------------------------------------------------
# SQL injection patterns
# ---------------------------------------------------------------------------

_SQL_INJECTION_PATTERNS: list[PatternEntry] = [
    PatternEntry(
        name="union_select",
        pattern=re.compile(
            r"(?:\d+|['\"])\s*\bUNION\s+(?:ALL\s+)?SELECT\b",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="or_tautology",
        pattern=re.compile(
            r"['\"]\s*OR\s+\d+\s*=\s*\d+",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="drop_table",
        pattern=re.compile(
            r"\bDROP\s+TABLE\b",
            re.IGNORECASE,
        ),
        severity="high",
    ),
    PatternEntry(
        name="sql_comment_terminator",
        pattern=re.compile(
            r";\s*--\s*$",
            re.MULTILINE,
        ),
        severity="medium",
    ),
]

# ---------------------------------------------------------------------------
# Path traversal patterns
# ---------------------------------------------------------------------------

_PATH_TRAVERSAL_PATTERNS: list[PatternEntry] = [
    PatternEntry(
        name="dot_dot_slash",
        pattern=re.compile(
            r"\.\./\.\./",
        ),
        severity="high",
    ),
    PatternEntry(
        name="etc_passwd",
        pattern=re.compile(
            r"/etc/(?:passwd|shadow|hosts)\b",
        ),
        severity="high",
    ),
    PatternEntry(
        name="dot_env_file",
        pattern=re.compile(
            r"(?:^|\s|/)\.env\s",
            re.MULTILINE,
        ),
        severity="medium",
    ),
    PatternEntry(
        name="ssh_directory",
        pattern=re.compile(
            r"\.ssh/",
        ),
        severity="high",
    ),
]

# ---------------------------------------------------------------------------
# Encoding attack patterns
# ---------------------------------------------------------------------------

_ENCODING_ATTACK_PATTERNS: list[PatternEntry] = [
    PatternEntry(
        name="base64_payload",
        pattern=re.compile(
            r"\bbase64\b.*[A-Za-z0-9+/]{12,}={0,2}",
            re.IGNORECASE,
        ),
        severity="medium",
    ),
    PatternEntry(
        name="hex_escape_sequence",
        pattern=re.compile(
            r"(?:\\x[0-9a-fA-F]{2}){4,}",
        ),
        severity="medium",
    ),
    PatternEntry(
        name="unicode_escape_sequence",
        pattern=re.compile(
            r"(?:\\u[0-9a-fA-F]{4}){4,}",
        ),
        severity="medium",
    ),
]

# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

PATTERN_REGISTRY: dict[str, list[PatternEntry]] = {
    "instruction_override": _INSTRUCTION_OVERRIDE_PATTERNS,
    "shell_injection": _SHELL_INJECTION_PATTERNS,
    "sql_injection": _SQL_INJECTION_PATTERNS,
    "path_traversal": _PATH_TRAVERSAL_PATTERNS,
    "encoding_attack": _ENCODING_ATTACK_PATTERNS,
}
"""Pattern registry organized by attack category."""
