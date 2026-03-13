"""Guardrail provider for Streetrace DSL runtime.

Orchestrate guardrail dispatch using a registry of ``Guardrail``
implementations. OTEL span instrumentation lives here as an
orchestration concern. Content types and individual guardrails
are in their own modules.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from openinference.semconv.trace import (
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry import trace

from streetrace.dsl.runtime.guardrail import CustomGuardrailAdapter
from streetrace.dsl.runtime.guardrail_types import (
    INSPECTABLE_FIELDS_CHECK,
    INSPECTABLE_FIELDS_MASK,
    GuardrailContent,
    GuardrailFunc,
    ToolCallContent,
    ToolResultContent,
    check_fields,
    mask_fields,
)
from streetrace.dsl.runtime.pii_guardrail import PiiGuardrail
from streetrace.guardrails.prompt_proxy.pipeline import PromptProxyPipeline
from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.guardrail import Guardrail

logger = get_logger(__name__)

# Re-export public names for backward compatibility — existing consumers
# import these from guardrail_provider and must continue to work.
__all__ = [
    "CAPTURE_CONTENT_ENV_VAR",
    "INSPECTABLE_FIELDS_CHECK",
    "INSPECTABLE_FIELDS_MASK",
    "GuardrailContent",
    "GuardrailFunc",
    "GuardrailProvider",
    "ToolCallContent",
    "ToolResultContent",
]

CAPTURE_CONTENT_ENV_VAR = "STREETRACE_CAPTURE_GUARDRAIL_CONTENT_IN_SPANS"
"""Env var controlling whether pre-masking/blocking input is captured in spans."""


# ---------------------------------------------------------------------------
# GuardrailProvider
# ---------------------------------------------------------------------------


class GuardrailProvider:
    """Dispatch guardrail operations through a registry of implementations.

    Built-in guardrails (``pii``, ``jailbreak``) are registered at
    construction. Custom guardrails registered via ``register_custom``
    take precedence over built-in handling for the same name.

    OTEL span instrumentation and structured content dispatch are
    orchestration concerns that live here, not in individual guardrails.
    """

    def __init__(self) -> None:
        """Initialize with built-in guardrails."""
        self._registry: dict[str, Guardrail] = {}
        self._parent_ctx: WorkflowContext | None = None
        self._session_id: str | None = None
        self._session_state: dict[str, object] | None = None

        # Register built-in guardrails
        jailbreak = PromptProxyPipeline(inference_pipeline=None)
        pii = PiiGuardrail()
        self._registry[jailbreak.name] = jailbreak
        self._registry[pii.name] = pii

    # -- invocation context ---------------------------------------------------

    def set_invocation_context(
        self,
        *,
        session_id: str,
        session_state: dict[str, object],
    ) -> None:
        """Set per-callback session context for session-aware guardrails.

        Called by ``GuardrailPlugin`` before each handler invocation with
        the session information from ADK's ``CallbackContext``.

        Args:
            session_id: ADK session identifier.
            session_state: Mutable session state dict from ADK.

        """
        self._session_id = session_id
        self._session_state = session_state

    def clear_invocation_context(self) -> None:
        """Reset session context to None."""
        self._session_id = None
        self._session_state = None

    @property
    def session_id(self) -> str | None:
        """Return the current ADK session ID, or None."""
        return self._session_id

    @property
    def session_state(self) -> dict[str, object] | None:
        """Return the current ADK session state, or None."""
        return self._session_state

    # -- custom guardrail registration ------------------------------------

    def register_custom(self, name: str, func: GuardrailFunc) -> None:
        """Register a custom guardrail function.

        Custom guardrails override built-in guardrails with the same name.

        Args:
            name: Guardrail name used in DSL (e.g. ``mask my_guard``).
            func: Callable accepting a message string.

        """
        self._registry[name] = CustomGuardrailAdapter(name, func)
        logger.debug("Registered custom guardrail: %s", name)

    # -- public API -------------------------------------------------------

    async def mask(
        self, guardrail: str, content: GuardrailContent,
    ) -> GuardrailContent:
        """Mask sensitive content in a message or structured result.

        Custom guardrails are tried first. The built-in ``pii``
        guardrail requires Presidio — a ``MissingDependencyError`` is
        raised if it cannot be loaded.

        Args:
            guardrail: Name of the guardrail (e.g., 'pii').
            content: Content to mask — string, tool result, or tool call.

        Returns:
            Content with sensitive data masked (same type as input).

        Raises:
            MissingDependencyError: If Presidio is required but unavailable.

        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            f"guardrail.mask.{guardrail}",
        ) as span:
            _set_guardrail_attributes(
                span, guardrail, "mask", self._get_event_phase(),
            )
            if _capture_content_enabled():
                span.set_attribute(
                    SpanAttributes.INPUT_VALUE,
                    _serialize_content(content),
                )

            logger.debug("Masking %s in message", guardrail)

            impl = self._registry.get(guardrail)

            # Custom guardrail adapter — receives full content, may be async
            if isinstance(impl, CustomGuardrailAdapter):
                result = await self._call_custom_mask(impl, content)
                masked: GuardrailContent = str(result)
                triggered = masked != _serialize_content(content)
                _set_triggered_output(
                    span, triggered=triggered, output_value=str(masked),
                )
                return masked

            if isinstance(content, ToolCallContent):
                _set_triggered_output(span, triggered=False)
                return content

            if isinstance(content, ToolResultContent):
                masked_result = self._mask_tool_result(
                    impl, content,
                )
                triggered = masked_result.data != content.data
                _set_triggered_output(
                    span,
                    triggered=triggered,
                    output_value=json.dumps(masked_result.data, default=str)
                    if triggered else None,
                )
                return masked_result

            # str path
            masked_str = self._mask_str(impl, guardrail, content)
            triggered = masked_str != content
            _set_triggered_output(
                span,
                triggered=triggered,
                output_value=masked_str if triggered else None,
            )
            return masked_str

    def _mask_str(
        self, impl: Guardrail | None, guardrail: str, message: str,
    ) -> str:
        """Apply masking to a plain string.

        Args:
            impl: Guardrail implementation or None.
            guardrail: Name of the guardrail.
            message: Text to mask.

        Returns:
            Masked text.

        """
        if impl is None:
            logger.warning(
                "Unknown guardrail type for masking: %s", guardrail,
            )
            return message
        return impl.mask_str(message)

    def _mask_tool_result(
        self,
        impl: Guardrail | None,
        content: ToolResultContent,
    ) -> ToolResultContent:
        """Apply masking to inspectable fields in a tool result.

        Args:
            impl: Guardrail implementation or None.
            content: Tool result content to mask.

        Returns:
            New ToolResultContent with masked fields.

        """
        if impl is None:
            return content
        masked_data = mask_fields(
            content.data, impl.mask_str,
        )
        return ToolResultContent(data=masked_data)

    async def check(
        self, guardrail: str, content: GuardrailContent,
    ) -> bool:
        """Check if content triggers a guardrail.

        Custom guardrails are tried first. The built-in ``jailbreak``
        guardrail uses regex patterns by design (Presidio has no
        jailbreak detection).

        Args:
            guardrail: Name of the guardrail (e.g., 'jailbreak').
            content: Content to check — string, tool result, or tool call.

        Returns:
            True if the guardrail is triggered.

        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            f"guardrail.check.{guardrail}",
        ) as span:
            _set_guardrail_attributes(
                span, guardrail, "check", self._get_event_phase(),
            )
            if _capture_content_enabled():
                span.set_attribute(
                    SpanAttributes.INPUT_VALUE,
                    _serialize_content(content),
                )

            logger.debug("Checking %s guardrail", guardrail)

            triggered = False
            detail = ""

            impl = self._registry.get(guardrail)

            # Custom guardrail adapter — receives full content, may be async
            if isinstance(impl, CustomGuardrailAdapter):
                result = await self._call_custom_check(impl, content)
                triggered = bool(result)
                if triggered:
                    detail = f"custom guardrail '{guardrail}' triggered"
            elif isinstance(content, ToolResultContent):
                triggered, detail = self._check_tool_result(
                    impl, content,
                )
            elif isinstance(content, ToolCallContent):
                text = json.dumps(content.data, default=str)
                triggered, detail = self._check_str(impl, guardrail, text)
            else:
                triggered, detail = self._check_str(
                    impl, guardrail, content,
                )

            span.set_attribute(
                "streetrace.guardrail.triggered", triggered,
            )
            span.set_attribute(
                SpanAttributes.OUTPUT_VALUE,
                detail if triggered else "not triggered",
            )
            return triggered

    def _check_str(
        self, impl: Guardrail | None, guardrail: str, text: str,
    ) -> tuple[bool, str]:
        """Check a plain string against a guardrail.

        Args:
            impl: Guardrail implementation or None.
            guardrail: Name of the guardrail.
            text: Text to check.

        Returns:
            Tuple of (triggered, detail).

        """
        if impl is None:
            logger.warning(
                "Unknown guardrail type for checking: %s", guardrail,
            )
            return False, ""
        return impl.check_str(text)

    def _check_tool_result(
        self,
        impl: Guardrail | None,
        content: ToolResultContent,
    ) -> tuple[bool, str]:
        """Check inspectable fields in a tool result.

        Only inspect user-facing fields (``output``, ``stdout``) —
        error messages are system-generated and would cause false
        positives.

        Args:
            impl: Guardrail implementation or None.
            content: Tool result content to check.

        Returns:
            Tuple of (triggered, detail).

        """
        if impl is None:
            return False, ""
        return check_fields(
            content.data,
            lambda text: impl.check_str(text),
        )

    # -- OTEL helpers -----------------------------------------------------

    def _get_event_phase(self) -> str:
        """Return the current event phase from the parent context.

        Returns:
            Event phase string, or empty string if no parent context.

        """
        if self._parent_ctx is not None:
            return self._parent_ctx.event_phase
        return ""

    # -- async dispatch for custom guardrails -----------------------------

    @staticmethod
    async def _call_custom_mask(
        adapter: CustomGuardrailAdapter,
        content: GuardrailContent,
    ) -> str:
        """Invoke a custom guardrail adapter for masking.

        Handle both sync and async callables.

        Args:
            adapter: The custom guardrail adapter.
            content: Input content (str or structured).

        Returns:
            Masked string result.

        """
        import asyncio
        import inspect

        result = adapter.func(content)
        if inspect.isawaitable(result) or asyncio.iscoroutine(result):
            result = await result

        return str(result)

    @staticmethod
    async def _call_custom_check(
        adapter: CustomGuardrailAdapter,
        content: GuardrailContent,
    ) -> bool:
        """Invoke a custom guardrail adapter for checking.

        Handle both sync and async callables.

        Args:
            adapter: The custom guardrail adapter.
            content: Input content (str or structured).

        Returns:
            True if the guardrail was triggered.

        """
        import asyncio
        import inspect

        result = adapter.func(content)
        if inspect.isawaitable(result) or asyncio.iscoroutine(result):
            result = await result

        return bool(result)


# ---------------------------------------------------------------------------
# Module-level OTEL helpers
# ---------------------------------------------------------------------------


def _serialize_content(content: GuardrailContent) -> str:
    """Serialize guardrail content to a string for OTEL attributes.

    Args:
        content: Content to serialize.

    Returns:
        String representation.

    """
    if isinstance(content, (ToolResultContent, ToolCallContent)):
        return json.dumps(content.data, default=str)
    return content


def _set_triggered_output(
    span: trace.Span,
    *,
    triggered: bool,
    output_value: str | None = None,
) -> None:
    """Set triggered and output.value attributes on a span.

    Args:
        span: The active span to annotate.
        triggered: Whether the guardrail was triggered.
        output_value: Value to set as output; defaults to "not triggered".

    """
    span.set_attribute("streetrace.guardrail.triggered", triggered)
    span.set_attribute(
        SpanAttributes.OUTPUT_VALUE,
        output_value if output_value is not None else "not triggered",
    )


def _set_guardrail_attributes(
    span: trace.Span,
    name: str,
    action: str,
    event_phase: str,
) -> None:
    """Set standard guardrail attributes on an OTEL span.

    Args:
        span: The active span to annotate.
        name: Guardrail name (e.g. ``"pii"``).
        action: Guardrail action (``"mask"`` or ``"check"``).
        event_phase: Event lifecycle phase (e.g. ``"input"``).

    """
    span.set_attribute(
        SpanAttributes.OPENINFERENCE_SPAN_KIND,
        OpenInferenceSpanKindValues.GUARDRAIL.value,
    )
    span.set_attribute("streetrace.guardrail.name", name)
    span.set_attribute("streetrace.guardrail.action", action)
    span.set_attribute("streetrace.guardrail.event_phase", event_phase)


def _capture_content_enabled() -> bool:
    """Check whether pre-masking input should be captured in spans.

    Returns:
        True if the ``STREETRACE_CAPTURE_GUARDRAIL_CONTENT_IN_SPANS``
        environment variable is set to a truthy value.

    """
    return os.environ.get(
        CAPTURE_CONTENT_ENV_VAR, "",
    ).lower() in ("true", "1", "yes")
