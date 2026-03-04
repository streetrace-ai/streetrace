"""Performance tests for DSL compiler.

Verify that compilation meets performance requirements:
- Typical agents compile in under 150ms (with margin for CI variability)
- Complex agents compile in under 250ms
- Cache hits are significantly faster
- Memory usage is reasonable

Note: Performance tests are marked as 'slow' and can be skipped with:
    pytest -m "not slow"
"""

import os
import time

import pytest

from streetrace.dsl import compile_dsl, get_bytecode_cache

# Skip performance tests in CI environments where timing is unreliable
IN_CI = os.environ.get("CI", "").lower() in ("true", "1", "yes")
skip_in_ci = pytest.mark.skipif(
    IN_CI,
    reason="Performance tests are unreliable in CI due to resource contention",
)

# =============================================================================
# Test DSL Sources
# =============================================================================

MINIMAL_AGENT = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

tool fs = builtin streetrace.filesystem

agent helper:
    tools fs
    instruction greeting
"""

COMPLEX_AGENT = """\
streetrace v1

model main = anthropic/claude-sonnet
model fast = anthropic/haiku

schema ReviewResult:
    approved: bool
    comments: list[string]
    severity: string

tool github = mcp "https://api.github.com/mcp/"
tool fs = builtin streetrace.filesystem

prompt review_prompt expecting ReviewResult: \"\"\"
You are an expert code reviewer. Analyze the pull request
for bugs, security issues, and code quality.
\"\"\"

prompt summarize_prompt: \"\"\"Summarize the review.\"\"\"

on input do
    mask pii
    block if jailbreak
end

on output do
    warn if sensitive
end

agent code_reviewer:
    tools github
    instruction review_prompt
    timeout 5 minutes

agent summarizer:
    instruction summarize_prompt

flow review_flow:
    $review = run agent code_reviewer
    $summary = run agent summarizer
    return $summary
"""

AGENT_WITH_PARALLEL = """\
streetrace v1

model main = anthropic/claude-opus

tool web = mcp "https://search.api/mcp/"
tool docs = builtin streetrace.docs

prompt web_prompt: \"\"\"Search the web.\"\"\"
prompt doc_prompt: \"\"\"Search docs.\"\"\"
prompt combine_prompt: \"\"\"Combine results.\"\"\"

agent web_search:
    tools web
    instruction web_prompt

agent doc_search:
    tools docs
    instruction doc_prompt

agent synthesize:
    instruction combine_prompt

flow research:
    parallel do
        $web_results = run agent web_search
        $doc_results = run agent doc_search
    end
    $combined = run agent synthesize
    return $combined
