"""Tests for guardrail result types and enums."""

from __future__ import annotations

import pytest

from streetrace.guardrails.types import GuardrailAction, GuardrailResult


class TestGuardrailAction:
    """Verify enum values for guardrail actions."""

    def test_allow_value(self) -> None:
        assert GuardrailAction.ALLOW == "allow"

    def test_warn_value(self) -> None:
        assert GuardrailAction.WARN == "warn"

    def test_block_value(self) -> None:
        assert GuardrailAction.BLOCK == "block"

    def test_all_members(self) -> None:
        members = {m.value for m in GuardrailAction}
        assert members == {"allow", "warn", "block"}


class TestGuardrailResult:
    """Verify GuardrailResult construction and validation."""

    def test_construction_with_all_fields(self) -> None:
        result = GuardrailResult(
            action=GuardrailAction.BLOCK,
            confidence=0.95,
            detail="injection detected",
            stage="syntactic",
            proxy="prompt_proxy",
        )
        assert result.action == GuardrailAction.BLOCK
        assert result.confidence == 0.95
        assert result.detail == "injection detected"
        assert result.stage == "syntactic"
        assert result.proxy == "prompt_proxy"

    def test_construction_minimal(self) -> None:
        result = GuardrailResult(action=GuardrailAction.ALLOW)
        assert result.action == GuardrailAction.ALLOW
        assert result.confidence == 0.0
        assert result.detail == ""
        assert result.stage == ""
        assert result.proxy == ""

    def test_confidence_clamped_above_one(self) -> None:
        result = GuardrailResult(
            action=GuardrailAction.WARN, confidence=1.5,
        )
        assert result.confidence == 1.0

    def test_confidence_clamped_below_zero(self) -> None:
        result = GuardrailResult(
            action=GuardrailAction.WARN, confidence=-0.3,
        )
        assert result.confidence == 0.0

    def test_confidence_at_boundaries(self) -> None:
        assert GuardrailResult(
            action=GuardrailAction.ALLOW, confidence=0.0,
        ).confidence == 0.0
        assert GuardrailResult(
            action=GuardrailAction.ALLOW, confidence=1.0,
        ).confidence == 1.0

    def test_is_triggered_block(self) -> None:
        result = GuardrailResult(action=GuardrailAction.BLOCK)
        assert result.is_triggered is True

    def test_is_triggered_warn(self) -> None:
        result = GuardrailResult(action=GuardrailAction.WARN)
        assert result.is_triggered is True

    def test_is_triggered_allow(self) -> None:
        result = GuardrailResult(action=GuardrailAction.ALLOW)
        assert result.is_triggered is False

    def test_result_is_immutable(self) -> None:
        result = GuardrailResult(action=GuardrailAction.ALLOW)
        with pytest.raises(AttributeError):
            result.action = GuardrailAction.BLOCK  # type: ignore[misc]
