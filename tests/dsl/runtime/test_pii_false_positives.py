"""Tests for PII masking false positives on documentation content.

Verify that ``_EXCLUDED_ENTITY_TYPES`` correctly filters URL and
DATE_TIME entities while still masking real PII like email addresses.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from streetrace.dsl.runtime.pii_guardrail import PiiGuardrail, _PresidioBackend


def _make_analyzer_result(
    entity_type: str,
    start: int,
    end: int,
    score: float = 0.85,
) -> MagicMock:
    """Create a mock Presidio RecognizerResult."""
    result = MagicMock()
    result.entity_type = entity_type
    result.start = start
    result.end = end
    result.score = score
    return result


def _build_backend_with_results(
    analyzer_results: list[MagicMock],
    anonymized_text: str,
) -> _PresidioBackend:
    """Build a ``_PresidioBackend`` with mocked Presidio engines."""
    backend = object.__new__(_PresidioBackend)

    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = analyzer_results
    backend._analyzer = mock_analyzer  # noqa: SLF001

    mock_anonymized = MagicMock()
    mock_anonymized.text = anonymized_text
    mock_anonymizer = MagicMock()
    mock_anonymizer.anonymize.return_value = mock_anonymized
    backend._anonymizer = mock_anonymizer  # noqa: SLF001

    backend._operator_config = MagicMock()  # noqa: SLF001

    return backend


README_WITH_URLS_AND_DATES = """\
# Streetrace

Get started in under 5 minutes.

**[Get Started](docs/user/GETTING_STARTED.md)**

## What It Does Today

- Python-based runtime that works locally or in CI/CD
- DSL agent definitions for structured workflows
"""

README_WITH_MARKDOWN_LINKS = """\
## Documentation

- [API Reference](docs/api/README.md)
- [User Guide](docs/user/guide.md)
- [Contributing](CONTRIBUTING.md)
"""


@pytest.fixture
def pii_guardrail_with_url_results() -> PiiGuardrail:
    """PiiGuardrail with backend returning URL and DATE_TIME entities."""
    backend = _build_backend_with_results(
        analyzer_results=[
            _make_analyzer_result("URL", 64, 95),
            _make_analyzer_result("DATE_TIME", 28, 39),
        ],
        anonymized_text=README_WITH_URLS_AND_DATES,
    )
    guard = PiiGuardrail()
    guard._presidio = backend  # noqa: SLF001
    return guard


@pytest.fixture
def pii_guardrail_with_link_results() -> PiiGuardrail:
    """PiiGuardrail with backend returning URL entities for markdown links."""
    backend = _build_backend_with_results(
        analyzer_results=[
            _make_analyzer_result("URL", 30, 51),
        ],
        anonymized_text=README_WITH_MARKDOWN_LINKS,
    )
    guard = PiiGuardrail()
    guard._presidio = backend  # noqa: SLF001
    return guard


@pytest.fixture
def pii_guardrail_with_email_results() -> PiiGuardrail:
    """PiiGuardrail with backend returning EMAIL_ADDRESS entity."""
    backend = _build_backend_with_results(
        analyzer_results=[
            _make_analyzer_result("EMAIL_ADDRESS", 8, 28),
        ],
        anonymized_text="Contact [MASKED_EMAIL_ADDRESS] for support",
    )
    guard = PiiGuardrail()
    guard._presidio = backend  # noqa: SLF001
    return guard


class TestPiiMaskingFalsePositives:
    """Test that non-PII content is not masked."""

    def test_readme_urls_not_masked(
        self, pii_guardrail_with_url_results: PiiGuardrail,
    ) -> None:
        """Documentation URLs should not be masked as PII.

        Presidio's URL recognizer false-positives on file paths like
        docs/user/GETTING_STARTED.md. The ``_EXCLUDED_ENTITY_TYPES``
        set filters these out before anonymization.
        """
        pii_guardrail_with_url_results.mask_str(
            README_WITH_URLS_AND_DATES,
        )
        # URL entities excluded — anonymizer receives no URL results
        backend = pii_guardrail_with_url_results._presidio  # noqa: SLF001
        assert backend is not None
        call_kwargs = backend._anonymizer.anonymize.call_args[1]  # noqa: SLF001
        filtered = call_kwargs["analyzer_results"]
        entity_types = {r.entity_type for r in filtered}
        assert "URL" not in entity_types

    def test_readme_dates_not_masked(
        self, pii_guardrail_with_url_results: PiiGuardrail,
    ) -> None:
        """Phrases like 'under 5 minutes' should not be masked.

        Presidio's DATE_TIME recognizer matches time references.
        These are excluded via ``_EXCLUDED_ENTITY_TYPES``.
        """
        pii_guardrail_with_url_results.mask_str(
            README_WITH_URLS_AND_DATES,
        )
        backend = pii_guardrail_with_url_results._presidio  # noqa: SLF001
        assert backend is not None
        call_kwargs = backend._anonymizer.anonymize.call_args[1]  # noqa: SLF001
        filtered = call_kwargs["analyzer_results"]
        entity_types = {r.entity_type for r in filtered}
        assert "DATE_TIME" not in entity_types

    def test_markdown_links_not_masked(
        self, pii_guardrail_with_link_results: PiiGuardrail,
    ) -> None:
        """Markdown reference links should not be masked."""
        pii_guardrail_with_link_results.mask_str(
            README_WITH_MARKDOWN_LINKS,
        )
        backend = pii_guardrail_with_link_results._presidio  # noqa: SLF001
        assert backend is not None
        call_kwargs = backend._anonymizer.anonymize.call_args[1]  # noqa: SLF001
        filtered = call_kwargs["analyzer_results"]
        entity_types = {r.entity_type for r in filtered}
        assert "URL" not in entity_types

    def test_real_pii_still_masked(
        self, pii_guardrail_with_email_results: PiiGuardrail,
    ) -> None:
        """Real PII like email addresses should still be masked."""
        text = "Contact john.doe@example.com for support"
        result = pii_guardrail_with_email_results.mask_str(text)
        assert result == "Contact [MASKED_EMAIL_ADDRESS] for support"

        # EMAIL_ADDRESS should NOT be filtered out
        backend = pii_guardrail_with_email_results._presidio  # noqa: SLF001
        assert backend is not None
        call_kwargs = backend._anonymizer.anonymize.call_args[1]  # noqa: SLF001
        filtered = call_kwargs["analyzer_results"]
        entity_types = {r.entity_type for r in filtered}
        assert "EMAIL_ADDRESS" in entity_types
