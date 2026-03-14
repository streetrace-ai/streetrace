"""Policy enforcer for MCP tool call validation.

Enforce allowlist/denylist policies, rate limits, and data
boundary rules for MCP tool calls.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.guardrails.config import McpGuardConfig

logger = get_logger(__name__)

DEFAULT_MAX_CALLS_PER_TOOL = 100
"""Default maximum calls per tool per session."""

_DATA_BOUNDARY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_secret", re.compile(
        r"(?:AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN)\s*=",
        re.IGNORECASE,
    )),
    ("api_key", re.compile(
        r"(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|API_KEY)\s*=",
        re.IGNORECASE,
    )),
    ("private_key", re.compile(
        r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----",
    )),
    ("password_field", re.compile(
        r"(?:password|passwd|secret)\s*[:=]\s*\S+",
        re.IGNORECASE,
    )),
]
"""Patterns for detecting credential exfiltration in arguments."""


@dataclass(frozen=True)
class PolicyResult:
    """Result of policy enforcement.

    Attributes:
        allowed: Whether the tool call is allowed.
        reason: Explanation of the decision.

    """

    allowed: bool
    reason: str


class PolicyEnforcer:
    """Enforce allowlist/denylist, rate limits, and data boundaries.

    Check each tool call against configured policies before
    allowing it to proceed to syntactic/neural stages.
    """

    def __init__(
        self,
        *,
        config: McpGuardConfig,
        max_calls_per_tool: int = DEFAULT_MAX_CALLS_PER_TOOL,
    ) -> None:
        """Initialize the policy enforcer.

        Args:
            config: MCP-Guard configuration with lists and thresholds.
            max_calls_per_tool: Maximum calls per tool before rate limiting.

        """
        self._config = config
        self._max_calls = max_calls_per_tool
        self._call_counts: dict[str, int] = {}

    def check(
        self,
        *,
        server_id: str,
        tool_name: str,
        args: dict[str, object] | None = None,
    ) -> PolicyResult:
        """Check a tool call against all policies.

        Evaluation order: denylist -> allowlist -> rate limit
        -> data boundaries.

        Args:
            server_id: MCP server identifier.
            tool_name: Name of the tool being called.
            args: Tool call arguments (optional).

        Returns:
            PolicyResult with allowed status and reason.

        """
        # Check denylist first (takes precedence)
        if server_id in self._config.server_denylist:
            logger.warning(
                "Server %s is on denylist, blocking %s",
                server_id,
                tool_name,
            )
            return PolicyResult(
                allowed=False,
                reason=f"Server '{server_id}' is denied by policy",
            )

        # Check allowlist (bypass remaining checks)
        if (
            self._config.server_allowlist
            and server_id in self._config.server_allowlist
        ):
            return PolicyResult(
                allowed=True,
                reason=f"Server '{server_id}' is on allowlist",
            )

        # Rate limiting
        rate_result = self._check_rate_limit(server_id, tool_name)
        if not rate_result.allowed:
            return rate_result

        # Data boundary enforcement
        if args is not None:
            boundary_result = self._check_data_boundaries(args)
            if not boundary_result.allowed:
                return boundary_result

        return PolicyResult(
            allowed=True,
            reason="Policy checks passed",
        )

    def _check_rate_limit(
        self,
        server_id: str,
        tool_name: str,
    ) -> PolicyResult:
        """Check and update rate limit for a tool.

        Args:
            server_id: Server identifier.
            tool_name: Tool name.

        Returns:
            PolicyResult indicating if rate limit is exceeded.

        """
        key = f"{server_id}:{tool_name}"
        current = self._call_counts.get(key, 0)

        if current >= self._max_calls:
            logger.warning(
                "Rate limit exceeded for %s on %s: %d/%d",
                tool_name,
                server_id,
                current,
                self._max_calls,
            )
            return PolicyResult(
                allowed=False,
                reason=(
                    f"Rate limit exceeded for '{tool_name}' "
                    f"on server '{server_id}': "
                    f"{current}/{self._max_calls} calls"
                ),
            )

        self._call_counts[key] = current + 1
        return PolicyResult(
            allowed=True,
            reason="Within rate limit",
        )

    def _check_data_boundaries(
        self,
        args: dict[str, object],
    ) -> PolicyResult:
        """Check tool arguments for data boundary violations.

        Scan serialized arguments for credential patterns and
        other sensitive data that should not leave the system.

        Args:
            args: Tool call arguments.

        Returns:
            PolicyResult indicating if boundaries are violated.

        """
        text = json.dumps(args, default=str)

        for pattern_name, pattern in _DATA_BOUNDARY_PATTERNS:
            match = pattern.search(text)
            if match:
                logger.warning(
                    "Data boundary violation: %s matched in tool args",
                    pattern_name,
                )
                return PolicyResult(
                    allowed=False,
                    reason=(
                        f"Data boundary violation: "
                        f"{pattern_name} pattern detected in arguments"
                    ),
                )

        return PolicyResult(
            allowed=True,
            reason="Data boundary checks passed",
        )
