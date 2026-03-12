"""Tests for PiiGuardrail."""

from unittest.mock import MagicMock, patch

import pytest

from streetrace.dsl.runtime.errors import MissingDependencyError
from streetrace.dsl.runtime.pii_guardrail import PiiGuardrail


class TestPiiGuardrailProperties:
    """Test guardrail identity and protocol conformance."""

    def test_name_is_pii(self):
        """Guardrail name is 'pii'."""
        guard = PiiGuardrail()
        assert guard.name == "pii"

    def test_check_str_always_returns_not_triggered(self):
        """check_str always returns (False, '') — PII is mask-only."""
        guard = PiiGuardrail()
        triggered, detail = guard.check_str("John Doe john@example.com")
        assert triggered is False
        assert detail == ""


class TestPiiMasking:
    """Test mask_str delegates to Presidio."""

    def test_mask_str_delegates_to_presidio(self):
        """mask_str uses Presidio backend for PII detection."""
        guard = PiiGuardrail()
        mock_backend = MagicMock()
        mock_backend.mask_pii.return_value = "Hello [PII]"
        guard._presidio = mock_backend  # noqa: SLF001

        result = guard.mask_str("Hello John")

        assert result == "Hello [PII]"
        mock_backend.mask_pii.assert_called_once_with("Hello John")


class TestPresidioBackendMasking:
    """Test _PresidioBackend builds per-entity-type operators."""

    def test_operators_use_entity_type_placeholders(self):
        """Each detected entity type gets a [MASKED_<TYPE>] placeholder."""
        from streetrace.dsl.runtime.pii_guardrail import _PresidioBackend

        backend = object.__new__(_PresidioBackend)

        mock_result_email = MagicMock()
        mock_result_email.entity_type = "EMAIL_ADDRESS"
        mock_result_person = MagicMock()
        mock_result_person.entity_type = "PERSON"

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = [
            mock_result_email,
            mock_result_person,
        ]
        backend._analyzer = mock_analyzer  # noqa: SLF001

        mock_anonymized = MagicMock()
        mock_anonymized.text = "Hi [MASKED_PERSON] at [MASKED_EMAIL_ADDRESS]"
        mock_anonymizer = MagicMock()
        mock_anonymizer.anonymize.return_value = mock_anonymized
        backend._anonymizer = mock_anonymizer  # noqa: SLF001

        result = backend.mask_pii("Hi John at john@example.com")

        assert result == "Hi [MASKED_PERSON] at [MASKED_EMAIL_ADDRESS]"

        call_kwargs = mock_anonymizer.anonymize.call_args[1]
        operators = call_kwargs["operators"]
        assert "EMAIL_ADDRESS" in operators
        assert "PERSON" in operators
        assert "DEFAULT" not in operators

    def test_no_entities_produces_empty_operators(self):
        """When no PII is detected, operators dict is empty."""
        from streetrace.dsl.runtime.pii_guardrail import _PresidioBackend

        backend = object.__new__(_PresidioBackend)

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = []
        backend._analyzer = mock_analyzer  # noqa: SLF001

        mock_anonymized = MagicMock()
        mock_anonymized.text = "No PII here"
        mock_anonymizer = MagicMock()
        mock_anonymizer.anonymize.return_value = mock_anonymized
        backend._anonymizer = mock_anonymizer  # noqa: SLF001

        result = backend.mask_pii("No PII here")

        assert result == "No PII here"
        call_kwargs = mock_anonymizer.anonymize.call_args[1]
        assert call_kwargs["operators"] == {}


class TestPresidioLazyInit:
    """Test lazy initialization of Presidio backend."""

    def test_presidio_not_loaded_on_init(self):
        """Presidio backend is not loaded at construction time."""
        guard = PiiGuardrail()
        assert guard._presidio is None  # noqa: SLF001

    def test_cached_backend_returned(self):
        """Cached Presidio backend is returned without re-loading."""
        guard = PiiGuardrail()
        mock_backend = MagicMock()
        guard._presidio = mock_backend  # noqa: SLF001

        result = guard._require_presidio()  # noqa: SLF001
        assert result is mock_backend

    def test_missing_presidio_raises_with_clear_message(self):
        """Missing Presidio raises MissingDependencyError."""
        guard = PiiGuardrail()

        with (
            patch.object(
                PiiGuardrail,
                "_try_load_presidio",
                return_value=False,
            ),
            patch.object(
                PiiGuardrail,
                "_attempt_runtime_install",
                return_value=False,
            ),
            pytest.raises(MissingDependencyError) as exc_info,
        ):
            guard._require_presidio()  # noqa: SLF001

        assert exc_info.value.package == "presidio-analyzer"
        assert "streetrace[guardrails]" in exc_info.value.install_command

    def test_spacy_model_download_triggered(self):
        """Missing spaCy model triggers download."""
        mock_spacy = MagicMock()
        mock_spacy.load.side_effect = OSError("Model not found")
        mock_download = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "spacy": mock_spacy,
                    "spacy.cli": MagicMock(download=mock_download),
                },
            ),
            patch(
                "importlib.import_module",
                return_value=mock_spacy,
            ),
        ):
            PiiGuardrail._ensure_spacy_model()  # noqa: SLF001

        mock_spacy.load.assert_called_once_with("en_core_web_lg")
