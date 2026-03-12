"""Content types and field helpers for guardrail dispatch.

Define the structured content types passed through guardrail operations,
inspectable field constants, and the custom guardrail function protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@dataclass(frozen=True)
class ToolResultContent:
    """Tool result for guardrail inspection.

    Wrap the full result dict (OpResult/CliResult shape) so guardrails
    can inspect content fields while preserving metadata.
    """

    data: dict[str, object]


@dataclass(frozen=True)
class ToolCallContent:
    """Tool call arguments for guardrail inspection."""

    data: dict[str, object]


GuardrailContent = str | ToolResultContent | ToolCallContent
"""Union type for content passed to guardrail operations."""

INSPECTABLE_FIELDS_MASK = ("output", "stdout", "error", "stderr")
"""Content fields to inspect during masking — PII can leak anywhere."""

INSPECTABLE_FIELDS_CHECK = ("output", "stdout")
"""Content fields to inspect during checking — only user-facing content."""


@runtime_checkable
class GuardrailFunc(Protocol):
    """Protocol for custom guardrail functions.

    Return ``str`` to replace the message (masking), or ``bool`` to
    indicate whether the guardrail was triggered (checking).
    """

    def __call__(
        self, content: GuardrailContent,
    ) -> str | bool | Awaitable[str | bool]:
        """Execute the guardrail on *content*."""
        ...


def mask_fields(
    data: dict[str, object],
    mask_fn: Callable[[str], str],
) -> dict[str, object]:
    """Apply a mask function to inspectable content fields.

    Iterate ``INSPECTABLE_FIELDS_MASK`` and apply *mask_fn* to each
    string-valued field. Return a shallow copy with replaced fields.

    Args:
        data: Original tool result dict.
        mask_fn: Function to mask a single string value.

    Returns:
        New dict with masked field values.

    """
    result = dict(data)
    for field in INSPECTABLE_FIELDS_MASK:
        value = result.get(field)
        if isinstance(value, str) and value:
            result[field] = mask_fn(value)
    return result


def check_fields(
    data: dict[str, object],
    check_fn: Callable[[str], tuple[bool, str]],
) -> tuple[bool, str]:
    """Check inspectable content fields for guardrail triggers.

    Iterate ``INSPECTABLE_FIELDS_CHECK`` and return on first trigger.

    Args:
        data: Tool result dict.
        check_fn: Function that returns (triggered, detail) for a string.

    Returns:
        Tuple of (triggered, detail).

    """
    for field in INSPECTABLE_FIELDS_CHECK:
        value = data.get(field)
        if isinstance(value, str) and value:
            triggered, detail = check_fn(value)
            if triggered:
                return True, f"{detail} in field '{field}'"
    return False, ""
