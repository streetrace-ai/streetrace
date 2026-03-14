"""Guardrail protocol and custom guardrail adapter.

Define the ``Guardrail`` protocol that all guardrails implement and
the ``CustomGuardrailAdapter`` that wraps user-provided functions
into the protocol interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from streetrace.dsl.runtime.guardrail_types import GuardrailFunc


@runtime_checkable
class Guardrail(Protocol):
    """Protocol for guardrail implementations.

    Each guardrail has a name, can mask text, and can check text.
    Guardrails that only support one operation return a no-op for
    the other (identity for mask, ``(False, "")`` for check).
    """

    @property
    def name(self) -> str:
        """Return the guardrail name."""
        ...

    def mask_str(self, text: str) -> str:
        """Mask sensitive content in *text*.

        Args:
            text: Input text to mask.

        Returns:
            Text with sensitive content replaced.

        """
        ...

    def check_str(self, text: str) -> tuple[bool, str]:
        """Check if *text* triggers the guardrail.

        Args:
            text: Input text to check.

        Returns:
            Tuple of (triggered, detail message).

        """
        ...


class CustomGuardrailAdapter:
    """Adapt a ``GuardrailFunc`` to the ``Guardrail`` protocol.

    The provider detects this adapter and awaits the underlying
    function if it returns a coroutine.
    """

    def __init__(self, guardrail_name: str, func: GuardrailFunc) -> None:
        """Initialize the adapter.

        Args:
            guardrail_name: Guardrail name used in DSL.
            func: User-provided guardrail function.

        """
        self._name = guardrail_name
        self._func = func

    @property
    def name(self) -> str:
        """Return the guardrail name."""
        return self._name

    @property
    def func(self) -> GuardrailFunc:
        """Return the wrapped function for async dispatch."""
        return self._func

    def mask_str(self, text: str) -> str:
        """Invoke the underlying function synchronously for masking.

        For async functions the provider detects this adapter and
        awaits the result directly.

        Args:
            text: Input text to mask.

        Returns:
            Masked text.

        """
        result = self._func(text)
        return str(result)

    def check_str(self, text: str) -> tuple[bool, str]:
        """Invoke the underlying function synchronously for checking.

        For async functions the provider detects this adapter and
        awaits the result directly.

        Args:
            text: Input text to check.

        Returns:
            Tuple of (triggered, detail).

        """
        result = self._func(text)
        triggered = bool(result)
        detail = f"custom guardrail '{self._name}' triggered" if triggered else ""
        return triggered, detail
