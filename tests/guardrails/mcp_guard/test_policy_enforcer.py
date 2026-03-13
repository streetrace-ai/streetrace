"""Tests for PolicyEnforcer: allowlist/denylist, rate limits, data boundaries."""

from __future__ import annotations

from streetrace.guardrails.config import McpGuardConfig
from streetrace.guardrails.mcp_guard.policy_enforcer import PolicyEnforcer


class TestAllowlistDenylist:
    """Verify allowlist and denylist enforcement."""

    def test_denied_server_blocked(self) -> None:
        """Server on denylist is immediately blocked."""
        config = McpGuardConfig(server_denylist=["evil-server"])
        enforcer = PolicyEnforcer(config=config)
        result = enforcer.check(
            server_id="evil-server",
            tool_name="any_tool",
        )
        assert result.allowed is False
        assert "denied" in result.reason.lower()

    def test_allowed_server_passes(self) -> None:
        """Server on allowlist bypasses checks."""
        config = McpGuardConfig(server_allowlist=["trusted-server"])
        enforcer = PolicyEnforcer(config=config)
        result = enforcer.check(
            server_id="trusted-server",
            tool_name="any_tool",
        )
        assert result.allowed is True

    def test_unlisted_server_allowed_by_default(self) -> None:
        """Server not on any list is allowed by default."""
        config = McpGuardConfig()
        enforcer = PolicyEnforcer(config=config)
        result = enforcer.check(
            server_id="normal-server",
            tool_name="any_tool",
        )
        assert result.allowed is True

    def test_denylist_takes_precedence(self) -> None:
        """Denylist takes precedence over allowlist."""
        config = McpGuardConfig(
            server_allowlist=["server-x"],
            server_denylist=["server-x"],
        )
        enforcer = PolicyEnforcer(config=config)
        result = enforcer.check(
            server_id="server-x",
            tool_name="any_tool",
        )
        assert result.allowed is False


class TestRateLimiting:
    """Verify rate limit enforcement."""

    def test_rate_limit_blocks_after_threshold(self) -> None:
        """Calls exceeding rate limit are blocked."""
        config = McpGuardConfig()
        enforcer = PolicyEnforcer(config=config, max_calls_per_tool=3)

        for _ in range(3):
            result = enforcer.check(
                server_id="server-a",
                tool_name="fast_tool",
            )
            assert result.allowed is True

        result = enforcer.check(
            server_id="server-a",
            tool_name="fast_tool",
        )
        assert result.allowed is False
        assert "rate" in result.reason.lower()

    def test_different_tools_have_separate_limits(self) -> None:
        """Rate limits are tracked per tool."""
        config = McpGuardConfig()
        enforcer = PolicyEnforcer(config=config, max_calls_per_tool=2)

        for _ in range(2):
            enforcer.check(server_id="s", tool_name="tool_a")

        # tool_b should still be allowed
        result = enforcer.check(server_id="s", tool_name="tool_b")
        assert result.allowed is True


class TestDataBoundaryEnforcement:
    """Verify data boundary pattern detection in args."""

    def test_detects_credential_in_args(self) -> None:
        """Credential patterns in tool args are blocked."""
        config = McpGuardConfig()
        enforcer = PolicyEnforcer(config=config)
        result = enforcer.check(
            server_id="server",
            tool_name="send",
            args={"body": "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE"},
        )
        assert result.allowed is False
        assert "data boundary" in result.reason.lower()

    def test_clean_args_pass(self) -> None:
        """Clean args without credential patterns pass."""
        config = McpGuardConfig()
        enforcer = PolicyEnforcer(config=config)
        result = enforcer.check(
            server_id="server",
            tool_name="send",
            args={"body": "Hello, world!"},
        )
        assert result.allowed is True


class TestPolicyResult:
    """Verify PolicyResult structure."""

    def test_result_has_required_fields(self) -> None:
        """PolicyResult has allowed and reason fields."""
        config = McpGuardConfig()
        enforcer = PolicyEnforcer(config=config)
        result = enforcer.check(
            server_id="server",
            tool_name="tool",
        )
        assert hasattr(result, "allowed")
        assert hasattr(result, "reason")
        assert isinstance(result.allowed, bool)
        assert isinstance(result.reason, str)
