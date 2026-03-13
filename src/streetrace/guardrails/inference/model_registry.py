"""Model registry with state machine for ONNX model lifecycle.

Track available models, manage loading state transitions, and validate
model file integrity via SHA-256 checksums. Prevent duplicate loads
using shared futures.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from streetrace.dsl.runtime.errors import MissingDependencyError
from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

logger = get_logger(__name__)

ONNX_PACKAGE = "onnxruntime"
"""Package name for ONNX Runtime."""

ONNX_INSTALL_COMMAND = "pip install onnxruntime"
"""Install command for ONNX Runtime."""


class ModelState(StrEnum):
    """Loading state for a registered model."""

    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


@dataclass
class _ModelEntry:
    """Internal record for a registered model."""

    model_id: str
    path: Path
    checksum: str
    state: ModelState = ModelState.UNLOADED
    session: object | None = None
    load_future: asyncio.Future[object] | None = None
    load_callback: Callable[..., Awaitable[object]] | None = None
    failure_reason: str = ""


class ModelRegistry:
    """Manage ONNX model registration, loading, and state tracking.

    Each model follows a state machine: unloaded -> loading -> ready | failed.
    Concurrent requests for the same model share a single load future to
    prevent duplicate loading.
    """

    def __init__(self) -> None:
        """Initialize an empty model registry."""
        self._models: dict[str, _ModelEntry] = {}
        self._lock = asyncio.Lock()

    def register_model(
        self,
        model_id: str,
        *,
        path: Path,
        checksum: str,
        load_callback: Callable[..., Awaitable[object]] | None = None,
    ) -> None:
        """Register a model for later loading.

        Args:
            model_id: Unique identifier for the model.
            path: Filesystem path to the ONNX model file.
            checksum: Expected SHA-256 hex digest of the model file.
            load_callback: Optional async callback to create session.

        Raises:
            ValueError: If model_id is already registered.

        """
        if model_id in self._models:
            msg = f"Model '{model_id}' is already registered"
            raise ValueError(msg)

        self._models[model_id] = _ModelEntry(
            model_id=model_id,
            path=path,
            checksum=checksum,
            load_callback=load_callback,
        )
        logger.info("Registered model %s at %s", model_id, path)

    def get_state(self, model_id: str) -> ModelState:
        """Return the current loading state of a model.

        Args:
            model_id: Model identifier.

        Returns:
            Current ModelState, or UNLOADED if model is not registered.

        """
        entry = self._models.get(model_id)
        if entry is None:
            return ModelState.UNLOADED
        return entry.state

    async def get_session(self, model_id: str) -> object:
        """Get or load an ONNX inference session for the given model.

        If the model is not yet loaded, trigger loading. Concurrent callers
        share the same load future. Failed models raise immediately.

        Args:
            model_id: Model identifier.

        Returns:
            An ONNX InferenceSession (typed as object to avoid import).

        Raises:
            MissingDependencyError: If model is not registered, failed to
                load, or ONNX Runtime is not installed.

        """
        entry = self._models.get(model_id)
        if entry is None:
            raise MissingDependencyError(
                package=f"Model '{model_id}' not registered",
                install_command=ONNX_INSTALL_COMMAND,
            )

        if entry.state == ModelState.FAILED:
            raise MissingDependencyError(
                package=f"Model '{model_id}' failed: {entry.failure_reason}",
                install_command=ONNX_INSTALL_COMMAND,
            )

        if entry.state == ModelState.READY and entry.session is not None:
            return entry.session

        async with self._lock:
            # Re-check after acquiring lock
            if entry.state == ModelState.READY and entry.session is not None:
                return entry.session

            if entry.state == ModelState.FAILED:  # type: ignore[comparison-overlap]
                raise MissingDependencyError(
                    package=(
                        f"Model '{model_id}' failed: "
                        f"{entry.failure_reason}"
                    ),
                    install_command=ONNX_INSTALL_COMMAND,
                )

            if entry.load_future is not None:
                # Another coroutine is already loading, wait on it
                return await entry.load_future

            # Start loading
            loop = asyncio.get_running_loop()
            entry.load_future = loop.create_future()
            entry.state = ModelState.LOADING

        try:
            session = await self._load_model(entry)
        except MissingDependencyError:
            entry.state = ModelState.FAILED
            if not entry.load_future.done():
                entry.load_future.set_exception(
                    MissingDependencyError(
                        package=(
                            f"Model '{model_id}' failed: "
                            f"{entry.failure_reason}"
                        ),
                        install_command=ONNX_INSTALL_COMMAND,
                    ),
                )
            raise
        else:
            entry.session = session
            entry.state = ModelState.READY
            entry.load_future.set_result(session)
            logger.info("Model %s loaded successfully", model_id)
            return session

    async def _load_model(self, entry: _ModelEntry) -> object:
        """Load and validate a model file, returning a session.

        Args:
            entry: Model entry with path and checksum.

        Returns:
            An ONNX InferenceSession.

        Raises:
            MissingDependencyError: On file not found, checksum mismatch,
                or import errors.

        """
        if not entry.path.exists():
            entry.failure_reason = f"Model file not found: {entry.path}"
            raise MissingDependencyError(
                package=(
                    f"Model '{entry.model_id}' not found at "
                    f"{entry.path}"
                ),
                install_command=ONNX_INSTALL_COMMAND,
            )

        model_bytes = entry.path.read_bytes()
        actual_checksum = hashlib.sha256(model_bytes).hexdigest()

        if actual_checksum != entry.checksum:
            entry.failure_reason = (
                f"Checksum mismatch: expected {entry.checksum}, "
                f"got {actual_checksum}"
            )
            raise MissingDependencyError(
                package=(
                    f"Model '{entry.model_id}' checksum mismatch"
                ),
                install_command=ONNX_INSTALL_COMMAND,
            )

        if entry.load_callback is not None:
            return await entry.load_callback(entry.path, model_bytes)

        try:
            return _create_onnx_session(model_bytes)
        except ImportError:
            entry.failure_reason = "onnxruntime is not installed"
            raise MissingDependencyError(
                package=ONNX_PACKAGE,
                install_command=ONNX_INSTALL_COMMAND,
            ) from None


def _create_onnx_session(model_bytes: bytes) -> object:
    """Create an ONNX Runtime InferenceSession from model bytes.

    Args:
        model_bytes: Raw ONNX model file content.

    Returns:
        An onnxruntime.InferenceSession instance.

    Raises:
        ImportError: If onnxruntime is not installed.

    """
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.inter_op_num_threads = 2
    opts.intra_op_num_threads = 2
    opts.graph_optimization_level = (
        ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    )

    return ort.InferenceSession(
        model_bytes,
        sess_options=opts,
        providers=["CPUExecutionProvider"],
    )
