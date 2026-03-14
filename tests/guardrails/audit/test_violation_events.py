"""Tests for violation event models and OTEL attribute mapping."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from streetrace.guardrails.audit.violation_events import (
    DriftViolation,
    PromptViolation,
    RecoveryEvent,
    ToolViolation,
    ViolationEvent,
    ViolationSeverity,
)
from streetrace.guardrails.types import GuardrailAction


class TestViolationSeverity:
    """Verify severity enum values."""

    def test_severity_values(self) -> None:
        assert ViolationSeverity.INFO == "info"
        assert ViolationSeverity.WARNING == "warning"
        assert ViolationSeverity.CRITICAL == "critical"

    def test_all_members(self) -> None:
        members = {m.value for m in ViolationSeverity}
        assert members == {"info", "warning", "critical"}


class TestViolationEvent:
    """Verify base violation event schema."""

    def test_required_fields_present(self) -> None:
        event = ViolationEvent(
            severity=ViolationSeverity.WARNING,
            action=GuardrailAction.WARN,
            guardrail_name="jailbreak",
            detail="injection detected",
        )
        assert event.severity == ViolationSeverity.WARNING
        assert event.action == GuardrailAction.WARN
        assert event.guardrail_name == "jailbreak"
        assert event.detail == "injection detected"

    def test_violation_id_auto_generated(self) -> None:
        event = ViolationEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="test",
            detail="test",
        )
        # Should be a valid UUID
        parsed = uuid.UUID(event.violation_id)
        assert str(parsed) == event.violation_id

    def test_violation_ids_are_unique(self) -> None:
        e1 = ViolationEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="test",
            detail="test",
        )
        e2 = ViolationEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="test",
            detail="test",
        )
        assert e1.violation_id != e2.violation_id

    def test_timestamp_auto_generated(self) -> None:
        before = datetime.now(tz=UTC)
        event = ViolationEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="test",
            detail="test",
        )
        after = datetime.now(tz=UTC)
        assert before <= event.timestamp <= after

    def test_confidence_defaults_to_zero(self) -> None:
        event = ViolationEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="test",
            detail="test",
        )
        assert event.confidence == 0.0

    def test_confidence_set_explicitly(self) -> None:
        event = ViolationEvent(
            severity=ViolationSeverity.CRITICAL,
            action=GuardrailAction.BLOCK,
            guardrail_name="jailbreak",
            detail="blocked",
            confidence=0.95,
        )
        assert event.confidence == 0.95

    def test_to_otel_attributes(self) -> None:
        event = ViolationEvent(
            severity=ViolationSeverity.CRITICAL,
            action=GuardrailAction.BLOCK,
            guardrail_name="jailbreak",
            detail="injection detected",
            confidence=0.92,
        )
        attrs = event.to_otel_attributes()

        assert attrs["streetrace.guardrail.violation.id"] == event.violation_id
        assert attrs["streetrace.guardrail.violation.severity"] == "critical"
        assert attrs["streetrace.guardrail.violation.action"] == "block"
        assert attrs["streetrace.guardrail.violation.guardrail_name"] == "jailbreak"
        assert attrs["streetrace.guardrail.violation.detail"] == "injection detected"
        assert attrs["streetrace.guardrail.violation.confidence"] == 0.92

    def test_to_otel_attributes_types(self) -> None:
        event = ViolationEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="test",
            detail="ok",
            confidence=0.5,
        )
        attrs = event.to_otel_attributes()
        for key, val in attrs.items():
            assert isinstance(key, str)
            assert isinstance(val, (str, float, bool))


class TestPromptViolation:
    """Verify prompt proxy violation event."""

    def test_includes_prompt_specific_fields(self) -> None:
        event = PromptViolation(
            severity=ViolationSeverity.CRITICAL,
            action=GuardrailAction.BLOCK,
            guardrail_name="jailbreak",
            detail="syntactic match",
            stage="syntactic",
            pattern_matched="ignore.*instructions",
            embedding_score=0.0,
        )
        assert event.stage == "syntactic"
        assert event.pattern_matched == "ignore.*instructions"
        assert event.embedding_score == 0.0

    def test_otel_attributes_include_prompt_fields(self) -> None:
        event = PromptViolation(
            severity=ViolationSeverity.WARNING,
            action=GuardrailAction.WARN,
            guardrail_name="jailbreak",
            detail="semantic match",
            stage="semantic",
            pattern_matched="",
            embedding_score=0.78,
        )
        attrs = event.to_otel_attributes()
        assert attrs["streetrace.guardrail.violation.stage"] == "semantic"
        assert attrs["streetrace.guardrail.violation.pattern_matched"] == ""
        assert attrs["streetrace.guardrail.violation.embedding_score"] == 0.78

    def test_optional_fields_default(self) -> None:
        event = PromptViolation(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="jailbreak",
            detail="ok",
        )
        assert event.stage == ""
        assert event.pattern_matched == ""
        assert event.embedding_score == 0.0


class TestToolViolation:
    """Verify MCP-Guard violation event."""

    def test_includes_tool_specific_fields(self) -> None:
        event = ToolViolation(
            severity=ViolationSeverity.CRITICAL,
            action=GuardrailAction.BLOCK,
            guardrail_name="mcp_guard",
            detail="shell injection in args",
            server_id="untrusted-server",
            tool_name="execute_command",
            trust_score=0.2,
        )
        assert event.server_id == "untrusted-server"
        assert event.tool_name == "execute_command"
        assert event.trust_score == 0.2

    def test_otel_attributes_include_tool_fields(self) -> None:
        event = ToolViolation(
            severity=ViolationSeverity.WARNING,
            action=GuardrailAction.WARN,
            guardrail_name="mcp_guard",
            detail="low trust",
            server_id="server-1",
            tool_name="read_file",
            trust_score=0.45,
        )
        attrs = event.to_otel_attributes()
        assert attrs["streetrace.guardrail.violation.server_id"] == "server-1"
        assert attrs["streetrace.guardrail.violation.tool_name"] == "read_file"
        assert attrs["streetrace.guardrail.violation.trust_score"] == 0.45

    def test_optional_fields_default(self) -> None:
        event = ToolViolation(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="mcp_guard",
            detail="ok",
        )
        assert event.server_id == ""
        assert event.tool_name == ""
        assert event.trust_score == 0.0


class TestDriftViolation:
    """Verify cognitive drift violation event."""

    def test_includes_drift_specific_fields(self) -> None:
        event = DriftViolation(
            severity=ViolationSeverity.WARNING,
            action=GuardrailAction.WARN,
            guardrail_name="cognitive_drift",
            detail="intent drift detected",
            session_id="sess-123",
            turn_number=7,
            risk_score=0.72,
        )
        assert event.session_id == "sess-123"
        assert event.turn_number == 7
        assert event.risk_score == 0.72

    def test_otel_attributes_include_drift_fields(self) -> None:
        event = DriftViolation(
            severity=ViolationSeverity.CRITICAL,
            action=GuardrailAction.BLOCK,
            guardrail_name="cognitive_drift",
            detail="drift blocked",
            session_id="sess-456",
            turn_number=12,
            risk_score=0.95,
        )
        attrs = event.to_otel_attributes()
        assert attrs["streetrace.guardrail.violation.session_id"] == "sess-456"
        assert attrs["streetrace.guardrail.violation.turn_number"] == 12.0
        assert attrs["streetrace.guardrail.violation.risk_score"] == 0.95

    def test_optional_fields_default(self) -> None:
        event = DriftViolation(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="cognitive_drift",
            detail="ok",
        )
        assert event.session_id == ""
        assert event.turn_number == 0
        assert event.risk_score == 0.0


class TestRecoveryEvent:
    """Verify recovery event after intervention."""

    def test_includes_recovery_fields(self) -> None:
        event = RecoveryEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="cognitive_drift",
            detail="recovery complete",
            session_id="sess-789",
            recovery_turns=3,
            recovery_time_ms=1500,
        )
        assert event.session_id == "sess-789"
        assert event.recovery_turns == 3
        assert event.recovery_time_ms == 1500

    def test_otel_attributes_include_recovery_fields(self) -> None:
        event = RecoveryEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="cognitive_drift",
            detail="recovered",
            session_id="sess-abc",
            recovery_turns=2,
            recovery_time_ms=800,
        )
        attrs = event.to_otel_attributes()
        assert attrs["streetrace.guardrail.violation.session_id"] == "sess-abc"
        assert attrs["streetrace.guardrail.violation.recovery_turns"] == 2.0
        assert attrs["streetrace.guardrail.violation.recovery_time_ms"] == 800.0

    def test_optional_fields_default(self) -> None:
        event = RecoveryEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="cognitive_drift",
            detail="ok",
        )
        assert event.session_id == ""
        assert event.recovery_turns == 0
        assert event.recovery_time_ms == 0


class TestSeverityClassification:
    """Verify severity values map to expected threat levels."""

    @pytest.mark.parametrize(
        ("action", "expected_severity"),
        [
            (GuardrailAction.ALLOW, ViolationSeverity.INFO),
            (GuardrailAction.WARN, ViolationSeverity.WARNING),
            (GuardrailAction.BLOCK, ViolationSeverity.CRITICAL),
        ],
    )
    def test_severity_matches_action_convention(
        self, action: GuardrailAction, expected_severity: ViolationSeverity,
    ) -> None:
        """Verify each severity can be used with the matching action."""
        event = ViolationEvent(
            severity=expected_severity,
            action=action,
            guardrail_name="test",
            detail="test",
        )
        assert event.severity == expected_severity
        assert event.action == action
