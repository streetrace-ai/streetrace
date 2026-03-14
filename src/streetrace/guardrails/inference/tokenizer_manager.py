"""Tokenizer manager for HuggingFace tokenizers.

Load and cache tokenizers alongside their ONNX models, providing
model-specific tokenization with max length enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass

from streetrace.dsl.runtime.errors import MissingDependencyError
from streetrace.log import get_logger

logger = get_logger(__name__)

TOKENIZERS_PACKAGE = "tokenizers"
"""Package name for HuggingFace tokenizers."""

TOKENIZERS_INSTALL_COMMAND = "pip install tokenizers"
"""Install command for HuggingFace tokenizers."""

DEFAULT_MAX_LENGTH = 512
"""Default maximum token length for tokenization."""


@dataclass(frozen=True)
class TokenizerOutput:
    """Result of tokenizing text.

    Attributes:
        input_ids: Token IDs from the tokenizer.
        attention_mask: Attention mask (1 for real tokens, 0 for padding).

    """

    input_ids: list[int]
    attention_mask: list[int]


class TokenizerManager:
    """Manage tokenizers for ONNX models.

    Register tokenizers by model ID and provide tokenization with
    configurable max length truncation.
    """

    def __init__(self) -> None:
        """Initialize with an empty tokenizer registry."""
        self._tokenizers: dict[str, object] = {}

    def register(self, model_id: str, tokenizer: object) -> None:
        """Register a tokenizer for a model.

        Args:
            model_id: Model identifier.
            tokenizer: A tokenizer instance (e.g., from HuggingFace).

        """
        self._tokenizers[model_id] = tokenizer
        logger.info("Registered tokenizer for %s", model_id)

    def has_tokenizer(self, model_id: str) -> bool:
        """Check if a tokenizer is registered for the given model.

        Args:
            model_id: Model identifier.

        Returns:
            True if a tokenizer is registered.

        """
        return model_id in self._tokenizers

    def tokenize(
        self,
        model_id: str,
        text: str,
        *,
        max_length: int = DEFAULT_MAX_LENGTH,
    ) -> TokenizerOutput:
        """Tokenize text using the model's registered tokenizer.

        Args:
            model_id: Model identifier.
            text: Text to tokenize.
            max_length: Maximum number of tokens.

        Returns:
            TokenizerOutput with input_ids and attention_mask.

        Raises:
            MissingDependencyError: If no tokenizer is registered.

        """
        tokenizer = self._tokenizers.get(model_id)
        if tokenizer is None:
            raise MissingDependencyError(
                package=f"Tokenizer for '{model_id}'",
                install_command=TOKENIZERS_INSTALL_COMMAND,
            )

        encoding = tokenizer.encode(text)  # type: ignore[attr-defined]
        input_ids = encoding.ids[:max_length]
        attention_mask = encoding.attention_mask[:max_length]

        return TokenizerOutput(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

    def load_from_path(self, model_id: str, path: str) -> None:
        """Load a tokenizer from a filesystem path.

        Args:
            model_id: Model identifier.
            path: Path to the tokenizer directory or file.

        Raises:
            MissingDependencyError: If tokenizers package is not installed.

        """
        try:
            tokenizer = _load_tokenizer_from_path(path)
        except ImportError:
            raise MissingDependencyError(
                package=TOKENIZERS_PACKAGE,
                install_command=TOKENIZERS_INSTALL_COMMAND,
            ) from None

        self.register(model_id, tokenizer)
        logger.info("Loaded tokenizer for %s from %s", model_id, path)


def _load_tokenizer_from_path(path: str) -> object:
    """Load a HuggingFace tokenizer from a filesystem path.

    Args:
        path: Path to the tokenizer JSON file or directory.

    Returns:
        A tokenizers.Tokenizer instance.

    Raises:
        ImportError: If the tokenizers package is not installed.

    """
    from tokenizers import Tokenizer

    return Tokenizer.from_file(path)
