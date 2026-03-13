"""Semantic detector for embedding-based prompt injection detection.

Embed text via InferencePipeline (MiniLM model) and compute cosine
similarity against known injection pattern embeddings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.guardrails.inference.pipeline import InferencePipeline

logger = get_logger(__name__)

EMBEDDING_MODEL_ID = "minilm-l6-v2"
"""Model identifier for the MiniLM embedding model."""

DEFAULT_WARN_THRESHOLD = 0.60
"""Default cosine similarity score triggering a warning."""

DEFAULT_BLOCK_THRESHOLD = 0.85
"""Default cosine similarity score triggering a block."""


@dataclass(frozen=True)
class SemanticResult:
    """Result from semantic injection detection.

    Attributes:
        score: Maximum cosine similarity against reference embeddings.
        matched_pattern: Name of the closest reference pattern.

    """

    score: float
    matched_pattern: str


class SemanticDetector:
    """Detect prompt injection via embedding cosine similarity.

    Embed input text using the InferencePipeline and compare against
    a set of reference injection embeddings. Return the maximum
    similarity score and the matched reference pattern name.
    """

    def __init__(
        self,
        *,
        inference_pipeline: InferencePipeline,
        reference_embeddings: dict[str, list[float]],
        warn_threshold: float = DEFAULT_WARN_THRESHOLD,
        block_threshold: float = DEFAULT_BLOCK_THRESHOLD,
    ) -> None:
        """Initialize the semantic detector.

        Args:
            inference_pipeline: Pipeline for embedding generation.
            reference_embeddings: Map of pattern names to embedding vectors.
            warn_threshold: Similarity score triggering a warning.
            block_threshold: Similarity score triggering a block.

        """
        self._pipeline = inference_pipeline
        self._reference_embeddings = reference_embeddings
        self._warn_threshold = warn_threshold
        self._block_threshold = block_threshold

    async def detect(self, text: str) -> SemanticResult:
        """Detect prompt injection in the given text.

        Args:
            text: Input text to analyze.

        Returns:
            SemanticResult with the max similarity score and pattern name.

        """
        text_embedding = await self._pipeline.get_embedding(
            EMBEDDING_MODEL_ID, text,
        )

        max_score = 0.0
        max_pattern = ""

        for pattern_name, ref_embedding in self._reference_embeddings.items():
            score = _cosine_similarity(text_embedding, ref_embedding)
            if score > max_score:
                max_score = score
                max_pattern = pattern_name

        if max_score >= self._block_threshold:
            logger.warning(
                "Semantic detector: score=%.3f pattern=%s (block)",
                max_score,
                max_pattern,
            )
        elif max_score >= self._warn_threshold:
            logger.info(
                "Semantic detector: score=%.3f pattern=%s (warn)",
                max_score,
                max_pattern,
            )

        return SemanticResult(score=max_score, matched_pattern=max_pattern)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        vec_a: First vector.
        vec_b: Second vector.

    Returns:
        Cosine similarity in range [-1.0, 1.0].

    """
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)
