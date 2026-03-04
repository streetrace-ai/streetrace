"""Bytecode cache for Streetrace DSL compiler.

Provide in-memory caching of compiled DSL bytecode with content-based
keying and LRU eviction policy.
"""

import hashlib
from collections import OrderedDict
from types import CodeType

from streetrace.dsl.sourcemap.registry import SourceMapping
from streetrace.log import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_SIZE = 100
"""Default maximum number of cached entries."""


class BytecodeCache:
    """In-memory cache for compiled DSL bytecode.

    Cache compiled bytecode using content-based hashing for automatic
    invalidation when source changes. Uses LRU eviction when the cache
    exceeds its maximum size.
    """

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE) -> None:
        """Initialize the bytecode cache.

        Args:
            max_size: Maximum number of entries to cache.

        """
        self._cache: OrderedDict[str, tuple[CodeType, list[SourceMapping]]] = (
            OrderedDict()
        )
        self._max_size = max_size
        logger.debug("Created BytecodeCache with max_size=%d", max_size)

    def _compute_key(self, source: str) -> str:
        """Compute cache key from source content.

        Args:
            source: The DSL source code.

        Returns:
            SHA-256 hash of the source content.

        """
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def get(self, source: str) -> tuple[CodeType, list[SourceMapping]] | None:
        """Get cached bytecode if available.

        Args:
            source: The DSL source code.

        Returns:
            Tuple of (bytecode, source_mappings) if cached, None otherwise.

        """
        key = self._compute_key(source)
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            logger.debug("Cache hit for key %s...", key[:12])
            return self._cache[key]

        logger.debug("Cache miss for key %s...", key[:12])
        return None

    def put(
        self,
        source: str,
        bytecode: CodeType,
        source_mappings: list[SourceMapping],
    ) -> None:
        """Cache compiled bytecode.

        Args:
            source: The DSL source code.
            bytecode: The compiled Python bytecode.
            source_mappings: Source mappings for error translation.

        """
        key = self._compute_key(source)

        # Evict oldest entries if at capacity
        while len(self._cache) >= self._max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug("Evicted cache entry %s...", evicted_key[:12])

        self._cache[key] = (bytecode, source_mappings)
        logger.debug("Cached bytecode for key %s...", key[:12])

    def invalidate(self, source: str) -> bool:
        """Invalidate a specific cache entry.

        Args:
            source: The DSL source code to invalidate.

        Returns:
            True if entry was found and removed, False otherwise.

        """
        key = self._compute_key(source)
        if key in self._cache:
            del self._cache[key]
            logger.debug("Invalidated cache entry %s...", key[:12])
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.debug("Cleared %d cache entries", count)

    def __len__(self) -> int:
        """Get the number of cached entries.

        Returns:
            Number of entries currently cached.

        """
        return len(self._cache)

    @property
    def max_size(self) -> int:
        """Get the maximum cache size.

        Returns:
            Maximum number of entries allowed.

        """
        return self._max_size
