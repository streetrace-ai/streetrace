"""Tests for guardrail configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from streetrace.guardrails.config import (
    CognitiveMonitorConfig,
    GuardrailsConfig,
    McpGuardConfig,
    PromptProxyConfig,
)


class TestPromptProxyConfig:
    """Verify Prompt Proxy configuration validation."""

    def test_defaults(self) -> None:
        cfg = PromptProxyConfig()
        assert cfg.enabled is True
        assert 0.0 < cfg.warn_threshold < cfg.block_threshold <= 1.0

    def test_custom_thresholds(self) -> None:
        cfg = PromptProxyConfig(
            warn_threshold=0.5, block_threshold=0.8,
        )
        assert cfg.warn_threshold == 0.5
        assert cfg.block_threshold == 0.8

    def test_warn_must_be_less_than_block(self) -> None:
        with pytest.raises(ValidationError):
            PromptProxyConfig(warn_threshold=0.9, block_threshold=0.5)

    def test_threshold_at_zero_invalid(self) -> None:
        with pytest.raises(ValidationError):
            PromptProxyConfig(warn_threshold=0.0)

    def test_threshold_above_one_invalid(self) -> None:
        with pytest.raises(ValidationError):
            PromptProxyConfig(block_threshold=1.1)


class TestMcpGuardConfig:
    """Verify MCP-Guard configuration validation."""

    def test_defaults(self) -> None:
        cfg = McpGuardConfig()
        assert cfg.enabled is True
        assert cfg.trust_threshold > 0.0

    def test_custom_trust_threshold(self) -> None:
        cfg = McpGuardConfig(trust_threshold=0.7)
        assert cfg.trust_threshold == 0.7

    def test_allowlist_denylist(self) -> None:
        cfg = McpGuardConfig(
            server_allowlist=["safe-server"],
            server_denylist=["bad-server"],
        )
        assert cfg.server_allowlist == ["safe-server"]
        assert cfg.server_denylist == ["bad-server"]


class TestCognitiveMonitorConfig:
    """Verify Cognitive Monitor configuration validation."""

    def test_defaults(self) -> None:
        cfg = CognitiveMonitorConfig()
        assert cfg.enabled is True
        assert cfg.min_turns_before_alert >= 1
        assert 0.0 < cfg.warn_threshold < cfg.block_threshold <= 1.0

    def test_warn_must_be_less_than_block(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveMonitorConfig(
                warn_threshold=0.9, block_threshold=0.5,
            )

    def test_min_turns_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveMonitorConfig(min_turns_before_alert=0)


class TestGuardrailsConfig:
    """Verify top-level guardrails configuration."""

    def test_defaults(self) -> None:
        cfg = GuardrailsConfig()
        assert isinstance(cfg.prompt_proxy, PromptProxyConfig)
        assert isinstance(cfg.mcp_guard, McpGuardConfig)
        assert isinstance(cfg.cognitive_monitor, CognitiveMonitorConfig)

    def test_nested_override(self) -> None:
        cfg = GuardrailsConfig(
            prompt_proxy=PromptProxyConfig(warn_threshold=0.4),
        )
        assert cfg.prompt_proxy.warn_threshold == 0.4

    def test_round_trip_dict(self) -> None:
        cfg = GuardrailsConfig()
        data = cfg.model_dump()
        restored = GuardrailsConfig.model_validate(data)
        assert restored == cfg
