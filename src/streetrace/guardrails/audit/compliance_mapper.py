"""Map EU AI Act articles to platform guardrail capabilities.

Provide structured mappings between regulatory requirements and
the guardrail infrastructure that satisfies them, along with
evidence queries for compliance reporting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComplianceMapping:
    """Map a single regulatory article to platform capabilities.

    Args:
        article_number: EU AI Act article number.
        article_title: Human-readable article title.
        capability_description: Platform capability that addresses this article.
        evidence_query: Description of what audit data to collect as evidence.

    """

    article_number: int
    article_title: str
    capability_description: str
    evidence_query: str


_EU_AI_ACT_MAPPINGS: dict[int, ComplianceMapping] = {
    9: ComplianceMapping(
        article_number=9,
        article_title="Risk Management System",
        capability_description=(
            "Guardrail detection capabilities across Prompt Proxy, "
            "MCP-Guard, and Cognitive Monitor provide continuous risk "
            "assessment. Configurable warn/block thresholds enable "
            "risk-proportionate responses. Detection effectiveness "
            "metrics (ASR, false positive rate) quantify residual risk."
        ),
        evidence_query=(
            "Aggregate violation counts by severity and proxy type "
            "over configurable time windows. Include detection "
            "effectiveness metrics and threshold configurations."
        ),
    ),
    12: ComplianceMapping(
        article_number=12,
        article_title="Record-Keeping",
        capability_description=(
            "Audit trail captures every guardrail check as an OTEL "
            "span with structured violation events. Each violation "
            "has a unique ID, timestamp, confidence score, and "
            "detection context. Retention policies enforce minimum "
            "and maximum storage periods."
        ),
        evidence_query=(
            "Count total guardrail checks and violations over the "
            "retention period. Verify audit trail completeness by "
            "comparing check count to expected invocation count. "
            "Report retention policy configuration and compliance."
        ),
    ),
    14: ComplianceMapping(
        article_number=14,
        article_title="Human Oversight",
        capability_description=(
            "Cognitive Monitor detects intent drift and triggers "
            "escalation to human operators. MTTR-A metrics measure "
            "recovery time after intervention. Guardrail block "
            "actions halt agent execution until human review."
        ),
        evidence_query=(
            "List escalation events with timestamps, recovery turns, "
            "and recovery time. Report MTTR-A statistics. Count "
            "block actions requiring human intervention."
        ),
    ),
    62: ComplianceMapping(
        article_number=62,
        article_title="Serious Incident Reporting",
        capability_description=(
            "Critical violations generate structured incident "
            "records with unique IDs, full detection context, and "
            "timeline data. Real-time alerting on critical severity "
            "violations enables 72-hour reporting compliance."
        ),
        evidence_query=(
            "Retrieve all critical-severity violations within the "
            "reporting period. Include violation timeline, affected "
            "sessions, agent identifiers, and corrective actions "
            "taken (block, escalation)."
        ),
    ),
}


class ComplianceMapper:
    """Map EU AI Act articles to platform guardrail capabilities.

    Provide structured access to the mapping between regulatory
    articles and the platform's compliance infrastructure.
    """

    def get_mapping(self, *, article: int) -> ComplianceMapping:
        """Return the compliance mapping for a specific article.

        Args:
            article: EU AI Act article number.

        Returns:
            Compliance mapping for the article.

        Raises:
            KeyError: If the article number is not mapped.

        """
        return _EU_AI_ACT_MAPPINGS[article]

    def all_mappings(self) -> list[ComplianceMapping]:
        """Return all compliance mappings.

        Returns:
            List of all mapped article-to-capability relationships.

        """
        return list(_EU_AI_ACT_MAPPINGS.values())
