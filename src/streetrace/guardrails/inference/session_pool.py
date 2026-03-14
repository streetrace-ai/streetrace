"""Thread-safe ONNX InferenceSession pool.

Manage a pool of ONNX Runtime sessions per model, distributing
inference requests and queuing when all sessions are in use.
"""

from __future__ import annotations

import asyncio

from streetrace.log import get_logger

logger = get_logger(__name__)


class SessionPool:
    """Manage ONNX InferenceSession instances per model.

    Each model gets a pool of sessions. Acquire borrows a session,
    release returns it. When all sessions are in use, acquire waits
    until one becomes available.
    """

    def __init__(self, *, pool_size: int = 2) -> None:
        """Initialize the session pool.

        Args:
            pool_size: Maximum number of sessions per model.

        """
        self._pool_size = pool_size
        self._queues: dict[str, asyncio.Queue[object]] = {}

    def add_session(self, model_id: str, session: object) -> None:
        """Add a session to the pool for a model.

        Args:
            model_id: Model identifier.
            session: ONNX InferenceSession instance.

        """
        if model_id not in self._queues:
            self._queues[model_id] = asyncio.Queue(
                maxsize=self._pool_size,
            )
        self._queues[model_id].put_nowait(session)
        logger.info(
            "Added session for %s (available: %d)",
            model_id,
            self._queues[model_id].qsize(),
        )

    async def acquire(self, model_id: str) -> object:
        """Acquire a session from the pool.

        Block if no sessions are available until one is released.

        Args:
            model_id: Model identifier.

        Returns:
            An ONNX InferenceSession instance.

        Raises:
            KeyError: If model_id has no sessions in the pool.

        """
        if model_id not in self._queues:
            msg = f"No sessions for model '{model_id}'"
            raise KeyError(msg)
        return await self._queues[model_id].get()

    def release(self, model_id: str, session: object) -> None:
        """Return a session to the pool.

        Args:
            model_id: Model identifier.
            session: The session to return.

        """
        if model_id in self._queues:
            self._queues[model_id].put_nowait(session)

    def has_model(self, model_id: str) -> bool:
        """Check whether the pool has sessions for a model.

        Args:
            model_id: Model identifier.

        Returns:
            True if sessions exist for the model.

        """
        return model_id in self._queues

    def available_count(self, model_id: str) -> int:
        """Return the number of available sessions for a model.

        Args:
            model_id: Model identifier.

        Returns:
            Number of sessions currently available.

        """
        queue = self._queues.get(model_id)
        if queue is None:
            return 0
        return queue.qsize()
