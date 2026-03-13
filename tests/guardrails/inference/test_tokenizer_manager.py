"""Tests for the tokenizer manager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from streetrace.dsl.runtime.errors import MissingDependencyError
from streetrace.guardrails.inference.tokenizer_manager import TokenizerManager


@pytest.fixture
def manager() -> TokenizerManager:
    """Create a fresh tokenizer manager."""
    return TokenizerManager()


@pytest.fixture
def mock_tokenizer() -> MagicMock:
    """Create a mock tokenizer with encode method."""
    tokenizer = MagicMock()
    encoding = MagicMock()
    encoding.ids = [101, 2023, 2003, 1037, 3231, 102]
    encoding.attention_mask = [1, 1, 1, 1, 1, 1]
    tokenizer.encode = MagicMock(return_value=encoding)
    return tokenizer


class TestTokenizerLoading:
    """Verify tokenizer loading and caching."""

    def test_register_tokenizer(
        self,
        manager: TokenizerManager,
        mock_tokenizer: MagicMock,
    ) -> None:
        manager.register("model-a", mock_tokenizer)
        assert manager.has_tokenizer("model-a") is True

    def test_has_tokenizer_false_for_unregistered(
        self,
        manager: TokenizerManager,
    ) -> None:
        assert manager.has_tokenizer("unknown") is False

    def test_tokenize_with_registered_tokenizer(
        self,
        manager: TokenizerManager,
        mock_tokenizer: MagicMock,
    ) -> None:
        manager.register("model-a", mock_tokenizer)
        result = manager.tokenize("model-a", "this is a test")
        assert result.input_ids == [101, 2023, 2003, 1037, 3231, 102]
        assert result.attention_mask == [1, 1, 1, 1, 1, 1]

    def test_tokenize_unregistered_raises(
        self,
        manager: TokenizerManager,
    ) -> None:
        with pytest.raises(
            MissingDependencyError,
            match="Tokenizer for 'unknown'",
        ):
            manager.tokenize("unknown", "text")


class TestTokenizerFromPath:
    """Verify tokenizer loading from filesystem path."""

    def test_load_from_path_imports_tokenizers(
        self,
        manager: TokenizerManager,
        mock_tokenizer: MagicMock,
    ) -> None:
        with patch(
            "streetrace.guardrails.inference.tokenizer_manager"
            "._load_tokenizer_from_path",
            return_value=mock_tokenizer,
        ):
            manager.load_from_path("model-a", "/path/to/tokenizer")

        assert manager.has_tokenizer("model-a") is True

    def test_load_from_path_import_error_raises(
        self,
        manager: TokenizerManager,
    ) -> None:
        with (
            patch(
                "streetrace.guardrails.inference.tokenizer_manager"
                "._load_tokenizer_from_path",
                side_effect=ImportError("No module named 'tokenizers'"),
            ),
            pytest.raises(MissingDependencyError, match="tokenizers"),
        ):
            manager.load_from_path("model-a", "/path/to/tokenizer")


class TestTokenizerMaxLength:
    """Verify max token length enforcement."""

    def test_truncation_applied(
        self,
        manager: TokenizerManager,
        mock_tokenizer: MagicMock,
    ) -> None:
        manager.register("model-a", mock_tokenizer)
        manager.tokenize("model-a", "text", max_length=512)
        mock_tokenizer.encode.assert_called_once()
