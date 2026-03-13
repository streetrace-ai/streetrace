"""Tests for the model registry state machine and checksum validation."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streetrace.dsl.runtime.errors import MissingDependencyError
from streetrace.guardrails.inference.model_registry import (
    ModelRegistry,
    ModelState,
)


@pytest.fixture
def registry() -> ModelRegistry:
    """Create a fresh model registry."""
    return ModelRegistry()


@pytest.fixture
def model_bytes() -> bytes:
    """Create dummy model bytes."""
    return b"fake-onnx-model-data"


@pytest.fixture
def model_checksum(model_bytes: bytes) -> str:
    """Compute SHA-256 checksum of model bytes."""
    return hashlib.sha256(model_bytes).hexdigest()


@pytest.fixture
def tmp_model_file(tmp_path: Path, model_bytes: bytes) -> Path:
    """Create a temporary model file."""
    model_file = tmp_path / "test-model.onnx"
    model_file.write_bytes(model_bytes)
    return model_file


class TestModelState:
    """Verify model state enum values."""

    def test_all_states(self) -> None:
        assert ModelState.UNLOADED == "unloaded"
        assert ModelState.LOADING == "loading"
        assert ModelState.READY == "ready"
        assert ModelState.FAILED == "failed"


class TestModelRegistration:
    """Verify model registration and state tracking."""

    def test_register_model(
        self,
        registry: ModelRegistry,
        tmp_model_file: Path,
        model_checksum: str,
    ) -> None:
        registry.register_model(
            "test-model",
            path=tmp_model_file,
            checksum=model_checksum,
        )
        assert registry.get_state("test-model") == ModelState.UNLOADED

    def test_register_duplicate_model_raises(
        self,
        registry: ModelRegistry,
        tmp_model_file: Path,
        model_checksum: str,
    ) -> None:
        registry.register_model(
            "test-model",
            path=tmp_model_file,
            checksum=model_checksum,
        )
        msg = "Model 'test-model' is already registered"
        with pytest.raises(ValueError, match=msg):
            registry.register_model(
                "test-model",
                path=tmp_model_file,
                checksum=model_checksum,
            )

    def test_get_state_unknown_model(
        self,
        registry: ModelRegistry,
    ) -> None:
        assert registry.get_state("nonexistent") == ModelState.UNLOADED


class TestModelLoading:
    """Verify model loading state machine transitions."""

    @pytest.mark.asyncio
    async def test_get_session_transitions_to_ready(
        self,
        registry: ModelRegistry,
        tmp_model_file: Path,
        model_checksum: str,
    ) -> None:
        registry.register_model(
            "test-model",
            path=tmp_model_file,
            checksum=model_checksum,
        )
        mock_session = MagicMock()
        with patch(
            "streetrace.guardrails.inference.model_registry"
            "._create_onnx_session",
            return_value=mock_session,
        ):
            session = await registry.get_session("test-model")

        assert session is mock_session
        assert registry.get_state("test-model") == ModelState.READY

    @pytest.mark.asyncio
    async def test_duplicate_get_session_shares_future(
        self,
        registry: ModelRegistry,
        tmp_model_file: Path,
        model_checksum: str,
    ) -> None:
        registry.register_model(
            "test-model",
            path=tmp_model_file,
            checksum=model_checksum,
        )
        mock_session = MagicMock()
        call_count = 0

        def counting_create(*_args: object, **_kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            return mock_session

        with patch(
            "streetrace.guardrails.inference.model_registry"
            "._create_onnx_session",
            side_effect=counting_create,
        ):
            s1, s2 = await asyncio.gather(
                registry.get_session("test-model"),
                registry.get_session("test-model"),
            )

        assert s1 is mock_session
        assert s2 is mock_session
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_checksum_mismatch_transitions_to_failed(
        self,
        registry: ModelRegistry,
        tmp_model_file: Path,
    ) -> None:
        registry.register_model(
            "test-model",
            path=tmp_model_file,
            checksum="wrong-checksum",
        )
        with pytest.raises(MissingDependencyError):
            await registry.get_session("test-model")

        assert registry.get_state("test-model") == ModelState.FAILED

    @pytest.mark.asyncio
    async def test_missing_file_transitions_to_failed(
        self,
        registry: ModelRegistry,
    ) -> None:
        registry.register_model(
            "test-model",
            path=Path("/nonexistent/model.onnx"),
            checksum="abc123",
        )
        with pytest.raises(MissingDependencyError, match="not found"):
            await registry.get_session("test-model")

        assert registry.get_state("test-model") == ModelState.FAILED

    @pytest.mark.asyncio
    async def test_failed_model_raises_on_subsequent_get(
        self,
        registry: ModelRegistry,
    ) -> None:
        registry.register_model(
            "test-model",
            path=Path("/nonexistent/model.onnx"),
            checksum="abc",
        )
        with pytest.raises(MissingDependencyError):
            await registry.get_session("test-model")

        # Second call should also raise, not retry
        with pytest.raises(MissingDependencyError):
            await registry.get_session("test-model")

    @pytest.mark.asyncio
    async def test_unregistered_model_raises(
        self,
        registry: ModelRegistry,
    ) -> None:
        with pytest.raises(MissingDependencyError, match="not registered"):
            await registry.get_session("unknown-model")

    @pytest.mark.asyncio
    async def test_onnx_import_error_raises_missing_dependency(
        self,
        registry: ModelRegistry,
        tmp_model_file: Path,
        model_checksum: str,
    ) -> None:
        registry.register_model(
            "test-model",
            path=tmp_model_file,
            checksum=model_checksum,
        )
        with (
            patch(
                "streetrace.guardrails.inference.model_registry"
                "._create_onnx_session",
                side_effect=ImportError("No module named 'onnxruntime'"),
            ),
            pytest.raises(MissingDependencyError, match="onnxruntime"),
        ):
            await registry.get_session("test-model")

        assert registry.get_state("test-model") == ModelState.FAILED


class TestModelRegistryLoadCallback:
    """Verify model load callback for session pool integration."""

    @pytest.mark.asyncio
    async def test_load_callback_invoked(
        self,
        registry: ModelRegistry,
        tmp_model_file: Path,
        model_checksum: str,
    ) -> None:
        callback = AsyncMock(return_value=MagicMock())
        registry.register_model(
            "test-model",
            path=tmp_model_file,
            checksum=model_checksum,
            load_callback=callback,
        )
        await registry.get_session("test-model")

        callback.assert_awaited_once()
