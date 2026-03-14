"""Tests for the ONNX session pool."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from streetrace.guardrails.inference.session_pool import SessionPool


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock ONNX InferenceSession."""
    session = MagicMock()
    session.run = MagicMock(return_value=[[[0.1, 0.2, 0.3]]])
    return session


@pytest.fixture
def pool_of_two(mock_session: MagicMock) -> SessionPool:
    """Create a session pool with 2 sessions."""
    pool = SessionPool(pool_size=2)
    pool.add_session("test-model", mock_session)
    pool.add_session("test-model", mock_session)
    return pool


class TestSessionPoolAcquireRelease:
    """Verify session acquire/release lifecycle."""

    @pytest.mark.asyncio
    async def test_acquire_returns_session(
        self,
        pool_of_two: SessionPool,
    ) -> None:
        session = await pool_of_two.acquire("test-model")
        assert session is not None

    @pytest.mark.asyncio
    async def test_release_returns_session_to_pool(
        self,
        pool_of_two: SessionPool,
    ) -> None:
        session = await pool_of_two.acquire("test-model")
        pool_of_two.release("test-model", session)
        # Should be able to acquire again
        session2 = await pool_of_two.acquire("test-model")
        assert session2 is not None

    @pytest.mark.asyncio
    async def test_pool_exhaustion_waits(
        self,
        mock_session: MagicMock,
    ) -> None:
        pool = SessionPool(pool_size=1)
        pool.add_session("test-model", mock_session)

        # Acquire the only session
        s1 = await pool.acquire("test-model")

        async def delayed_release() -> None:
            await asyncio.sleep(0.01)
            pool.release("test-model", s1)

        # Start release in background and wait for second acquire
        task = asyncio.create_task(delayed_release())
        s2 = await asyncio.wait_for(
            pool.acquire("test-model"),
            timeout=1.0,
        )
        assert s2 is s1
        await task

    @pytest.mark.asyncio
    async def test_acquire_unknown_model_raises(
        self,
        pool_of_two: SessionPool,
    ) -> None:
        with pytest.raises(KeyError, match="unknown"):
            await pool_of_two.acquire("unknown")


class TestSessionPoolManagement:
    """Verify pool management operations."""

    def test_has_model(self, pool_of_two: SessionPool) -> None:
        assert pool_of_two.has_model("test-model") is True
        assert pool_of_two.has_model("unknown") is False

    def test_available_count(self, pool_of_two: SessionPool) -> None:
        assert pool_of_two.available_count("test-model") == 2

    @pytest.mark.asyncio
    async def test_available_decreases_on_acquire(
        self,
        pool_of_two: SessionPool,
    ) -> None:
        await pool_of_two.acquire("test-model")
        assert pool_of_two.available_count("test-model") == 1
