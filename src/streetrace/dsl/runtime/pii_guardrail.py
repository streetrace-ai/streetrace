"""PII masking guardrail using Microsoft Presidio.

Detect and anonymize personally identifiable information.
This is a mask-only guardrail — checking always returns not triggered.
"""

from __future__ import annotations

from streetrace.dsl.runtime.errors import MissingDependencyError
from streetrace.log import get_logger

logger = get_logger(__name__)

INSTALL_COMMAND = "pip install 'streetrace[guardrails]'"
"""Command users should run to install guardrail dependencies."""

_EXCLUDED_ENTITY_TYPES = frozenset({
    "URL",
    "DATE_TIME",
})
"""Entity types excluded from PII masking.

URLs and dates are not personally identifiable information. Presidio's
URL recognizer false-positives on file paths (``README.md``) and its
DATE_TIME recognizer matches time references (``5 minutes``) in
documentation content.
"""


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
            Text with PII entities replaced by type-specific placeholders
            such as ``[MASKED_EMAIL_ADDRESS]`` or ``[MASKED_PHONE_NUMBER]``.

        """
        from presidio_anonymizer.entities import OperatorConfig

        all_results = self._analyzer.analyze(text=text, language="en")
        results = [
            r for r in all_results
            if r.entity_type not in _EXCLUDED_ENTITY_TYPES
        ]
        operators = {
            r.entity_type: OperatorConfig(
                "replace",
                {"new_value": f"[MASKED_{r.entity_type}]"},
            )
            for r in results
        }
        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        return str(anonymized.text)


class PiiGuardrail:
    """Mask PII using Microsoft Presidio.

    This is a mask-only guardrail. ``check_str`` always returns
    ``(False, "")``. PII masking requires Presidio — if not installed,
    a runtime install is attempted; if that also fails, a clear error
    is raised.
    """

    def __init__(self) -> None:
        """Initialize with lazy Presidio detection."""
        self._presidio: _PresidioBackend | None = None

    @property
    def name(self) -> str:
        """Return the guardrail name."""
        return "pii"

    def mask_str(self, text: str) -> str:
        """Mask PII in *text* using Presidio.

        Args:
            text: Input text to mask.

        Returns:
            Text with PII replaced by type-specific placeholders.

        Raises:
            MissingDependencyError: If Presidio is unavailable.

        """
        backend = self._require_presidio()
        return backend.mask_pii(text)

    def check_str(self, text: str) -> tuple[bool, str]:  # noqa: ARG002
        """Return not triggered — PII is mask-only.

        Args:
            text: Input text (unused).

        Returns:
            Always ``(False, "")``.

        """
        return False, ""

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

        if self._try_load_presidio():
            return self._presidio  # type: ignore[return-value]

        logger.warning(
            "Presidio not found. Attempting runtime install: %s",
            INSTALL_COMMAND,
        )
        if self._attempt_runtime_install() and self._try_load_presidio():
            logger.info("Presidio installed successfully at runtime")
            return self._presidio  # type: ignore[return-value]

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
