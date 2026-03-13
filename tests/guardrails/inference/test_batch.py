"""Tests for the batch inference queue."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from streetrace.guardrails.inference.batch import BatchInferenceQueue

DEFAULT_DEADLINE_MS = 2
"""Default batch deadline in milliseconds."""

MAX_BATCH_SIZE = 8
"""Default maximum batch size."""


@pytest.fixture
def mock_inference_fn() -> AsyncMock:
    """Create a mock inference function that returns embeddings."""
    fn = AsyncMock()
    fn.return_value = [[0.1, 0.2, 0.3]]
    return fn


@pytest.fixture
def queue(mock_inference_fn: AsyncMock) -> BatchInferenceQueue:
    """Create a batch queue with defaults."""
    return BatchInferenceQueue(
        inference_fn=mock_inference_fn,
        max_batch_size=MAX_BATCH_SIZE,
        deadline_ms=DEFAULT_DEADLINE_MS,
    )


class TestBatchGrouping:
    """Verify requests are grouped by model."""

    @pytest.mark.asyncio
    async def test_single_request_returns_result(
        self,
        queue: BatchInferenceQueue,
        mock_inference_fn: AsyncMock,
    ) -> None:
        mock_inference_fn.return_value = [[0.1, 0.2, 0.3]]
        result = await queue.submit("model-a", [101, 102, 103])
        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_multiple_requests_same_model_batched(
        self,
        mock_inference_fn: AsyncMock,
    ) -> None:
        mock_inference_fn.return_value = [
            [0.1, 0.2],
            [0.3, 0.4],
        ]
        q = BatchInferenceQueue(
            inference_fn=mock_inference_fn,
            max_batch_size=MAX_BATCH_SIZE,
            deadline_ms=50,
        )

        r1, r2 = await asyncio.gather(
            q.submit("model-a", [101]),
            q.submit("model-a", [201]),
        )
        assert r1 == [0.1, 0.2]
        assert r2 == [0.3, 0.4]


class TestDeadlineFlushing:
    """Verify batch is flushed at deadline."""

    @pytest.mark.asyncio
    async def test_flush_at_deadline(
        self,
        queue: BatchInferenceQueue,
        mock_inference_fn: AsyncMock,
    ) -> None:
        mock_inference_fn.return_value = [[1.0, 2.0]]
        result = await asyncio.wait_for(
            queue.submit("model-a", [101]),
            timeout=1.0,
        )
        assert result == [1.0, 2.0]


class TestMaxBatchSize:
    """Verify batch is flushed when max size reached."""

    @pytest.mark.asyncio
    async def test_flush_at_max_batch_size(
        self,
        mock_inference_fn: AsyncMock,
    ) -> None:
        small_batch = 2
        mock_inference_fn.return_value = [[1.0], [2.0]]

        q = BatchInferenceQueue(
            inference_fn=mock_inference_fn,
            max_batch_size=small_batch,
            deadline_ms=5000,
        )

        r1, r2 = await asyncio.gather(
            q.submit("model-a", [101]),
            q.submit("model-a", [201]),
        )
        assert r1 == [1.0]
        assert r2 == [2.0]
