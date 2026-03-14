"""Intent tracker with two-tier risk scoring strategy.

Baseline: cosine similarity delta between consecutive turn embeddings.
Optional: GRU forward pass on embedding sequence when weights available.
Risk score is the maximum of both tiers.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.dsl.runtime.guardrail_provider import GuardrailProvider

logger = get_logger(__name__)

HIDDEN_STATE_KEY = "streetrace.cognitive_monitor.hidden_state"
"""Session state key for GRU hidden state vector."""

PREV_EMBEDDING_KEY = "streetrace.cognitive_monitor.prev_embedding"
"""Session state key for previous turn embedding."""

class IntentTracker:
    """Track intent drift with two-tier scoring.

    Tier 1 (baseline): Compute cosine delta between consecutive
    turn embeddings. Always runs.

    Tier 2 (GRU): If GRU weights are provided, run a forward pass
    and use the hidden state delta as an additional risk signal.
    Risk score is max(baseline, gru).
    """

    def __init__(
        self,
        *,
        provider: GuardrailProvider,
        gru_weights: dict[str, list[list[float]]] | None = None,
    ) -> None:
        """Initialize the tracker.

        Args:
            provider: GuardrailProvider for session context access.
            gru_weights: Optional GRU weight matrices.

        """
        self._provider = provider
        self._gru_weights = gru_weights
        self._turn_count = 0

    @property
    def turn_count(self) -> int:
        """Return the number of turns processed."""
        return self._turn_count

    def compute_risk(self, embedding: list[float]) -> float:
        """Compute risk score for the given turn embedding.

        On the first turn, establish baseline and return 0.0.
        On subsequent turns, compute cosine delta and optionally
        run GRU forward pass.

        Args:
            embedding: Current turn embedding vector.

        Returns:
            Risk score between 0.0 and 1.0.

        """
        self._turn_count += 1
        state = self._get_session_state()

        prev_embedding = self._read_prev_embedding(state)
        self._write_prev_embedding(state, embedding)

        if prev_embedding is None:
            logger.debug("First turn, establishing baseline")
            if self._gru_weights is not None:
                hidden_size = len(self._gru_weights["b_z"][0])
                self._write_hidden_state(
                    state, [0.0] * hidden_size,
                )
            return 0.0

        # Tier 1: Baseline cosine delta
        baseline_risk = _cosine_delta(prev_embedding, embedding)

        # Tier 2: Optional GRU forward pass
        gru_risk = 0.0
        if self._gru_weights is not None:
            gru_risk = self._gru_forward(state, embedding)

        risk = max(baseline_risk, gru_risk)
        risk = max(0.0, min(1.0, risk))

        logger.debug(
            "Turn %d risk: baseline=%.4f, gru=%.4f, final=%.4f",
            self._turn_count, baseline_risk, gru_risk, risk,
        )
        return risk

    def _gru_forward(
        self,
        state: dict[str, object],
        embedding: list[float],
    ) -> float:
        """Run GRU forward pass and compute risk from hidden state.

        Args:
            state: Session state dict.
            embedding: Current turn embedding.

        Returns:
            GRU-based risk score.

        """
        assert self._gru_weights is not None  # noqa: S101  # nosec B101
        weights = self._gru_weights

        h_prev = self._read_hidden_state(state)
        hidden_size = len(weights["b_z"][0])

        if h_prev is None:
            h_prev = [0.0] * hidden_size

        x = embedding

        # Update gate: z = sigmoid(W_z @ x + U_z @ h_prev + b_z)
        z = _sigmoid_vec(
            _add_vec(
                _add_vec(
                    _mat_vec(weights["W_z"], x),
                    _mat_vec(weights["U_z"], h_prev),
                ),
                weights["b_z"][0],
            ),
        )

        # Reset gate: r = sigmoid(W_r @ x + U_r @ h_prev + b_r)
        r = _sigmoid_vec(
            _add_vec(
                _add_vec(
                    _mat_vec(weights["W_r"], x),
                    _mat_vec(weights["U_r"], h_prev),
                ),
                weights["b_r"][0],
            ),
        )

        # Candidate hidden state
        r_h = _elem_mul(r, h_prev)
        h_tilde = _tanh_vec(
            _add_vec(
                _add_vec(
                    _mat_vec(weights["W_h"], x),
                    _mat_vec(weights["U_h"], r_h),
                ),
                weights["b_h"][0],
            ),
        )

        # New hidden state: h = (1 - z) * h_prev + z * h_tilde
        h_new = _add_vec(
            _elem_mul(_sub_from_one(z), h_prev),
            _elem_mul(z, h_tilde),
        )

        self._write_hidden_state(state, h_new)

        # Risk from hidden state magnitude change
        delta = _l2_norm(_sub_vec(h_new, h_prev))
        max_delta = math.sqrt(float(hidden_size)) * 2.0
        return min(1.0, delta / max_delta) if max_delta > 0 else 0.0

    def _get_session_state(self) -> dict[str, object]:
        """Return the session state dict from the provider.

        Returns:
            Mutable session state dictionary.

        """
        state = self._provider.session_state
        if state is None:
            return {}
        return state

    def _read_prev_embedding(
        self, state: dict[str, object],
    ) -> list[float] | None:
        """Read previous embedding from session state.

        Args:
            state: Session state dict.

        Returns:
            Previous embedding or None.

        """
        raw = state.get(PREV_EMBEDDING_KEY)
        if isinstance(raw, list):
            return [float(v) for v in raw]
        return None

    @staticmethod
    def _write_prev_embedding(
        state: dict[str, object],
        embedding: list[float],
    ) -> None:
        """Write embedding to session state.

        Args:
            state: Session state dict.
            embedding: Embedding vector to store.

        """
        state[PREV_EMBEDDING_KEY] = embedding

    def _read_hidden_state(
        self, state: dict[str, object],
    ) -> list[float] | None:
        """Read GRU hidden state from session state.

        Args:
            state: Session state dict.

        Returns:
            Hidden state vector or None.

        """
        raw = state.get(HIDDEN_STATE_KEY)
        if isinstance(raw, list):
            return [float(v) for v in raw]
        return None

    @staticmethod
    def _write_hidden_state(
        state: dict[str, object],
        hidden: list[float],
    ) -> None:
        """Write GRU hidden state to session state.

        Args:
            state: Session state dict.
            hidden: Hidden state vector to store.

        """
        state[HIDDEN_STATE_KEY] = hidden


# ---------------------------------------------------------------------------
# Pure math helpers (no numpy dependency)
# ---------------------------------------------------------------------------


def _cosine_delta(a: list[float], b: list[float]) -> float:
    """Compute cosine delta: (1 - cosine_similarity) / 2.

    Result is in [0.0, 1.0] where 0 = identical, 1 = opposite.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Cosine delta score.

    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    similarity = dot / (norm_a * norm_b)
    return (1.0 - similarity) / 2.0


