"""Tests for compliance mapper EU AI Act article mapping."""

from __future__ import annotations

import pytest

from streetrace.guardrails.audit.compliance_mapper import (
    ComplianceMapper,
    ComplianceMapping,
)


class TestComplianceMapping:
    """Verify compliance mapping data model."""

    def test_mapping_fields(self) -> None:
        mapping = ComplianceMapping(
            article_number=9,
            article_title="Risk Management",
            capability_description="Guardrail detection capabilities",
            evidence_query="violations by severity over time",
        )
        assert mapping.article_number == 9
        assert mapping.article_title == "Risk Management"
        assert mapping.capability_description != ""
        assert mapping.evidence_query != ""


class TestComplianceMapper:
    """Verify EU AI Act article mapping coverage."""

    def test_all_four_articles_mapped(self) -> None:
        mapper = ComplianceMapper()
        mappings = mapper.all_mappings()
        article_numbers = {m.article_number for m in mappings}
        assert article_numbers == {9, 12, 14, 62}

    def test_get_article_9_risk_management(self) -> None:
        mapper = ComplianceMapper()
        mapping = mapper.get_mapping(article=9)
        assert mapping.article_number == 9
        assert "Risk Management" in mapping.article_title
        assert mapping.capability_description != ""
        assert mapping.evidence_query != ""

    def test_get_article_12_record_keeping(self) -> None:
        mapper = ComplianceMapper()
        mapping = mapper.get_mapping(article=12)
        assert mapping.article_number == 12
        assert "Record" in mapping.article_title
        assert mapping.evidence_query != ""

    def test_get_article_14_human_oversight(self) -> None:
        mapper = ComplianceMapper()
        mapping = mapper.get_mapping(article=14)
        assert mapping.article_number == 14
        assert "Oversight" in mapping.article_title
        assert mapping.evidence_query != ""

    def test_get_article_62_incident_reporting(self) -> None:
        mapper = ComplianceMapper()
        mapping = mapper.get_mapping(article=62)
        assert mapping.article_number == 62
        assert "Incident" in mapping.article_title
        assert mapping.evidence_query != ""

    def test_get_unknown_article_raises(self) -> None:
        mapper = ComplianceMapper()
        with pytest.raises(KeyError):
            mapper.get_mapping(article=99)

    def test_each_mapping_has_evidence_query(self) -> None:
        mapper = ComplianceMapper()
        for mapping in mapper.all_mappings():
            assert mapping.evidence_query.strip() != "", (
                f"Article {mapping.article_number} missing evidence query"
            )

    def test_each_mapping_has_capability_description(self) -> None:
        mapper = ComplianceMapper()
        for mapping in mapper.all_mappings():
            assert mapping.capability_description.strip() != "", (
                f"Article {mapping.article_number} missing capability"
            )

    def test_mappings_are_distinct(self) -> None:
        mapper = ComplianceMapper()
        mappings = mapper.all_mappings()
        titles = [m.article_title for m in mappings]
        assert len(titles) == len(set(titles))
