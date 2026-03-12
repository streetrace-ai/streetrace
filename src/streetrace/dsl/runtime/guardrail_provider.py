"""Guardrail provider for Streetrace DSL runtime.

Provide PII masking, jailbreak detection, and custom guardrail dispatch.
PII masking requires Presidio — if not installed, an automatic installation
is attempted; if that also fails, a clear error is raised.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from openinference.semconv.trace import (
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry import trace

from streetrace.dsl.runtime.errors import MissingDependencyError
from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from streetrace.dsl.runtime.context import WorkflowContext

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Structured content types for guardrail dispatch
# ---------------------------------------------------------------------------


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

INSTALL_COMMAND = "pip install 'streetrace[guardrails]'"
"""Command users should run to install guardrail dependencies."""

CAPTURE_CONTENT_ENV_VAR = "STREETRACE_CAPTURE_GUARDRAIL_CONTENT_IN_SPANS"
"""Env var controlling whether pre-masking/blocking input is captured in spans."""

# ---------------------------------------------------------------------------
# Jailbreak detection patterns (case insensitive) — regex by design,
# not a fallback.  Presidio has no jailbreak detection capability.
# ---------------------------------------------------------------------------

_JAILBREAK_PATTERNS = [
    re.compile(r"ignore.*(?:previous|all).*instructions", re.IGNORECASE),
    re.compile(r"(?:you are|act as).*(?:DAN|do anything)", re.IGNORECASE),
    re.compile(r"pretend.*(?:no|without).*(?:restrictions|rules)", re.IGNORECASE),
    re.compile(
        r"(?:show|reveal|what is).*(?:system|initial).*(?:prompt|instruction)",
        re.IGNORECASE,
    ),
    re.compile(r"bypass.*(?:safety|security|restrictions)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"ignore.*(?:ethics|guidelines|policies)", re.IGNORECASE),
]
"""Patterns to detect common jailbreak attempts."""


# ---------------------------------------------------------------------------
# Custom guardrail protocol
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Presidio backend (lazy-loaded)
# ---------------------------------------------------------------------------


class _PresidioBackend:
    """Wrap Presidio analyzer and anonymizer engines.

    Instantiated lazily on first use so the heavy spaCy model is only
    loaded when guardrails actually need NLP-based PII detection.
    """

    def __init__(self) -> None:
        """Initialize Presidio engines."""
        import presidio_analyzer
        import presidio_anonymizer

        self._analyzer = presidio_analyzer.AnalyzerEngine()
        self._anonymizer = presidio_anonymizer.AnonymizerEngine()

    def mask_pii(self, text: str) -> str:
        """Detect and anonymize PII in *text*.

        Args:
            text: Input text to scan.

        Returns:
            Text with PII entities replaced by type placeholders.

        """
        from presidio_anonymizer.entities import OperatorConfig

        results = self._analyzer.analyze(text=text, language="en")
        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators={
                "DEFAULT": OperatorConfig("replace", {"new_value": "[PII]"}),
            },
        )
        return str(anonymized.text)


# ---------------------------------------------------------------------------
# GuardrailProvider
# ---------------------------------------------------------------------------


class GuardrailProvider:
    """Dispatch guardrail operations to Presidio for PII masking.

    PII masking requires Presidio. If not installed, the provider
    attempts a runtime install. If that fails, a ``MissingDependencyError``
    is raised with exact install instructions.

    Jailbreak detection uses regex patterns by design — Presidio does
    not offer jailbreak detection.

    Custom guardrails registered via ``register_custom`` take
    precedence over built-in handling for the same name.
    """

    def __init__(self) -> None:
        """Initialize the provider with lazy Presidio detection."""
        self._presidio: _PresidioBackend | None = None
        self._custom: dict[str, GuardrailFunc] = {}
        self._parent_ctx: WorkflowContext | None = None

    # -- custom guardrail registration ------------------------------------

    def register_custom(self, name: str, func: GuardrailFunc) -> None:
        """Register a custom guardrail function.

        Args:
            name: Guardrail name used in DSL (e.g. ``mask my_guard``).
            func: Callable accepting a message string.

        """
        self._custom[name] = func
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

            # Custom guardrail takes precedence — receives full content
            if guardrail in self._custom:
                result = await self._call_custom(
                    guardrail, content, expect_str=True,
                )
                masked: GuardrailContent = str(result)
                triggered = masked != _serialize_content(content)
                _set_triggered_output(
                    span, triggered=triggered, output_value=str(masked),
                )
                return masked

            if isinstance(content, ToolCallContent):
                # Tool call args rarely need masking — pass through
                _set_triggered_output(span, triggered=False)
                return content

            if isinstance(content, ToolResultContent):
                masked_result = self._mask_tool_result(
                    guardrail, content,
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
            masked_str = self._mask_str(guardrail, content)
            triggered = masked_str != content
            _set_triggered_output(
                span,
                triggered=triggered,
                output_value=masked_str if triggered else None,
            )
            return masked_str

    def _mask_str(self, guardrail: str, message: str) -> str:
        """Apply masking to a plain string.

        Args:
            guardrail: Name of the guardrail.
            message: Text to mask.

        Returns:
            Masked text.

        """
        if guardrail != "pii":
            logger.warning(
                "Unknown guardrail type for masking: %s", guardrail,
            )
            return message
        backend = self._require_presidio()
        return backend.mask_pii(message)

    def _mask_tool_result(
        self,
        guardrail: str,
        content: ToolResultContent,
    ) -> ToolResultContent:
        """Apply masking to inspectable fields in a tool result.

        Args:
            guardrail: Name of the guardrail.
            content: Tool result content to mask.

        Returns:
            New ToolResultContent with masked fields.

        """
        if guardrail != "pii":
            logger.warning(
                "Unknown guardrail type for masking: %s", guardrail,
            )
            return content
        backend = self._require_presidio()
        masked_data = _mask_fields(
            content.data, backend.mask_pii,
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

            # Custom guardrail takes precedence
            if guardrail in self._custom:
                result = await self._call_custom(
                    guardrail, content, expect_str=False,
                )
                triggered = bool(result)
                if triggered:
                    detail = f"custom guardrail '{guardrail}' triggered"
            elif isinstance(content, ToolResultContent):
                triggered, detail = self._check_tool_result(
                    guardrail, content,
                )
            elif isinstance(content, ToolCallContent):
                # Check tool call args as JSON string
                text = json.dumps(content.data, default=str)
                triggered, detail = self._check_str(guardrail, text)
            else:
                triggered, detail = self._check_str(guardrail, content)

            span.set_attribute(
                "streetrace.guardrail.triggered", triggered,
            )
            span.set_attribute(
                SpanAttributes.OUTPUT_VALUE,
                detail if triggered else "not triggered",
            )
            return triggered

    def _check_str(
        self, guardrail: str, text: str,
    ) -> tuple[bool, str]:
        """Check a plain string against a guardrail.

        Args:
            guardrail: Name of the guardrail.
            text: Text to check.

        Returns:
            Tuple of (triggered, detail).

        """
        if guardrail != "jailbreak":
            logger.warning(
                "Unknown guardrail type for checking: %s", guardrail,
            )
            return False, ""
        for pattern in _JAILBREAK_PATTERNS:
            if pattern.search(text):
                logger.warning(
                    "Jailbreak attempt detected: pattern=%s",
                    pattern.pattern,
                )
                return True, (
                    f"triggered: pattern match "
                    f"({pattern.pattern})"
                )
        return False, ""

    def _check_tool_result(
        self,
        guardrail: str,
        content: ToolResultContent,
    ) -> tuple[bool, str]:
        """Check inspectable fields in a tool result.

        Only inspect user-facing fields (``output``, ``stdout``) —
        error messages are system-generated and would cause false
        positives.

        Args:
            guardrail: Name of the guardrail.
            content: Tool result content to check.

        Returns:
            Tuple of (triggered, detail).

        """
        return _check_fields(
            content.data,
            lambda text: self._check_str(guardrail, text)[0],
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

    # -- internals --------------------------------------------------------

    def _require_presidio(self) -> _PresidioBackend:
        """Return a Presidio backend, installing deps if necessary.

        Attempt order:
        1. Return cached backend if already loaded.
        2. Try importing Presidio.
        3. If missing, attempt ``pip install streetrace[guardrails]``.
        4. Try importing again.
        5. If still missing, raise ``MissingDependencyError``.

        Returns:
            Initialized _PresidioBackend.

        Raises:
            MissingDependencyError: If Presidio cannot be loaded or installed.

        """
        if self._presidio is not None:
            return self._presidio

        # First attempt — maybe it's already installed
        if self._try_load_presidio():
            return self._presidio  # type: ignore[return-value]

        # Attempt runtime install
        logger.warning(
            "Presidio not found. Attempting runtime install: %s",
            INSTALL_COMMAND,
        )
        if self._attempt_runtime_install() and self._try_load_presidio():
            logger.info("Presidio installed successfully at runtime")
            return self._presidio  # type: ignore[return-value]

        # Cannot proceed
        raise MissingDependencyError(
            package="presidio-analyzer",
            install_command=INSTALL_COMMAND,
        )

    def _try_load_presidio(self) -> bool:
        """Try to import Presidio and create the backend.

        Returns:
            True if Presidio loaded successfully.

        """
        try:
            import importlib

            importlib.import_module("presidio_analyzer")
            importlib.import_module("presidio_anonymizer")
            self._ensure_spacy_model()
            self._presidio = _PresidioBackend()
            logger.info("Presidio engines loaded for PII detection")
        except (ModuleNotFoundError, ImportError):
            return False
        else:
            return True

    @staticmethod
    def _attempt_runtime_install() -> bool:
        """Try to pip-install guardrail dependencies.

        Returns:
            True if the install command succeeded.

        """
        import subprocess  # nosec B404 — controlled internal use only
        import sys

        try:
            subprocess.check_call(  # noqa: S603 # nosec B603 — controlled internal install
                [
                    sys.executable, "-m", "pip", "install",
                    "presidio-analyzer", "presidio-anonymizer", "spacy",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
            logger.warning("Runtime install of Presidio failed: %s", exc)
            return False
        else:
            return True

    @staticmethod
    def _ensure_spacy_model() -> None:
        """Download the spaCy model if missing."""
        import importlib

        spacy = importlib.import_module("spacy")
        model_name = "en_core_web_lg"
        try:
            spacy.load(model_name)
        except OSError:
            logger.info("Downloading spaCy model %s ...", model_name)
            from spacy.cli import download

            download(model_name)

    async def _call_custom(
        self,
        name: str,
        content: GuardrailContent,
        *,
        expect_str: bool,
    ) -> str | bool:
        """Invoke a registered custom guardrail.

        Handle both sync and async callables.

        Args:
            name: Guardrail name.
            content: Input content (str or structured).
            expect_str: When True, coerce result to str for masking.

        Returns:
            Result from the custom guardrail function.

        """
        import asyncio
        import inspect

        func = self._custom[name]
        result = func(content)
        if inspect.isawaitable(result) or asyncio.iscoroutine(result):
            result = await result

        if expect_str:
            return str(result)
        return bool(result)


# ---------------------------------------------------------------------------
# Module-level OTEL helpers
# ---------------------------------------------------------------------------


def _mask_fields(
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


def _check_fields(
    data: dict[str, object],
    check_fn: Callable[[str], bool],
) -> tuple[bool, str]:
    """Check inspectable content fields for guardrail triggers.

    Iterate ``INSPECTABLE_FIELDS_CHECK`` and return on first trigger.

    Args:
        data: Tool result dict.
        check_fn: Function that returns True if content triggers.

    Returns:
        Tuple of (triggered, detail).

    """
    for field in INSPECTABLE_FIELDS_CHECK:
        value = data.get(field)
        if isinstance(value, str) and value and check_fn(value):
            return True, f"triggered in field '{field}'"
    return False, ""


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
