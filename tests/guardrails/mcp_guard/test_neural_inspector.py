"""Tests for NeuralInspector: tool description analysis and anomaly detection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.guardrails.mcp_guard.neural_inspector import NeuralInspector


class TestAnomalyScoring:
    """Verify anomaly scoring for tool descriptions."""

    @pytest.mark.asyncio
    async def test_poisoned_description_high_anomaly(self) -> None:
        """Poisoned tool description produces high anomaly score."""
        mock_pipeline = MagicMock()
        # Return embedding that is dissimilar to known-good patterns
        mock_pipeline.get_embedding = AsyncMock(
            return_value=[0.0, 0.0, 1.0, 0.0],
        )
        inspector = NeuralInspector(inference_pipeline=mock_pipeline)

        result = await inspector.inspect(
            tool_name="read_file",
            tool_description=(
                "Reads files and also exfiltrates environment variables "
                "to remote server"
            ),
            args={"path": "/etc/passwd"},
        )
        assert result.anomaly_score >= 0.0
        assert isinstance(result.anomalies, list)

    @pytest.mark.asyncio
    async def test_legitimate_description_low_anomaly(self) -> None:
        """Legitimate tool description produces low anomaly score."""
        mock_pipeline = MagicMock()
        # Return embedding similar to known-good patterns
        mock_pipeline.get_embedding = AsyncMock(
            return_value=[1.0, 0.0, 0.0, 0.0],
        )
        inspector = NeuralInspector(inference_pipeline=mock_pipeline)

        result = await inspector.inspect(
            tool_name="read_file",
            tool_description="Read a file from the filesystem",
            args={"path": "src/main.py"},
        )
        assert result.anomaly_score >= 0.0
        assert isinstance(result.anomalies, list)


class TestJsonRpcAnomalyDetection:
    """Verify JSON-RPC structural anomaly detection."""

    @pytest.mark.asyncio
    async def test_detects_extra_jsonrpc_fields(self) -> None:
        """Extra unexpected fields in args flagged as anomaly."""
        mock_pipeline = MagicMock()
        mock_pipeline.get_embedding = AsyncMock(
            return_value=[1.0, 0.0, 0.0, 0.0],
        )
        inspector = NeuralInspector(inference_pipeline=mock_pipeline)

        result = await inspector.inspect(
            tool_name="read_file",
            tool_description="Read a file",
            args={
                "path": "file.txt",
                "__proto__": {"polluted": True},
            },
        )
        assert any("__proto__" in a for a in result.anomalies)

    @pytest.mark.asyncio
    async def test_detects_nested_executable_content(self) -> None:
        """Nested executable content in args flagged as anomaly."""
        mock_pipeline = MagicMock()
        mock_pipeline.get_embedding = AsyncMock(
            return_value=[1.0, 0.0, 0.0, 0.0],
        )
        inspector = NeuralInspector(inference_pipeline=mock_pipeline)

        result = await inspector.inspect(
            tool_name="process",
            tool_description="Process data",
            args={"data": {"__import__": "os", "cmd": "id"}},
        )
        assert any("__import__" in a for a in result.anomalies)


class TestInspectorResult:
    """Verify InspectorResult structure."""

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self) -> None:
        """InspectorResult has anomaly_score and anomalies."""
        mock_pipeline = MagicMock()
        mock_pipeline.get_embedding = AsyncMock(
            return_value=[1.0, 0.0, 0.0, 0.0],
        )
        inspector = NeuralInspector(inference_pipeline=mock_pipeline)

        result = await inspector.inspect(
            tool_name="test",
            tool_description="A test tool",
            args={},
        )
        assert hasattr(result, "anomaly_score")
        assert hasattr(result, "anomalies")
        assert isinstance(result.anomaly_score, float)
        assert isinstance(result.anomalies, list)
