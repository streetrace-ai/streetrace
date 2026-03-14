"""Tests for PII masking false positives on documentation content.

Reproduce the issue where Presidio's URL and date recognizers mask
non-PII content in README files and documentation.
"""

from __future__ import annotations

import pytest

from streetrace.dsl.runtime.pii_guardrail import PiiGuardrail


@pytest.fixture
def pii_guardrail() -> PiiGuardrail:
    """Create a PiiGuardrail instance."""
    return PiiGuardrail()


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


class TestPiiMaskingFalsePositives:
    """Test that non-PII content is not masked."""

    def test_readme_urls_not_masked(
        self, pii_guardrail: PiiGuardrail,
    ) -> None:
        """Documentation URLs should not be masked as PII.

        BUG: Presidio's URL recognizer masks markdown links like
        docs/user/GETTING_STARTED.md as URLs containing PII.
        """
        result = pii_guardrail.mask_str(README_WITH_URLS_AND_DATES)
        assert "[MASKED_URL]" not in result, (
            f"Documentation URL falsely masked:\n{result}"
        )
        assert "GETTING_STARTED" in result, (
            f"Documentation link was masked:\n{result}"
        )

    def test_readme_dates_not_masked(
        self, pii_guardrail: PiiGuardrail,
    ) -> None:
        """Phrases like 'under 5 minutes' and 'Today' should not be masked.

        BUG: Presidio's date recognizer masks phrases containing
        time references as date PII.
        """
        result = pii_guardrail.mask_str(README_WITH_URLS_AND_DATES)
        assert "[MASKED_DATE_TIME]" not in result, (
            f"Date reference falsely masked:\n{result}"
        )
        assert "5 minutes" in result, (
            f"Time reference was masked:\n{result}"
        )

    def test_markdown_links_not_masked(
        self, pii_guardrail: PiiGuardrail,
    ) -> None:
        """Markdown reference links should not be masked."""
        result = pii_guardrail.mask_str(README_WITH_MARKDOWN_LINKS)
        assert "README.md" in result, (
            f"Markdown link was masked:\n{result}"
        )

    def test_real_pii_still_masked(
        self, pii_guardrail: PiiGuardrail,
    ) -> None:
        """Real PII like email addresses should still be masked."""
        text = "Contact john.doe@example.com for support"
        result = pii_guardrail.mask_str(text)
        assert "john.doe@example.com" not in result, (
            "Real email PII should be masked"
        )
