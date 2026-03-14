"""Inference pipeline facade combining registry, pool, cache, and tokenizer.

Provide a unified API for embedding generation, classification, and
batch operations with caching and fail-fast error handling.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from streetrace.guardrails.inference.model_registry import ModelState
from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.guardrails.inference.embedding_cache import (
        EmbeddingCache,
    )
    from streetrace.guardrails.inference.model_registry import (
        ModelRegistry,
    )
    from streetrace.guardrails.inference.session_pool import SessionPool
    from streetrace.guardrails.inference.tokenizer_manager import (
        TokenizerManager,
    )

logger = get_logger(__name__)


class InferencePipeline:
    """Facade combining model registry, session pool, cache, and tokenizer.

    Provide high-level inference operations that handle caching,
    tokenization, session management, and error propagation.
    """

    def __init__(
        self,
        *,
        registry: ModelRegistry,
        pool: SessionPool,
        cache: EmbeddingCache,
        tokenizer_manager: TokenizerManager,
    ) -> None:
        """Initialize the inference pipeline.

        Args:
            registry: Model registry for state tracking.
            pool: Session pool for ONNX sessions.
            cache: Embedding cache for deduplication.
            tokenizer_manager: Tokenizer manager for text encoding.

        """
        self._registry = registry
        self._pool = pool
        self._cache = cache
        self._tokenizer_manager = tokenizer_manager

    async def get_embedding(
        self,
        model_id: str,
        text: str,
    ) -> list[float]:
        """Generate an embedding vector for the given text.

        Check the cache first. On miss, tokenize, run inference,
        cache the result, and return it.

        Args:
            model_id: Model identifier.
            text: Input text to embed.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            MissingDependencyError: If the model is unavailable.

        """
        cached = self._cache.get(model_id, text)
        if cached is not None:
            return cached

        # Ensure model is loaded (may trigger load or raise)
        await self._registry.get_session(model_id)

        session = await self._pool.acquire(model_id)
        try:
            tokens = self._tokenizer_manager.tokenize(model_id, text)
            result = session.run(  # type: ignore[attr-defined]
                None,
                {
                    "input_ids": [tokens.input_ids],
                    "attention_mask": [tokens.attention_mask],
                },
            )
            embedding = _extract_embedding(result)
            self._cache.put(model_id, text, embedding)
            return embedding
        finally:
            self._pool.release(model_id, session)

    async def classify(
        self,
        model_id: str,
        text: str,
        *,
        labels: list[str] | None = None,
    ) -> dict[str, float]:
        """Run classification inference on the given text.

        Args:
            model_id: Model identifier.
            text: Input text to classify.
            labels: Optional label names for output keys.

        Returns:
            Dictionary mapping label names to probabilities.

        Raises:
            MissingDependencyError: If the model is unavailable.

        """
        await self._registry.get_session(model_id)

        session = await self._pool.acquire(model_id)
        try:
            tokens = self._tokenizer_manager.tokenize(model_id, text)
            result = session.run(  # type: ignore[attr-defined]
                None,
                {
                    "input_ids": [tokens.input_ids],
                    "attention_mask": [tokens.attention_mask],
                },
            )
            probabilities = _extract_probabilities(result)

            if labels is not None:
                return dict(zip(labels, probabilities, strict=False))
            return {
                str(i): prob for i, prob in enumerate(probabilities)
            }
        finally:
            self._pool.release(model_id, session)

    async def batch_embed(
        self,
        model_id: str,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Check cache for each text individually. Run inference
        only for cache misses.

        Args:
            model_id: Model identifier.
            texts: List of input texts.

        Returns:
            List of embedding vectors.

        Raises:
            MissingDependencyError: If the model is unavailable.

        """
        tasks = [
            asyncio.create_task(self.get_embedding(model_id, text))
            for text in texts
        ]

        results: list[list[float]] = await asyncio.gather(*tasks)
        return list(results)

    def is_model_ready(self, model_id: str) -> bool:
        """Check if a model is loaded and ready for inference.

        Args:
            model_id: Model identifier.

        Returns:
            True if the model state is READY.

        """
        return self._registry.get_state(model_id) == ModelState.READY

    async def warm_up(self, model_ids: list[str]) -> None:
        """Pre-load models in background.

        Trigger loading for all specified models concurrently.
        Errors are logged but not raised (warm-up is best-effort
        during startup).

        Args:
            model_ids: List of model identifiers to load.

        """
        tasks = [
            self._registry.get_session(model_id)
            for model_id in model_ids
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        for model_id, result in zip(model_ids, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning(
                    "Failed to warm up model %s: %s",
                    model_id,
                    result,
                )
            else:
                logger.info("Warmed up model %s", model_id)


def _to_nested_list(raw: object) -> list[list[list[float]]]:
    """Convert raw ONNX output to a nested list structure.

    Args:
        raw: Raw output from ONNX inference (ndarray or list).

    Returns:
        Nested list in [batch, sequence, features] shape.

    """
    converted = raw.tolist() if hasattr(raw, "tolist") else raw

    if not isinstance(converted, list):
        return [[[float(converted)]]]  # type: ignore[arg-type]

    if len(converted) == 0:
        return [[[]]]

    first = converted[0]
    if not isinstance(first, list):
        return [[_as_floats(converted)]]

    second = first[0] if len(first) > 0 else None
    if not isinstance(second, list):
        return [[_as_floats(item) for item in converted]]

    return [
        [_as_floats(token) for token in batch]
        for batch in converted
    ]


def _as_floats(values: list[object]) -> list[float]:
    """Convert a list of numeric values to floats.

    Args:
        values: List of numeric values.

    Returns:
        List of float values.

    """
    return [float(v) for v in values]  # type: ignore[arg-type]


def _extract_embedding(result: list[object]) -> list[float]:
    """Extract embedding vector from ONNX inference output.

    Apply mean pooling over token dimension for transformer outputs
    shaped [batch, tokens, hidden_dim].

    Args:
        result: Raw ONNX inference output.

    Returns:
        Embedding vector as a list of floats.

    """
    nested = _to_nested_list(result[0])
    batch = nested[0]

    if len(batch) == 1:
        return batch[0]

    dim = len(batch[0])
    pooled = [0.0] * dim
    for token in batch:
        for i, val in enumerate(token):
            pooled[i] += val
    return [v / len(batch) for v in pooled]


def _extract_probabilities(result: list[object]) -> list[float]:
    """Extract classification probabilities from ONNX output.

    Args:
        result: Raw ONNX inference output.

    Returns:
        List of class probabilities.

    """
    nested = _to_nested_list(result[0])
    return nested[0][0]
