"""Cognitive Monitor implementing the Guardrail protocol.

Facade combining TurnEmbedder, IntentTracker, DriftDetector,
SequenceAnomalyDetector, and MttrCalculator for multi-turn
intent drift detection.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from opentelemetry import trace

from streetrace.guardrails.cognitive.drift_detector import (
    DriftDetector,
    DriftResult,
)
from streetrace.guardrails.cognitive.intent_tracker import IntentTracker
from streetrace.guardrails.cognitive.mttr_calculator import MttrCalculator
from streetrace.guardrails.cognitive.sequence_anomaly import (
    SequenceAnomalyDetector,
    SequencePattern,
)
from streetrace.guardrails.cognitive.turn_embedder import TurnEmbedder
from streetrace.guardrails.config import CognitiveMonitorConfig
from streetrace.guardrails.types import GuardrailAction
from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.dsl.runtime.guardrail_provider import GuardrailProvider
    from streetrace.guardrails.inference.pipeline import InferencePipeline

logger = get_logger(__name__)

_PROXY_NAME = "cognitive_monitor"
"""Proxy identifier for OTEL spans."""

_EMBEDDING_DIM_FALLBACK = 8
"""Fallback embedding dimension for text-hash embeddings."""

# Default suspicious sequence patterns
_DEFAULT_PATTERNS: list[SequencePattern] = [
    SequencePattern(
        name="data_exfiltration",
        sequence=["read_file", "encode_*", "send_*"],
    ),
    SequencePattern(
        name="privilege_escalation",
        sequence=["list_users", "modify_permissions", "*"],
    ),
]


class CognitiveMonitor:
    """Multi-turn intent drift detection guardrail.

    Implement the Guardrail protocol with name 'cognitive_drift'.
    Combine embedding-based drift tracking with sequence anomaly
    detection and recovery measurement.
    """

    def __init__(
        self,
        *,
        provider: GuardrailProvider,
        inference_pipeline: InferencePipeline | None = None,
        config: CognitiveMonitorConfig | None = None,
        gru_weights: dict[str, list[list[float]]] | None = None,
        sequence_patterns: list[SequencePattern] | None = None,
    ) -> None:
        """Initialize the cognitive monitor.

        Args:
            provider: GuardrailProvider for session context access.
            inference_pipeline: ONNX inference facade, or None for
                fallback text-hash embeddings.
            config: Monitor configuration. Uses defaults if None.
            gru_weights: Optional GRU weight matrices.
            sequence_patterns: Suspicious sequence patterns.

        """
        self._provider = provider
        self._config = config or CognitiveMonitorConfig()
        self._embedder = TurnEmbedder(
            inference_pipeline=inference_pipeline,
        )
        self._tracker = IntentTracker(
            provider=provider, gru_weights=gru_weights,
        )
        self._drift_detector = DriftDetector(config=self._config)
        self._anomaly_detector = SequenceAnomalyDetector(
            patterns=(
                sequence_patterns
                if sequence_patterns is not None
                else _DEFAULT_PATTERNS
            ),
        )
        self._mttr = MttrCalculator()
        self._inference_pipeline = inference_pipeline

    @property
    def name(self) -> str:
        """Return the guardrail name."""
        return "cognitive_drift"

    def mask_str(self, text: str) -> str:
        """Return text unchanged -- drift detection is check-only.

        Args:
            text: Input text.

        Returns:
            The input text unmodified.

        """
        return text

    def check_str(self, text: str) -> tuple[bool, str]:
        """Check if conversation shows intent drift.

        Embed the turn, compute risk, evaluate against thresholds,
        and manage intervention/recovery lifecycle.

        Args:
            text: Turn text to analyze.

        Returns:
            Tuple of (triggered, detail message).

        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            "guardrail.cognitive_monitor.check",
        ) as span:
            span.set_attribute(
                "streetrace.guardrail.proxy", _PROXY_NAME,
            )

            embedding = self._get_embedding(text)
            risk_score = self._tracker.compute_risk(embedding)
            turn_number = self._tracker.turn_count

            drift_result = self._drift_detector.evaluate(
                risk_score=risk_score, turn_number=turn_number,
            )

            # OTEL attributes
            span.set_attribute(
                "streetrace.guardrail.check.confidence", risk_score,
            )
            span.set_attribute(
                "streetrace.guardrail.risk_score", risk_score,
            )
            span.set_attribute(
                "streetrace.guardrail.turn_number", turn_number,
            )
            session_id = self._provider.session_id
            if session_id is not None:
                span.set_attribute(
                    "streetrace.guardrail.session_id", session_id,
                )

            # Intervention / recovery lifecycle
            self._handle_lifecycle(drift_result)

            triggered = drift_result.action != GuardrailAction.ALLOW
            detail = self._build_detail(drift_result)

            span.set_attribute(
                "streetrace.guardrail.triggered", triggered,
            )
            span.set_attribute(
                "streetrace.guardrail.violation.action",
                drift_result.action.value,
            )

            return triggered, detail

    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text, with fallback for no pipeline.

        When no InferencePipeline is available, generate a
        deterministic hash-based pseudo-embedding.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.

        """
        if self._inference_pipeline is not None:
            # Try sync embedding from cache
            cached = self._embedder.embed_sync(text)
            if cached is not None:
                return cached

        # Fallback: deterministic hash-based pseudo-embedding
        return _text_hash_embedding(text, _EMBEDDING_DIM_FALLBACK)

    def _handle_lifecycle(self, drift_result: DriftResult) -> None:
        """Handle intervention and recovery lifecycle.

        Args:
            drift_result: Current drift evaluation result.

        """
        if drift_result.action == GuardrailAction.BLOCK:
            if not self._mttr.is_recovering:
                self._mttr.record_intervention(
                    turn_number=drift_result.turn_number,
                    risk_score=drift_result.risk_score,
                )
        elif (
            self._mttr.is_recovering
            and drift_result.action == GuardrailAction.ALLOW
        ):
            self._mttr.record_recovery(
                turn_number=drift_result.turn_number,
                risk_score=drift_result.risk_score,
            )

    @staticmethod
    def _build_detail(drift_result: DriftResult) -> str:
        """Build detail message for the drift result.

        Args:
            drift_result: Drift evaluation result.

        Returns:
            Human-readable detail string.

        """
        if drift_result.action == GuardrailAction.BLOCK:
            return (
                f"Cognitive drift blocked: risk_score="
                f"{drift_result.risk_score:.4f} at turn "
                f"{drift_result.turn_number}"
            )
        if drift_result.action == GuardrailAction.WARN:
            return (
                f"Cognitive drift warning: risk_score="
                f"{drift_result.risk_score:.4f} at turn "
                f"{drift_result.turn_number}"
            )
        return ""


def _text_hash_embedding(text: str, dim: int) -> list[float]:
    """Generate a deterministic pseudo-embedding from text hash.

    Use SHA-256 bytes to produce a fixed-dimension vector.
    Not semantically meaningful, but deterministic and enables
    baseline cosine delta tracking without ONNX.

    Args:
        text: Text to embed.
        dim: Output embedding dimension.

    Returns:
        Pseudo-embedding vector.

    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Use bytes cyclically to fill the dimension
    values: list[float] = []
    for i in range(dim):
        byte_val = digest[i % len(digest)]
        # Map [0, 255] to [-1.0, 1.0]
        values.append((byte_val / 127.5) - 1.0)
    return values
