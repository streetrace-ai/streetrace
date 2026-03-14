"""Configuration models for enterprise guardrails.

Pydantic models for Prompt Proxy, MCP-Guard, and Cognitive Monitor
configuration with threshold validation.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class PromptProxyConfig(BaseModel):
    """Configure the 3-stage Prompt Proxy pipeline.

    Attributes:
        enabled: Whether the prompt proxy is active.
        warn_threshold: Semantic similarity score that triggers a warning.
        block_threshold: Semantic similarity score that triggers a block.

    """

    enabled: bool = True
    warn_threshold: float = 0.60
    block_threshold: float = 0.85

    @model_validator(mode="after")
    def _validate_thresholds(self) -> PromptProxyConfig:
        """Ensure thresholds are in (0, 1] and warn < block."""
        if self.warn_threshold <= 0.0 or self.warn_threshold > 1.0:
            msg = "warn_threshold must be in (0.0, 1.0]"
            raise ValueError(msg)
        if self.block_threshold <= 0.0 or self.block_threshold > 1.0:
            msg = "block_threshold must be in (0.0, 1.0]"
            raise ValueError(msg)
        if self.warn_threshold >= self.block_threshold:
            msg = "warn_threshold must be less than block_threshold"
            raise ValueError(msg)
        return self


class McpGuardConfig(BaseModel):
    """Configure the 2-stage MCP-Guard pipeline.

    Attributes:
        enabled: Whether MCP-Guard is active.
        trust_threshold: Minimum trust score for tool servers.
        server_allowlist: Servers always allowed (bypass checks).
        server_denylist: Servers always denied.

    """

    enabled: bool = True
    trust_threshold: float = 0.5
    server_allowlist: list[str] = []
    server_denylist: list[str] = []


class CognitiveMonitorConfig(BaseModel):
    """Configure the Cognitive Monitor drift detector.

    Attributes:
        enabled: Whether cognitive drift detection is active.
        warn_threshold: Risk score that triggers a warning.
        block_threshold: Risk score that triggers a block.
        min_turns_before_alert: Minimum conversation turns before alerting.

    """

    enabled: bool = True
    warn_threshold: float = 0.60
    block_threshold: float = 0.85
    min_turns_before_alert: int = 3

    @model_validator(mode="after")
    def _validate_thresholds(self) -> CognitiveMonitorConfig:
        """Ensure thresholds are in (0, 1] and warn < block."""
        if self.warn_threshold <= 0.0 or self.warn_threshold > 1.0:
            msg = "warn_threshold must be in (0.0, 1.0]"
            raise ValueError(msg)
        if self.block_threshold <= 0.0 or self.block_threshold > 1.0:
            msg = "block_threshold must be in (0.0, 1.0]"
            raise ValueError(msg)
        if self.warn_threshold >= self.block_threshold:
            msg = "warn_threshold must be less than block_threshold"
            raise ValueError(msg)
        if self.min_turns_before_alert < 1:
            msg = "min_turns_before_alert must be at least 1"
            raise ValueError(msg)
        return self


class GuardrailsConfig(BaseModel):
    """Top-level guardrails configuration.

    Compose sub-configs for all three proxy layers.
    """

    prompt_proxy: PromptProxyConfig = PromptProxyConfig()
    mcp_guard: McpGuardConfig = McpGuardConfig()
    cognitive_monitor: CognitiveMonitorConfig = CognitiveMonitorConfig()
