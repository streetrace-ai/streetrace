"""Neural inspector for MCP tool description analysis.

Embed tool descriptions via E5-small ONNX, compute cosine
similarity against known-good patterns, and detect JSON-RPC
structural anomalies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.guardrails.inference.pipeline import InferencePipeline

logger = get_logger(__name__)

E5_MODEL_ID = "e5-small"
"""Model identifier for E5-small embedding model."""

ANOMALY_SCORE_FLOOR = 0.0
"""Minimum anomaly score."""

ANOMALY_SCORE_CEILING = 1.0
"""Maximum anomaly score."""

_SUSPICIOUS_KEYS: frozenset[str] = frozenset({
    "__proto__",
    "__import__",
    "__class__",
    "__builtins__",
    "__globals__",
    "constructor",
    "prototype",
    "__subclasses__",
})
"""JSON keys that indicate prototype pollution or code injection."""

_KNOWN_GOOD_DESCRIPTIONS: list[str] = [
    "Read a file from the filesystem",
    "Write content to a file",
    "List files in a directory",
    "Search for text in files",
    "Execute a shell command safely",
    "Query a database table",
    "Send an HTTP request",
    "Get the current time",
]
"""Reference descriptions for known-good tool patterns."""


@dataclass(frozen=True)
class InspectorResult:
    """Result of neural inspection.

    Attributes:
        anomaly_score: Score from 0.0 (normal) to 1.0 (anomalous).
        anomalies: List of detected anomaly descriptions.

    """

    anomaly_score: float
    anomalies: list[str] = field(default_factory=list)


class NeuralInspector:
    """Analyze tool descriptions and args for anomalies.

    Combine E5-small embedding similarity against known-good
    patterns with structural analysis of JSON-RPC payloads.
    """

    def __init__(
        self,
        *,
        inference_pipeline: InferencePipeline,
    ) -> None:
        """Initialize the neural inspector.

        Args:
            inference_pipeline: ONNX inference pipeline for embeddings.

        """
        self._pipeline = inference_pipeline

    async def inspect(
        self,
        *,
        tool_name: str,
        tool_description: str,
        args: dict[str, object],
    ) -> InspectorResult:
        """Inspect a tool call for anomalies.

        Run structural analysis and embedding-based similarity
        checking against known-good tool patterns.

        Args:
            tool_name: Name of the tool being called.
            tool_description: Tool's advertised description.
            args: Tool call arguments.

        Returns:
            InspectorResult with anomaly score and descriptions.

        """
        anomalies: list[str] = []

        # Stage 1: Structural anomaly detection
        structural_anomalies = _detect_structural_anomalies(args)
        anomalies.extend(structural_anomalies)

        # Stage 2: Embedding similarity (if pipeline available)
        embedding_score = await self._compute_embedding_anomaly(
            tool_name, tool_description,
        )

        # Combine scores: structural issues raise the floor
        structural_penalty = min(
            len(structural_anomalies) * 0.2,
            ANOMALY_SCORE_CEILING,
        )
        combined_score = max(embedding_score, structural_penalty)
        clamped_score = min(combined_score, ANOMALY_SCORE_CEILING)

        return InspectorResult(
            anomaly_score=clamped_score,
            anomalies=anomalies,
        )

    async def _compute_embedding_anomaly(
        self,
        tool_name: str,
        tool_description: str,
    ) -> float:
        """Compute anomaly score based on embedding similarity.

        Embed the tool description and compare against known-good
        reference patterns. Higher distance = higher anomaly.

        Args:
            tool_name: Tool name for context.
            tool_description: Tool description to embed.

        Returns:
            Anomaly score from 0.0 to 1.0.

        """
        text = f"{tool_name}: {tool_description}"
        try:
            embedding = await self._pipeline.get_embedding(
                E5_MODEL_ID, text,
            )
        except (ValueError, RuntimeError):
            logger.warning(
                "Embedding failed for tool %s, using structural only",
                tool_name,
            )
            return ANOMALY_SCORE_FLOOR

        # Compare against known-good patterns
        max_similarity = ANOMALY_SCORE_FLOOR
        for ref_desc in _KNOWN_GOOD_DESCRIPTIONS:
            try:
                ref_embedding = await self._pipeline.get_embedding(
                    E5_MODEL_ID, ref_desc,
                )
                sim = _cosine_similarity(embedding, ref_embedding)
                max_similarity = max(max_similarity, sim)
            except (ValueError, RuntimeError):
                continue

        # Convert similarity to anomaly: high similarity = low anomaly
        return max(
            ANOMALY_SCORE_FLOOR,
            ANOMALY_SCORE_CEILING - max_similarity,
        )


def _detect_structural_anomalies(
    args: dict[str, object],
) -> list[str]:
    """Detect structural anomalies in tool arguments.

    Check for prototype pollution keys, nested executable
    content, and other suspicious patterns.

    Args:
        args: Tool call arguments to inspect.

    Returns:
        List of anomaly descriptions.

    """
    anomalies: list[str] = []
    _scan_dict_keys(args, anomalies, depth=0)
    return anomalies


MAX_SCAN_DEPTH = 10
"""Maximum recursion depth for structural scanning."""


def _scan_dict_keys(
    data: dict[str, object],
    anomalies: list[str],
    *,
    depth: int,
) -> None:
    """Recursively scan dictionary keys for suspicious patterns.

    Args:
        data: Dictionary to scan.
        anomalies: Accumulator for found anomalies.
        depth: Current recursion depth.

    """
    if depth > MAX_SCAN_DEPTH:
        return

    for key, value in data.items():
        if key in _SUSPICIOUS_KEYS:
            anomalies.append(
                f"Suspicious key '{key}' in tool arguments",
            )
        if isinstance(value, dict):
            _scan_dict_keys(
                value, anomalies, depth=depth + 1,
            )


def _cosine_similarity(
    vec_a: list[float],
    vec_b: list[float],
) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        vec_a: First vector.
        vec_b: Second vector.

    Returns:
        Cosine similarity from -1.0 to 1.0.

    """
    if len(vec_a) != len(vec_b) or len(vec_a) == 0:
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)