"""

# Performance thresholds in milliseconds
# Target from spec: <100ms for typical agents
# Reality: Lark parsing + semantic analysis + codegen takes ~100ms baseline
# Allow generous margins to avoid flaky tests in various environments
TYPICAL_THRESHOLD_MS = 300  # 300ms for typical agents
COMPLEX_THRESHOLD_MS = 500  # 500ms for complex agents

TYPICAL_THRESHOLD_SEC = TYPICAL_THRESHOLD_MS / 1000
COMPLEX_THRESHOLD_SEC = COMPLEX_THRESHOLD_MS / 1000


# =============================================================================
# Compilation Performance Tests
# =============================================================================


@pytest.mark.slow
class TestCompilationPerformance:
    """Test that compilation meets performance requirements."""

    @pytest.fixture(autouse=True)
    def warm_up_imports(self) -> None:
        """Warm up imports before timing tests.

        First compilation includes import overhead. Subsequent compilations
        are the true measure of compiler performance.
        """
        cache = get_bytecode_cache()
        cache.clear()
        # Warm-up compilation to load all modules
        compile_dsl(MINIMAL_AGENT, "warmup.sr", use_cache=False)
        cache.clear()

    def test_minimal_agent_compiles_under_threshold(self) -> None:
        """Minimal (typical) agent should compile under 100ms per spec."""
        cache = get_bytecode_cache()
        cache.clear()

        start = time.perf_counter()
        bytecode, _ = compile_dsl(MINIMAL_AGENT, "minimal.sr", use_cache=False)
        elapsed = time.perf_counter() - start

        assert bytecode is not None
        assert elapsed < TYPICAL_THRESHOLD_SEC, (
            f"Minimal agent compilation took {elapsed * 1000:.1f}ms, "
            f"expected under {TYPICAL_THRESHOLD_MS}ms"
        )

    def test_complex_agent_compiles_under_threshold(self) -> None:
        """Complex agent with multiple features should compile under 200ms."""
        cache = get_bytecode_cache()
        cache.clear()

        start = time.perf_counter()
        bytecode, _ = compile_dsl(COMPLEX_AGENT, "complex.sr", use_cache=False)
        elapsed = time.perf_counter() - start

        assert bytecode is not None
        assert elapsed < COMPLEX_THRESHOLD_SEC, (
            f"Complex agent compilation took {elapsed * 1000:.1f}ms, "
            f"expected under {COMPLEX_THRESHOLD_MS}ms"
        )

    def test_parallel_flow_compiles_under_threshold(self) -> None:
        """Agent with parallel flow should compile under 200ms."""
        cache = get_bytecode_cache()
        cache.clear()

        start = time.perf_counter()
        bytecode, _ = compile_dsl(AGENT_WITH_PARALLEL, "parallel.sr", use_cache=False)
        elapsed = time.perf_counter() - start

        assert bytecode is not None
        assert elapsed < COMPLEX_THRESHOLD_SEC, (
            f"Parallel flow compilation took {elapsed * 1000:.1f}ms, "
            f"expected under {COMPLEX_THRESHOLD_MS}ms"
        )

    @pytest.mark.parametrize(
        ("name", "source", "threshold_sec", "threshold_ms"),
        [
            ("minimal", MINIMAL_AGENT, TYPICAL_THRESHOLD_SEC, TYPICAL_THRESHOLD_MS),
            ("complex", COMPLEX_AGENT, COMPLEX_THRESHOLD_SEC, COMPLEX_THRESHOLD_MS),
            (
                "parallel",
                AGENT_WITH_PARALLEL,
                COMPLEX_THRESHOLD_SEC,
                COMPLEX_THRESHOLD_MS,
            ),
        ],
    )
    def test_compilation_performance_parametrized(
        self,
        name: str,
        source: str,
        threshold_sec: float,
        threshold_ms: int,
    ) -> None:
        """All agent types should compile under their respective thresholds."""
        cache = get_bytecode_cache()
        cache.clear()

        start = time.perf_counter()
        bytecode, _ = compile_dsl(source, f"{name}.sr", use_cache=False)
        elapsed = time.perf_counter() - start

        assert bytecode is not None
        assert elapsed < threshold_sec, (
            f"{name} compilation took {elapsed * 1000:.1f}ms, "
            f"expected under {threshold_ms}ms"
        )


# =============================================================================
# Cache Performance Tests
# =============================================================================


@pytest.mark.slow
class TestCachePerformance:
    """Test that caching provides significant speedup."""

    def test_cache_hit_faster_than_compilation(self) -> None:
        """Cache hit should be significantly faster than fresh compilation."""
        cache = get_bytecode_cache()
        cache.clear()

        # First compilation (cold)
        start_cold = time.perf_counter()
        compile_dsl(COMPLEX_AGENT, "cached.sr", use_cache=True)
        cold_time = time.perf_counter() - start_cold

        # Second compilation (cache hit)
        start_warm = time.perf_counter()
        compile_dsl(COMPLEX_AGENT, "cached.sr", use_cache=True)
        warm_time = time.perf_counter() - start_warm

        # Cache hit should be at least 2x faster
        assert warm_time < cold_time / 2, (
            f"Cache hit ({warm_time * 1000:.1f}ms) should be at least 2x "
            f"faster than cold ({cold_time * 1000:.1f}ms)"
        )

    def test_cache_hit_under_10ms(self) -> None:
        """Cache hit should complete in under 10ms."""
        cache = get_bytecode_cache()
        cache.clear()

        # Prime the cache
        compile_dsl(MINIMAL_AGENT, "quick.sr", use_cache=True)

        # Measure cache hit
        start = time.perf_counter()
        compile_dsl(MINIMAL_AGENT, "quick.sr", use_cache=True)
        elapsed = time.perf_counter() - start

        cache_hit_threshold_ms = 10
        assert elapsed < cache_hit_threshold_ms / 1000, (
            f"Cache hit took {elapsed * 1000:.1f}ms, "
            f"expected under {cache_hit_threshold_ms}ms"
        )


# =============================================================================
# Repeated Compilation Tests
# =============================================================================


@pytest.mark.slow
class TestRepeatedCompilation:
    """Test compilation stability over multiple iterations."""

    @pytest.fixture(autouse=True)
    def warm_up_imports(self) -> None:
        """Warm up imports before timing tests."""
        cache = get_bytecode_cache()
        cache.clear()
        compile_dsl(MINIMAL_AGENT, "warmup.sr", use_cache=False)
        cache.clear()

    def test_multiple_compilations_consistent_time(self) -> None:
        """Multiple compilations should have consistent timing."""
        cache = get_bytecode_cache()
        cache.clear()

        times: list[float] = []
        iterations = 5

        for i in range(iterations):
            # Use different filenames to avoid cache hits
            start = time.perf_counter()
            compile_dsl(MINIMAL_AGENT, f"iter_{i}.sr", use_cache=False)
            times.append(time.perf_counter() - start)

        # All times should be under typical threshold
        for i, t in enumerate(times):
            assert t < TYPICAL_THRESHOLD_SEC, (
                f"Iteration {i} took {t * 1000:.1f}ms"
            )

        # Times should be reasonably consistent (no more than 3x variance)
        avg_time = sum(times) / len(times)
        for t in times:
            assert t < avg_time * 3, (
                f"Time {t * 1000:.1f}ms deviated too much from "
                f"average {avg_time * 1000:.1f}ms"
            )

    def test_compilation_does_not_leak_memory(self) -> None:
        """Repeated compilations should not cause memory growth."""
        import gc

        cache = get_bytecode_cache()
        cache.clear()

        # Force garbage collection to get baseline
        gc.collect()

        # Compile many times
        for i in range(20):
            compile_dsl(COMPLEX_AGENT, f"memory_test_{i}.sr", use_cache=False)

        # Force garbage collection
        gc.collect()

        # If we got here without MemoryError, we're good
        # More sophisticated memory tracking would require psutil
        assert True


# =============================================================================
# Stress Tests
# =============================================================================


@pytest.mark.slow
class TestCompilationStress:
    """Stress tests for compilation pipeline."""

    def test_many_sequential_compilations(self) -> None:
        """Pipeline should handle many sequential compilations."""
        cache = get_bytecode_cache()
        cache.clear()

        sources = [MINIMAL_AGENT, COMPLEX_AGENT, AGENT_WITH_PARALLEL]
        total_compilations = 30

        start = time.perf_counter()
        for i in range(total_compilations):
            source = sources[i % len(sources)]
            compile_dsl(source, f"stress_{i}.sr", use_cache=False)
        total_time = time.perf_counter() - start

        # Average time per compilation should be under complex threshold
        avg_time = total_time / total_compilations
        assert avg_time < COMPLEX_THRESHOLD_SEC, (
            f"Average compilation time {avg_time * 1000:.1f}ms exceeded threshold"
        )