def _mat_vec(
    matrix: list[list[float]], vec: list[float],
) -> list[float]:
    """Multiply matrix (rows x cols) by vector (cols).

    Args:
        matrix: Weight matrix.
        vec: Input vector.

    Returns:
        Result vector.

    """
    return [
        sum(row[j] * vec[j] for j in range(len(vec)))
        for row in matrix
    ]


def _add_vec(a: list[float], b: list[float]) -> list[float]:
    """Element-wise vector addition.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Sum vector.

    """
    return [x + y for x, y in zip(a, b, strict=True)]


def _sub_vec(a: list[float], b: list[float]) -> list[float]:
    """Element-wise vector subtraction.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Difference vector.

    """
    return [x - y for x, y in zip(a, b, strict=True)]


def _elem_mul(a: list[float], b: list[float]) -> list[float]:
    """Element-wise vector multiplication.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Product vector.

    """
    return [x * y for x, y in zip(a, b, strict=True)]


def _sub_from_one(vec: list[float]) -> list[float]:
    """Compute 1 - x for each element.

    Args:
        vec: Input vector.

    Returns:
        Result vector.

    """
    return [1.0 - x for x in vec]


def _sigmoid(x: float) -> float:
    """Compute sigmoid activation.

    Args:
        x: Input value.

    Returns:
        Sigmoid output.

    """
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def _sigmoid_vec(vec: list[float]) -> list[float]:
    """Apply sigmoid to each element.

    Args:
        vec: Input vector.

    Returns:
        Sigmoid-activated vector.

    """
    return [_sigmoid(x) for x in vec]


def _tanh_vec(vec: list[float]) -> list[float]:
    """Apply tanh to each element.

    Args:
        vec: Input vector.

    Returns:
        Tanh-activated vector.

    """
    return [math.tanh(x) for x in vec]


def _l2_norm(vec: list[float]) -> float:
    """Compute L2 norm of a vector.

    Args:
        vec: Input vector.

    Returns:
        L2 norm.

    """
    return math.sqrt(sum(x * x for x in vec))
