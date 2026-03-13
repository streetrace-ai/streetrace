"""Tests for retention policy validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from streetrace.guardrails.audit.retention import RetentionPolicy


class TestRetentionPolicy:
    """Verify retention policy validation rules."""

    def test_valid_policy(self) -> None:
        policy = RetentionPolicy(
            min_retention_days=365,
            max_retention_days=2190,
            content_redaction_enabled=True,
            redact_after_days=90,
        )
        assert policy.min_retention_days == 365
        assert policy.max_retention_days == 2190
        assert policy.content_redaction_enabled is True
        assert policy.redact_after_days == 90

    def test_min_retention_at_zero(self) -> None:
        policy = RetentionPolicy(
            min_retention_days=0,
            max_retention_days=30,
        )
        assert policy.min_retention_days == 0

    def test_min_retention_negative_invalid(self) -> None:
        with pytest.raises(ValidationError):
            RetentionPolicy(
                min_retention_days=-1,
                max_retention_days=30,
            )

    def test_max_less_than_min_invalid(self) -> None:
        with pytest.raises(ValidationError):
            RetentionPolicy(
                min_retention_days=365,
                max_retention_days=30,
            )

    def test_max_equals_min_valid(self) -> None:
        policy = RetentionPolicy(
            min_retention_days=90,
            max_retention_days=90,
        )
        assert policy.min_retention_days == policy.max_retention_days

    def test_redaction_disabled_by_default(self) -> None:
        policy = RetentionPolicy(
            min_retention_days=0,
            max_retention_days=365,
        )
        assert policy.content_redaction_enabled is False
        assert policy.redact_after_days is None

    def test_redact_after_days_optional(self) -> None:
        policy = RetentionPolicy(
            min_retention_days=0,
            max_retention_days=365,
            content_redaction_enabled=True,
        )
        assert policy.redact_after_days is None

    def test_redact_after_days_set(self) -> None:
        policy = RetentionPolicy(
            min_retention_days=0,
            max_retention_days=365,
            content_redaction_enabled=True,
            redact_after_days=30,
        )
        assert policy.redact_after_days == 30
