"""Unit tests for history compactor module.

Test the HistoryCompactor class and related functions.
"""

import pytest

from streetrace.dsl.runtime.history_compactor import (
    COMPACTION_THRESHOLD,
    DEFAULT_CONTEXT_WINDOW,
    MINIMUM_RECENT_MESSAGES,
    CompactionResult,
    HistoryCompactor,
    SummarizeStrategy,
    TruncateStrategy,
    _count_message_tokens,
    _get_context_window,
)


class TestTokenCounting:
    """Test token counting functionality."""

    def test_count_empty_messages(self):
        """Test counting tokens in empty message list."""
        result = _count_message_tokens([], "gpt-4")
        # LiteLLM adds base overhead even for empty messages
        assert result >= 0

    def test_count_single_message(self):
        """Test counting tokens in a single message."""
        messages = [{"role": "user", "content": "Hello"}]
        result = _count_message_tokens(messages, "gpt-4")
        # Should return a positive number
        assert result > 0

    def test_count_multiple_messages(self):
        """Test counting tokens in multiple messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there! How can I help you?"},
            {"role": "user", "content": "Tell me about Python."},
        ]
        result = _count_message_tokens(messages, "gpt-4")
        # Multiple messages should have more tokens than one
        single_result = _count_message_tokens([messages[0]], "gpt-4")
        assert result > single_result

    def test_count_tokens_fallback(self):
        """Test fallback token counting when litellm fails."""
        messages = [{"role": "user", "content": "a" * 100}]
        # Even with invalid model, should return a number
        result = _count_message_tokens(messages, "invalid-model-xyz")
        assert result > 0


class TestContextWindowLookup:
    """Test context window size lookup."""

    def test_explicit_max_input_tokens(self):
        """Test that explicit max_input_tokens takes priority."""
        result = _get_context_window("gpt-4", max_input_tokens=50000)
        assert result == 50000

    def test_default_fallback(self):
        """Test default context window for unknown model."""
        # Use a model name that won't be in litellm's model cost table
        result = _get_context_window("xyz-nonexistent-test-model-12345")
        assert result == DEFAULT_CONTEXT_WINDOW


class TestCompactionThreshold:
    """Test compaction threshold calculation."""

    def test_should_compact_below_threshold(self):
        """Test that small history does not trigger compaction."""
        compactor = HistoryCompactor(strategy="truncate")
        messages = [{"role": "user", "content": "Hello"}]
        result = compactor.should_compact(messages, "gpt-4")
        assert result is False

    def test_should_compact_above_threshold(self):
        """Test that large history triggers compaction."""
        compactor = HistoryCompactor(strategy="truncate")
        # Create content that exceeds 80% of the small threshold
        # With max_input_tokens=100 and threshold=80%, we need >80 tokens
        # A word is roughly 1 token, so 200 words should exceed it
        long_content = " ".join(["word"] * 200)
        messages = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": long_content},
        ]
        result = compactor.should_compact(
            messages,
            "gpt-4",
            max_input_tokens=100,  # Low threshold for testing
        )
        assert result is True


class TestTruncateStrategy:
    """Test the truncate compaction strategy."""

    @pytest.fixture
    def strategy(self):
        """Create a TruncateStrategy instance."""
        return TruncateStrategy()

    @pytest.mark.asyncio
    async def test_truncate_preserves_minimum_messages(self, strategy):
        """Test that truncation preserves minimum recent messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
        ]
        result = await strategy.compact(messages, target_tokens=1000, model="gpt-4")
        # Should preserve at least minimum messages
        assert len(result) <= len(messages)
        assert len(result) >= 1  # At least first message

    @pytest.mark.asyncio
    async def test_truncate_keeps_first_message(self, strategy):
        """Test that first message (system) is always kept."""
        messages = [
            {"role": "system", "content": "System instructions"},
            {"role": "user", "content": "User message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "User message 2"},
        ]
        result = await strategy.compact(messages, target_tokens=500, model="gpt-4")
        # First message should be preserved
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "System instructions"

    @pytest.mark.asyncio
    async def test_truncate_small_list(self, strategy):
        """Test that small message lists are not truncated."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = await strategy.compact(messages, target_tokens=10000, model="gpt-4")
        # Small list should be returned unchanged
        assert len(result) == len(messages)


class TestSummarizeStrategy:
    """Test the summarize compaction strategy."""

    @pytest.fixture
    def strategy_no_llm(self):
        """Create a SummarizeStrategy without LLM client."""
        return SummarizeStrategy(llm_client=None)

    @pytest.mark.asyncio
    async def test_summarize_falls_back_to_truncate(self, strategy_no_llm):
        """Test that summarize falls back to truncate without LLM."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
        ]
        result = await strategy_no_llm.compact(
            messages, target_tokens=500, model="gpt-4",
        )
        # Should still return valid messages
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_summarize_small_list(self, strategy_no_llm):
        """Test that small message lists are not summarized."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = await strategy_no_llm.compact(
            messages, target_tokens=10000, model="gpt-4",
        )
        # Small list should be returned unchanged
        assert len(result) == len(messages)


class TestHistoryCompactor:
    """Test the HistoryCompactor class."""

    def test_init_default_strategy(self):
        """Test default strategy is truncate."""
        compactor = HistoryCompactor()
        strategy = compactor._get_strategy()  # noqa: SLF001
        assert isinstance(strategy, TruncateStrategy)

    def test_init_summarize_strategy(self):
        """Test summarize strategy selection."""
        compactor = HistoryCompactor(strategy="summarize")
        strategy = compactor._get_strategy()  # noqa: SLF001
        assert isinstance(strategy, SummarizeStrategy)

    def test_count_tokens(self):
        """Test token counting method."""
        compactor = HistoryCompactor()
        messages = [{"role": "user", "content": "Hello world"}]
        result = compactor.count_tokens(messages, "gpt-4")
        assert result > 0

    @pytest.mark.asyncio
    async def test_compact_returns_result(self):
        """Test that compact returns a CompactionResult."""
        compactor = HistoryCompactor(strategy="truncate")
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = await compactor.compact(messages, "gpt-4")
        assert isinstance(result, CompactionResult)
        assert isinstance(result.compacted_messages, list)
        assert result.original_tokens > 0
        assert result.compacted_tokens >= 0
        assert result.messages_removed >= 0


class TestCompactionResult:
    """Test CompactionResult dataclass."""

    def test_result_creation(self):
        """Test creating a CompactionResult."""
        result = CompactionResult(
            compacted_messages=[{"role": "user", "content": "Hello"}],
            original_tokens=100,
            compacted_tokens=50,
            messages_removed=2,
        )
        assert len(result.compacted_messages) == 1
        assert result.original_tokens == 100
        assert result.compacted_tokens == 50
        assert result.messages_removed == 2


class TestConstants:
    """Test module constants."""

    def test_compaction_threshold(self):
        """Test compaction threshold is reasonable."""
        assert 0 < COMPACTION_THRESHOLD < 1
        assert COMPACTION_THRESHOLD == 0.80

    def test_default_context_window(self):
        """Test default context window size."""
        assert DEFAULT_CONTEXT_WINDOW > 0
        assert DEFAULT_CONTEXT_WINDOW == 128_000

    def test_minimum_recent_messages(self):
        """Test minimum recent messages constant."""
        assert MINIMUM_RECENT_MESSAGES > 0
        assert MINIMUM_RECENT_MESSAGES == 4
