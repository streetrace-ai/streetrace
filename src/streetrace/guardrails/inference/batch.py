"""Batch inference queue for grouping requests by model.

Group pending inference requests and flush them as a batch either
when the batch is full or when a deadline expires, whichever comes
first.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)

DEFAULT_MAX_BATCH_SIZE = 8
"""Default maximum number of requests per batch."""

DEFAULT_DEADLINE_MS = 2
"""Default deadline in milliseconds before flushing a partial batch."""


@dataclass
class _PendingRequest:
    """A pending inference request awaiting batching."""

    model_id: str
    input_ids: list[int]
    future: asyncio.Future[list[float]] = field(
        default_factory=lambda: asyncio.get_event_loop().create_future(),
    )


class BatchInferenceQueue:
    """Group inference requests by model and flush as batches.

    Submit individual requests that are batched together. A batch is
    flushed when it reaches max_batch_size or when the deadline
    expires, whichever comes first.
    """

    def __init__(
        self,
        *,
        inference_fn: Callable[
            [str, list[list[int]]],
            Awaitable[list[list[float]]],
        ],
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
        deadline_ms: float = DEFAULT_DEADLINE_MS,
    ) -> None:
        """Initialize the batch inference queue.

        Args:
            inference_fn: Async function that runs batched inference.
                Takes (model_id, list_of_input_ids) and returns
                list_of_embeddings.
            max_batch_size: Maximum requests per batch.
            deadline_ms: Maximum wait time before flushing in ms.

        """
        self._inference_fn = inference_fn
        self._max_batch_size = max_batch_size
        self._deadline_seconds = deadline_ms / 1000.0
        self._pending: dict[str, list[_PendingRequest]] = defaultdict(list)
        self._timers: dict[str, asyncio.Task[None]] = {}
        self._flush_tasks: set[asyncio.Task[None]] = set()
        self._lock = asyncio.Lock()

    async def submit(
        self,
        model_id: str,
        input_ids: list[int],
    ) -> list[float]:
        """Submit a single inference request to be batched.

        Args:
            model_id: Model identifier.
            input_ids: Tokenized input IDs.

        Returns:
            The embedding vector for this request.

        """
        loop = asyncio.get_running_loop()
        request = _PendingRequest(
            model_id=model_id,
            input_ids=input_ids,
            future=loop.create_future(),
        )

        async with self._lock:
            self._pending[model_id].append(request)
            pending_count = len(self._pending[model_id])

            if pending_count >= self._max_batch_size:
                batch = self._pending.pop(model_id)
                self._cancel_timer(model_id)
                task = asyncio.create_task(
                    self._flush_batch(model_id, batch),
                )
                self._flush_tasks.add(task)
                task.add_done_callback(self._flush_tasks.discard)
            elif model_id not in self._timers:
                self._timers[model_id] = asyncio.create_task(
                    self._deadline_flush(model_id),
                )

        return await request.future

    async def _deadline_flush(self, model_id: str) -> None:
        """Wait for deadline then flush pending requests.

        Args:
            model_id: Model identifier to flush.

        """
        await asyncio.sleep(self._deadline_seconds)

        async with self._lock:
            batch = self._pending.pop(model_id, [])
            self._timers.pop(model_id, None)

        if batch:
            await self._flush_batch(model_id, batch)

    async def _flush_batch(
        self,
        model_id: str,
        batch: list[_PendingRequest],
    ) -> None:
        """Execute inference for a batch of requests.

        Args:
            model_id: Model identifier.
            batch: List of pending requests to process.

        """
        inputs = [req.input_ids for req in batch]
        logger.debug(
            "Flushing batch of %d for %s",
            len(batch),
            model_id,
        )

        try:
            results = await self._inference_fn(model_id, inputs)
            for request, result in zip(batch, results, strict=True):
                if not request.future.done():
                    request.future.set_result(result)
        except (ValueError, RuntimeError, ImportError) as exc:
            for request in batch:
                if not request.future.done():
                    request.future.set_exception(exc)

    def _cancel_timer(self, model_id: str) -> None:
        """Cancel the deadline timer for a model.

        Args:
            model_id: Model identifier.

        """
        timer = self._timers.pop(model_id, None)
        if timer is not None and not timer.done():
            timer.cancel()
