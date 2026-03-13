"""Tests for the embedding cache with LRU eviction and TTL."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from streetrace.guardrails.inference.embedding_cache import EmbeddingCache

SAMPLE_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5]
DIFFERENT_EMBEDDING = [0.9, 0.8, 0.7, 0.6, 0.5]


@pytest.fixture
def cache() -> EmbeddingCache:
    """Create a cache with default settings."""
    return EmbeddingCache(max_entries=100, ttl_seconds=3600)


@pytest.fixture
def small_cache() -> EmbeddingCache:
    """Create a cache with small capacity for eviction tests."""
    return EmbeddingCache(max_entries=3, ttl_seconds=3600)


@pytest.fixture
def short_ttl_cache() -> EmbeddingCache:
    """Create a cache with very short TTL for expiry tests."""
    return EmbeddingCache(max_entries=100, ttl_seconds=0.05)


@pytest.fixture
def mock_metrics() -> MagicMock:
    """Create a mock metrics recorder."""
    return MagicMock()


class TestCacheHitMiss:
    """Verify cache hit and miss behavior."""

    def test_cache_miss_returns_none(self, cache: EmbeddingCache) -> None:
        result = cache.get("model-a", "some text")
        assert result is None

    def test_put_then_get_returns_embedding(
        self,
        cache: EmbeddingCache,
    ) -> None:
        cache.put("model-a", "hello world", SAMPLE_EMBEDDING)
        result = cache.get("model-a", "hello world")
        assert result == SAMPLE_EMBEDDING

    def test_same_text_different_model_is_separate(
        self,
        cache: EmbeddingCache,
    ) -> None:
        cache.put("model-a", "hello", SAMPLE_EMBEDDING)
        cache.put("model-b", "hello", DIFFERENT_EMBEDDING)
        assert cache.get("model-a", "hello") == SAMPLE_EMBEDDING
        assert cache.get("model-b", "hello") == DIFFERENT_EMBEDDING

    def test_content_hash_keying(self, cache: EmbeddingCache) -> None:
        """Same text always returns cached embedding."""
        cache.put("model-a", "identical text", SAMPLE_EMBEDDING)
        result = cache.get("model-a", "identical text")
        assert result == SAMPLE_EMBEDDING


class TestLruEviction:
    """Verify LRU eviction when max entries exceeded."""

    def test_evicts_oldest_entry(self, small_cache: EmbeddingCache) -> None:
        small_cache.put("m", "text1", [1.0])
        small_cache.put("m", "text2", [2.0])
        small_cache.put("m", "text3", [3.0])

        # Adding a 4th should evict text1
        small_cache.put("m", "text4", [4.0])

        assert small_cache.get("m", "text1") is None
        assert small_cache.get("m", "text2") == [2.0]

    def test_access_refreshes_lru_order(
        self,
        small_cache: EmbeddingCache,
    ) -> None:
        small_cache.put("m", "text1", [1.0])
        small_cache.put("m", "text2", [2.0])
        small_cache.put("m", "text3", [3.0])

        # Access text1 to refresh it
        small_cache.get("m", "text1")

        # Adding text4 should evict text2 (oldest not-recently-accessed)
        small_cache.put("m", "text4", [4.0])

        assert small_cache.get("m", "text1") == [1.0]
        assert small_cache.get("m", "text2") is None


class TestTtlExpiry:
    """Verify TTL-based cache expiry."""

    def test_expired_entry_returns_none(
        self,
        short_ttl_cache: EmbeddingCache,
    ) -> None:
        short_ttl_cache.put("m", "text", SAMPLE_EMBEDDING)
        time.sleep(0.06)
        assert short_ttl_cache.get("m", "text") is None

    def test_fresh_entry_returns_value(
        self,
        short_ttl_cache: EmbeddingCache,
    ) -> None:
        short_ttl_cache.put("m", "text", SAMPLE_EMBEDDING)
        assert short_ttl_cache.get("m", "text") == SAMPLE_EMBEDDING


class TestCacheMetrics:
    """Verify OTEL metrics emission for cache hits and misses."""

    def test_hit_counter_incremented(
        self,
        mock_metrics: MagicMock,
    ) -> None:
        cache = EmbeddingCache(
            max_entries=100,
            ttl_seconds=3600,
            metrics=mock_metrics,
        )
        cache.put("m", "text", SAMPLE_EMBEDDING)
        cache.get("m", "text")

        mock_metrics.record_hit.assert_called_once()

    def test_miss_counter_incremented(
        self,
        mock_metrics: MagicMock,
    ) -> None:
        cache = EmbeddingCache(
            max_entries=100,
            ttl_seconds=3600,
            metrics=mock_metrics,
        )
        cache.get("m", "nonexistent")

        mock_metrics.record_miss.assert_called_once()


class TestCacheSize:
    """Verify cache size tracking."""

    def test_size_increases_on_put(self, cache: EmbeddingCache) -> None:
        assert cache.size == 0
        cache.put("m", "text1", SAMPLE_EMBEDDING)
        assert cache.size == 1

    def test_size_does_not_exceed_max(
        self,
        small_cache: EmbeddingCache,
    ) -> None:
        for i in range(10):
            small_cache.put("m", f"text{i}", [float(i)])
        assert small_cache.size <= 3
