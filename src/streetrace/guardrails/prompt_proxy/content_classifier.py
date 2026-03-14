"""Content safety classifier using DeBERTa via InferencePipeline.

Return per-category probabilities for content safety classification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.guardrails.inference.pipeline import InferencePipeline

logger = get_logger(__name__)

CLASSIFIER_MODEL_ID = "deberta-v3-xsmall"
"""Model identifier for the DeBERTa content classifier."""

CLASSIFICATION_LABELS: list[str] = ["safe", "injection", "harmful"]
"""Output category labels for content classification."""


class ContentClassifier:
    """Classify content safety using DeBERTa ONNX model.

    Return per-category probabilities via the InferencePipeline.
    Used for output screening and ambiguous input cases.
    """

    def __init__(
        self,
        *,
        inference_pipeline: InferencePipeline,
    ) -> None:
        """Initialize the content classifier.

        Args:
            inference_pipeline: Pipeline for classification inference.

        """
        self._pipeline = inference_pipeline

    async def classify(self, text: str) -> dict[str, float]:
        """Classify text into safety categories.

        Args:
            text: Input text to classify.

        Returns:
            Dict mapping category names to probabilities.

        """
        probabilities = await self._pipeline.classify(
            CLASSIFIER_MODEL_ID,
            text,
            labels=CLASSIFICATION_LABELS,
        )

        logger.debug(
            "Content classification: %s",
            probabilities,
        )

        return probabilities
