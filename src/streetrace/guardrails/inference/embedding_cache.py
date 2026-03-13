"""LRU embedding cache with TTL and OTEL metrics.

Cache embedding vectors keyed by SHA-256 content hash with
configurable max entries, TTL, and optional metrics recording.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Protocol

from streetrace.log import get_logger

logger = get_logger(__name__)


class CacheMetrics(Protocol):
    """Protocol for cache metrics recording."""

    def record_hit(self) -> None:
        """Record a cache hit."""
        ...

    def record_miss(self) -> None:
        """Record a cache miss."""
        ...


@dataclass
class _CacheEntry:
    """Internal cache entry with embedding and timestamp."""

    embedding: list[float]
    created_at: float = field(default_factory=time.monotonic)


class EmbeddingCache:
    """LRU cache for embedding vectors keyed by content hash.

    Store embeddings with TTL-based expiry and LRU eviction when
    the maximum number of entries is reached. Optionally record
    hit/miss metrics via an injected metrics recorder.
    """

    def __init__(
        self,
        *,
        max_entries: int = 10_000,
        ttl_seconds: float = 3600.0,
        metrics: CacheMetrics | None = None,
    ) -> None:
        """Initialize the embedding cache.

        Args:
            max_entries: Maximum number of cached embeddings.
            ttl_seconds: Time-to-live for cache entries in seconds.
            metrics: Optional metrics recorder for hit/miss tracking.

        """
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._metrics = metrics
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()

    @property
    def size(self) -> int:
        """Return current number of cached entries."""
        return len(self._entries)

    def get(
        self,
        model_id: str,
        text: str,
    ) -> list[float] | None:
        """Look up a cached embedding by model and text.

        Args:
            model_id: Model identifier used for embedding.
            text: Input text that was embedded.

        Returns:
            Cached embedding vector, or None on miss/expiry.

        """
        key = self._make_key(model_id, text)
        entry = self._entries.get(key)

        if entry is None:
            if self._metrics is not None:
                self._metrics.record_miss()
            return None

        elapsed = time.monotonic() - entry.created_at
        if elapsed > self._ttl_seconds:
            del self._entries[key]
            if self._metrics is not None:
                self._metrics.record_miss()
            return None

        # Move to end for LRU ordering
        self._entries.move_to_end(key)

        if self._metrics is not None:
            self._metrics.record_hit()

        return entry.embedding

    def put(
        self,
        model_id: str,
        text: str,
        embedding: list[float],
    ) -> None:
        """Store an embedding in the cache.

        Args:
            model_id: Model identifier used for embedding.
            text: Input text that was embedded.
            embedding: The embedding vector to cache.

        """
        key = self._make_key(model_id, text)

        if key in self._entries:
            self._entries.move_to_end(key)
            self._entries[key] = _CacheEntry(embedding=embedding)
            return

        # Evict oldest if at capacity
        while len(self._entries) >= self._max_entries:
            evicted_key, _ = self._entries.popitem(last=False)
            logger.debug("Evicted cache entry %s", evicted_key[:16])

        self._entries[key] = _CacheEntry(embedding=embedding)

    @staticmethod
    def _make_key(model_id: str, text: str) -> str:
        """Create a cache key from model ID and text content hash.

        Args:
            model_id: Model identifier.
            text: Input text.

        Returns:
            A string key combining model_id and content SHA-256.

        """
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{model_id}:{content_hash}"
