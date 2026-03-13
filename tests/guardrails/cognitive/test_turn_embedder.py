"""Tests for TurnEmbedder: embedding generation and caching."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.guardrails.cognitive.turn_embedder import TurnEmbedder

EMBEDDING_DIM = 4
SAMPLE_EMBEDDING = [0.1, 0.2, 0.3, 0.4]


@pytest.fixture
def mock_pipeline() -> MagicMock:
    """Create a mock InferencePipeline."""
    pipeline = MagicMock()
    pipeline.get_embedding = AsyncMock(return_value=SAMPLE_EMBEDDING)
    return pipeline


class TestEmbeddingGeneration:
    """Verify embedding generation via InferencePipeline."""

    @pytest.mark.asyncio
    async def test_generates_embedding_for_text(
        self, mock_pipeline: MagicMock,
    ) -> None:
        """Generate an embedding vector for given text."""
        embedder = TurnEmbedder(inference_pipeline=mock_pipeline)
        result = await embedder.embed("Hello world")

        assert result == SAMPLE_EMBEDDING
        mock_pipeline.get_embedding.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_list_of_floats(
        self, mock_pipeline: MagicMock,
    ) -> None:
        """Return type is list[float]."""
        embedder = TurnEmbedder(inference_pipeline=mock_pipeline)
        result = await embedder.embed("test text")

        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)


class TestEmbeddingCaching:
    """Verify that embeddings are cached per text hash."""

    @pytest.mark.asyncio
    async def test_caches_on_second_call(
        self, mock_pipeline: MagicMock,
    ) -> None:
        """Second call with same text returns cached result."""
        embedder = TurnEmbedder(inference_pipeline=mock_pipeline)
        result1 = await embedder.embed("same text")
        result2 = await embedder.embed("same text")

        assert result1 == result2
        assert mock_pipeline.get_embedding.await_count == 1

    @pytest.mark.asyncio
    async def test_different_text_not_cached(
        self, mock_pipeline: MagicMock,
    ) -> None:
        """Different text produces separate inference calls."""
        embedder = TurnEmbedder(inference_pipeline=mock_pipeline)
        await embedder.embed("text one")
        await embedder.embed("text two")

        assert mock_pipeline.get_embedding.await_count == 2


class TestWithoutInferencePipeline:
    """Verify behavior when no InferencePipeline is provided."""

    @pytest.mark.asyncio
    async def test_raises_without_pipeline(self) -> None:
        """Raise MissingDependencyError when pipeline is None."""
        from streetrace.dsl.runtime.errors import MissingDependencyError

        embedder = TurnEmbedder(inference_pipeline=None)
        with pytest.raises(MissingDependencyError):
            await embedder.embed("some text")
