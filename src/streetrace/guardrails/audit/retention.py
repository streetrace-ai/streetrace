"""Data retention policy model for guardrail audit records.

Define validation rules for retention periods and content
redaction settings used by the audit trail lifecycle management.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class RetentionPolicy(BaseModel):
    """Data retention policy for guardrail audit records.

    Enforce that retention periods are non-negative and that
    max is not less than min.
    """

    min_retention_days: int
    max_retention_days: int
    content_redaction_enabled: bool = False
    redact_after_days: int | None = None

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _validate_retention_bounds(self) -> RetentionPolicy:
        """Validate retention day constraints."""
        if self.min_retention_days < 0:
            msg = "min_retention_days must be >= 0"
            raise ValueError(msg)
        if self.max_retention_days < self.min_retention_days:
            msg = (
                "max_retention_days must be >= min_retention_days"
            )
            raise ValueError(msg)
        return self
