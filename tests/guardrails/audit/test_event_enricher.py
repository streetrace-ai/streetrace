"""Tests for event enricher context injection."""

from __future__ import annotations

from streetrace.guardrails.audit.event_enricher import EventEnricher
from streetrace.guardrails.audit.violation_events import (
    PromptViolation,
    ViolationEvent,
    ViolationSeverity,
)
from streetrace.guardrails.types import GuardrailAction


class TestEventEnricher:
    """Verify context enrichment of violation events."""

    def test_enrich_adds_agent_id(self) -> None:
        enricher = EventEnricher(
            context={"agent_id": "agent-42", "org_id": "org-1", "run_id": "run-99"},
        )
        event = ViolationEvent(
            severity=ViolationSeverity.WARNING,
            action=GuardrailAction.WARN,
            guardrail_name="jailbreak",
            detail="test",
        )
        enriched = enricher.enrich(event)
        assert enriched.agent_id == "agent-42"

    def test_enrich_adds_org_id(self) -> None:
        enricher = EventEnricher(
            context={"agent_id": "a", "org_id": "org-7", "run_id": "r"},
        )
        event = ViolationEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="test",
            detail="ok",
        )
        enriched = enricher.enrich(event)
        assert enriched.org_id == "org-7"

    def test_enrich_adds_run_id(self) -> None:
        enricher = EventEnricher(
            context={"agent_id": "a", "org_id": "o", "run_id": "run-555"},
        )
        event = ViolationEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="test",
            detail="ok",
        )
        enriched = enricher.enrich(event)
        assert enriched.run_id == "run-555"

    def test_enrich_returns_new_event(self) -> None:
        enricher = EventEnricher(
            context={"agent_id": "a", "org_id": "o", "run_id": "r"},
        )
        original = ViolationEvent(
            severity=ViolationSeverity.WARNING,
            action=GuardrailAction.WARN,
            guardrail_name="jailbreak",
            detail="test",
        )
        enriched = enricher.enrich(original)
        # Original is not mutated
        assert original.agent_id == ""
        assert enriched.agent_id == "a"
        # But original fields are preserved
        assert enriched.violation_id == original.violation_id
        assert enriched.severity == original.severity
        assert enriched.guardrail_name == original.guardrail_name

    def test_enrich_preserves_subtype(self) -> None:
        enricher = EventEnricher(
            context={"agent_id": "a", "org_id": "o", "run_id": "r"},
        )
        original = PromptViolation(
            severity=ViolationSeverity.CRITICAL,
            action=GuardrailAction.BLOCK,
            guardrail_name="jailbreak",
            detail="blocked",
            stage="syntactic",
            pattern_matched="ignore.*",
            embedding_score=0.0,
        )
        enriched = enricher.enrich(original)
        assert isinstance(enriched, PromptViolation)
        assert enriched.stage == "syntactic"  # type: ignore[attr-defined]
        assert enriched.agent_id == "a"

    def test_enrich_otel_attributes_include_context(self) -> None:
        enricher = EventEnricher(
            context={
                "agent_id": "agent-x",
                "org_id": "org-y",
                "run_id": "run-z",
            },
        )
        event = ViolationEvent(
            severity=ViolationSeverity.WARNING,
            action=GuardrailAction.WARN,
            guardrail_name="test",
            detail="test",
        )
        enriched = enricher.enrich(event)
        attrs = enriched.to_otel_attributes()
        assert attrs["streetrace.guardrail.violation.agent_id"] == "agent-x"
        assert attrs["streetrace.guardrail.violation.org_id"] == "org-y"
        assert attrs["streetrace.guardrail.violation.run_id"] == "run-z"

    def test_enrich_with_empty_context(self) -> None:
        enricher = EventEnricher(context={})
        event = ViolationEvent(
            severity=ViolationSeverity.INFO,
            action=GuardrailAction.ALLOW,
            guardrail_name="test",
            detail="ok",
        )
        enriched = enricher.enrich(event)
        assert enriched.agent_id == ""
        assert enriched.org_id == ""
        assert enriched.run_id == ""
