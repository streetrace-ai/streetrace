"""Turn embedder for generating per-turn MiniLM embeddings.

Generate fixed-size embedding vectors per conversation turn via
the shared InferencePipeline, with content-hash-based caching.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from streetrace.dsl.runtime.errors import MissingDependencyError
from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.guardrails.inference.pipeline import InferencePipeline

logger = get_logger(__name__)

EMBEDDING_MODEL_ID = "minilm-l6-v2"
"""Model identifier for MiniLM embedding inference."""

ONNX_PACKAGE = "onnxruntime"
"""Package name for ONNX Runtime dependency."""

ONNX_INSTALL_COMMAND = "pip install onnxruntime"
"""Install command shown when ONNX is unavailable."""


class TurnEmbedder:
    """Generate per-turn embeddings with content-hash caching.

    Use the shared InferencePipeline for MiniLM inference. Cache
    results keyed by SHA-256 text hash to avoid re-computation.
    """

    def __init__(
        self,
        *,
        inference_pipeline: InferencePipeline | None,
    ) -> None:
        """Initialize the embedder.

        Args:
            inference_pipeline: ONNX inference facade, or None.

        """
        self._pipeline = inference_pipeline
        self._cache: dict[str, list[float]] = {}

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding for the given text.

        Check the local cache first. On miss, delegate to the
        InferencePipeline.

        Args:
            text: Turn text to embed.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            MissingDependencyError: If inference pipeline is None.

        """
        if self._pipeline is None:
            raise MissingDependencyError(
                ONNX_PACKAGE, ONNX_INSTALL_COMMAND,
            )

        cache_key = self._hash_text(text)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for turn embedding")
            return cached

        embedding = await self._pipeline.get_embedding(
            EMBEDDING_MODEL_ID, text,
        )
        self._cache[cache_key] = embedding
        logger.debug("Generated and cached turn embedding")
        return embedding

    def embed_sync(self, text: str) -> list[float] | None:
        """Return a cached embedding synchronously, or None.

        Check the local cache only. If no cached embedding exists,
        return None so the caller can fall back to a hash-based
        pseudo-embedding. The async ``embed`` method populates
        the cache.

        Args:
            text: Turn text to look up.

        Returns:
            Cached embedding vector, or None if not cached.

        """
        if self._pipeline is None:
            return None

        cache_key = self._hash_text(text)
        return self._cache.get(cache_key)

    @staticmethod
    def _hash_text(text: str) -> str:
        """Compute SHA-256 hash of text for cache keying.

        Args:
            text: Text to hash.

        Returns:
            Hex digest string.

        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
