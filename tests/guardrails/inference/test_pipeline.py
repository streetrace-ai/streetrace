"""Tests for the inference pipeline facade."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.dsl.runtime.errors import MissingDependencyError
from streetrace.guardrails.inference.embedding_cache import EmbeddingCache
from streetrace.guardrails.inference.model_registry import (
    ModelRegistry,
    ModelState,
)
from streetrace.guardrails.inference.pipeline import InferencePipeline
from streetrace.guardrails.inference.session_pool import SessionPool
from streetrace.guardrails.inference.tokenizer_manager import (
    TokenizerManager,
)


@pytest.fixture
def mock_registry() -> MagicMock:
    """Create a mock model registry."""
    registry = MagicMock(spec=ModelRegistry)
    registry.get_state = MagicMock(return_value=ModelState.READY)
    mock_session = MagicMock()
    mock_session.run = MagicMock(
        return_value=[[[0.1, 0.2, 0.3, 0.4, 0.5]]],
    )
    registry.get_session = AsyncMock(return_value=mock_session)
    return registry


@pytest.fixture
def mock_pool() -> MagicMock:
    """Create a mock session pool."""
    pool = MagicMock(spec=SessionPool)
    mock_session = MagicMock()
    mock_session.run = MagicMock(
        return_value=[[[0.1, 0.2, 0.3, 0.4, 0.5]]],
    )
    pool.acquire = AsyncMock(return_value=mock_session)
    pool.release = MagicMock()
    pool.has_model = MagicMock(return_value=True)
    return pool


@pytest.fixture
def mock_cache() -> MagicMock:
    """Create a mock embedding cache."""
    cache = MagicMock(spec=EmbeddingCache)
    cache.get = MagicMock(return_value=None)
    cache.put = MagicMock()
    return cache


@pytest.fixture
def mock_tokenizer_mgr() -> MagicMock:
    """Create a mock tokenizer manager."""
    mgr = MagicMock(spec=TokenizerManager)
    encoding = MagicMock()
    encoding.input_ids = [101, 2023, 102]
    encoding.attention_mask = [1, 1, 1]
    mgr.tokenize = MagicMock(return_value=encoding)
    mgr.has_tokenizer = MagicMock(return_value=True)
    return mgr


@pytest.fixture
def pipeline(
    mock_registry: MagicMock,
    mock_pool: MagicMock,
    mock_cache: MagicMock,
    mock_tokenizer_mgr: MagicMock,
) -> InferencePipeline:
    """Create pipeline with all mock dependencies."""
    return InferencePipeline(
        registry=mock_registry,
        pool=mock_pool,
        cache=mock_cache,
        tokenizer_manager=mock_tokenizer_mgr,
    )


class TestGetEmbedding:
    """Verify embedding generation with cache integration."""

    @pytest.mark.asyncio
    async def test_cache_miss_runs_inference(
        self,
        pipeline: InferencePipeline,
        mock_cache: MagicMock,
    ) -> None:
        result = await pipeline.get_embedding("model-a", "hello world")
        assert isinstance(result, list)
        assert len(result) > 0
        mock_cache.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_skips_inference(
        self,
        pipeline: InferencePipeline,
        mock_cache: MagicMock,
        mock_pool: MagicMock,
    ) -> None:
        mock_cache.get.return_value = [0.5, 0.6, 0.7]
        result = await pipeline.get_embedding("model-a", "hello world")
        assert result == [0.5, 0.6, 0.7]
        mock_pool.acquire.assert_not_awaited()


class TestClassify:
    """Verify classification via pipeline."""

    @pytest.mark.asyncio
    async def test_classify_returns_probabilities(
        self,
        pipeline: InferencePipeline,
        mock_pool: MagicMock,
    ) -> None:
        mock_session = MagicMock()
        mock_session.run = MagicMock(
            return_value=[[[0.1, 0.9]]],
        )
        mock_session.get_outputs = MagicMock(
            return_value=[MagicMock(name="output")],
        )
        mock_pool.acquire = AsyncMock(return_value=mock_session)

        result = await pipeline.classify(
            "model-a",
            "test text",
            labels=["safe", "unsafe"],
        )
        assert isinstance(result, dict)


class TestFailFast:
    """Verify fail-fast behavior when models are unavailable."""

    @pytest.mark.asyncio
    async def test_get_embedding_failed_model_raises(
        self,
        pipeline: InferencePipeline,
        mock_registry: MagicMock,
    ) -> None:
        mock_registry.get_state.return_value = ModelState.FAILED
        mock_registry.get_session = AsyncMock(
            side_effect=MissingDependencyError(
                package="onnxruntime",
                install_command="pip install onnxruntime",
            ),
        )
        with pytest.raises(MissingDependencyError):
            await pipeline.get_embedding("failed-model", "text")


class TestIsModelReady:
    """Verify model readiness check."""

    def test_ready_model(
        self,
        pipeline: InferencePipeline,
        mock_registry: MagicMock,
    ) -> None:
        mock_registry.get_state.return_value = ModelState.READY
        assert pipeline.is_model_ready("model-a") is True

    def test_unloaded_model(
        self,
        pipeline: InferencePipeline,
        mock_registry: MagicMock,
    ) -> None:
        mock_registry.get_state.return_value = ModelState.UNLOADED
        assert pipeline.is_model_ready("model-a") is False


class TestWarmUp:
    """Verify model warm-up."""

    @pytest.mark.asyncio
    async def test_warm_up_loads_models(
        self,
        pipeline: InferencePipeline,
        mock_registry: MagicMock,
    ) -> None:
        await pipeline.warm_up(["model-a", "model-b"])
        assert mock_registry.get_session.await_count == 2


class TestBatchEmbed:
    """Verify batch embedding generation."""

    @pytest.mark.asyncio
    async def test_batch_embed_returns_list(
        self,
        pipeline: InferencePipeline,
        mock_cache: MagicMock,
    ) -> None:
        mock_cache.get.return_value = None
        results = await pipeline.batch_embed(
            "model-a",
            ["text1", "text2"],
        )
        assert isinstance(results, list)
        assert len(results) == 2
