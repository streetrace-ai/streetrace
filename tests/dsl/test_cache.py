"""Tests for DSL bytecode cache.

Test in-memory bytecode caching with content-based keying
and LRU eviction policy.
"""

from streetrace.dsl.cache import BytecodeCache
from streetrace.dsl.sourcemap.registry import SourceMapping


class TestBytecodeCache:
    """Test BytecodeCache class."""

    def _make_bytecode(self, name: str = "test") -> tuple:
        """Create a simple bytecode object for testing.

        Args:
            name: Name for the code object.

        Returns:
            Tuple of (bytecode, source_mappings).

        """
        # Use compile to create a real CodeType object
        code = compile(f"x = '{name}'", "<test>", "exec")
        mappings = [
            SourceMapping(
                generated_line=1,
                generated_column=0,
                source_file="test.sr",
                source_line=1,
                source_column=0,
            ),
        ]
        return code, mappings

    def test_create_cache(self) -> None:
        """Create a cache with default size."""
        cache = BytecodeCache()
        assert len(cache) == 0
        assert cache.max_size == 100

    def test_create_cache_custom_size(self) -> None:
        """Create a cache with custom size."""
        cache = BytecodeCache(max_size=10)
        assert cache.max_size == 10

    def test_cache_miss(self) -> None:
        """Cache miss returns None."""
        cache = BytecodeCache()
        result = cache.get("source code")
        assert result is None

    def test_cache_hit(self) -> None:
        """Cache hit returns stored bytecode."""
        cache = BytecodeCache()
        source = "model main = anthropic/claude-sonnet"
        bytecode, mappings = self._make_bytecode()

        cache.put(source, bytecode, mappings)
        result = cache.get(source)

        assert result is not None
        cached_bytecode, cached_mappings = result
        assert cached_bytecode is bytecode
        assert cached_mappings == mappings

    def test_content_based_keying(self) -> None:
        """Different content produces different cache keys."""
        cache = BytecodeCache()
        bytecode1, mappings1 = self._make_bytecode("first")
        bytecode2, mappings2 = self._make_bytecode("second")

        cache.put("source 1", bytecode1, mappings1)
        cache.put("source 2", bytecode2, mappings2)

        result1 = cache.get("source 1")
        result2 = cache.get("source 2")

        assert result1 is not None
        assert result2 is not None
        assert result1[0] is bytecode1
        assert result2[0] is bytecode2

    def test_same_content_same_key(self) -> None:
        """Same content produces same cache key."""
        cache = BytecodeCache()
        bytecode, mappings = self._make_bytecode()
        source = "model main = anthropic/claude-sonnet"

        cache.put(source, bytecode, mappings)

        # Get with exact same source
        result = cache.get(source)
        assert result is not None

    def test_cache_eviction(self) -> None:
        """Cache evicts oldest entry when full."""
        cache = BytecodeCache(max_size=3)

        # Fill cache
        for i in range(3):
            bytecode, mappings = self._make_bytecode(f"test{i}")
            cache.put(f"source {i}", bytecode, mappings)

        assert len(cache) == 3

        # Add one more - should evict oldest
        bytecode, mappings = self._make_bytecode("new")
        cache.put("new source", bytecode, mappings)

        assert len(cache) == 3
        # First entry should be evicted
        assert cache.get("source 0") is None
        # New entry should be present
        assert cache.get("new source") is not None

    def test_lru_eviction_order(self) -> None:
        """Cache evicts least recently used entry."""
        cache = BytecodeCache(max_size=3)

        # Fill cache
        for i in range(3):
            bytecode, mappings = self._make_bytecode(f"test{i}")
            cache.put(f"source {i}", bytecode, mappings)

        # Access source 0 to make it recently used
        cache.get("source 0")

        # Add new entry - should evict source 1 (least recently used)
        bytecode, mappings = self._make_bytecode("new")
        cache.put("new source", bytecode, mappings)

        # Source 0 should still be present (was accessed)
        assert cache.get("source 0") is not None
        # Source 1 should be evicted (least recently used)
        assert cache.get("source 1") is None
        # Source 2 should still be present
        assert cache.get("source 2") is not None

    def test_invalidate_existing(self) -> None:
        """Invalidate removes existing entry."""
        cache = BytecodeCache()
        source = "model main = anthropic/claude-sonnet"
        bytecode, mappings = self._make_bytecode()

        cache.put(source, bytecode, mappings)
        assert cache.get(source) is not None

        result = cache.invalidate(source)

        assert result is True
        assert cache.get(source) is None

    def test_invalidate_nonexistent(self) -> None:
        """Invalidate returns False for missing entry."""
        cache = BytecodeCache()
        result = cache.invalidate("nonexistent source")
        assert result is False

    def test_clear(self) -> None:
        """Clear removes all entries."""
        cache = BytecodeCache()

        for i in range(5):
            bytecode, mappings = self._make_bytecode(f"test{i}")
            cache.put(f"source {i}", bytecode, mappings)

        assert len(cache) == 5

        cache.clear()

        assert len(cache) == 0
        for i in range(5):
            assert cache.get(f"source {i}") is None

    def test_put_overwrites_existing(self) -> None:
        """Put overwrites existing entry with same key."""
        cache = BytecodeCache()
        source = "same source"

        bytecode1, mappings1 = self._make_bytecode("first")
        bytecode2, mappings2 = self._make_bytecode("second")

        cache.put(source, bytecode1, mappings1)
        cache.put(source, bytecode2, mappings2)

        result = cache.get(source)
        assert result is not None
        assert result[0] is bytecode2
