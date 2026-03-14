"""Tests for IntentTracker: cosine delta, GRU, risk scoring, state."""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from streetrace.guardrails.cognitive.intent_tracker import IntentTracker

SESSION_ID = "test-session-001"

HIDDEN_STATE_KEY = "streetrace.cognitive_monitor.hidden_state"
PREV_EMBEDDING_KEY = "streetrace.cognitive_monitor.prev_embedding"


def _make_provider(
    session_id: str = SESSION_ID,
    session_state: dict[str, object] | None = None,
) -> MagicMock:
    """Create a mock GuardrailProvider with session context."""
    provider = MagicMock()
    provider.session_id = session_id
    provider.session_state = session_state if session_state is not None else {}
    return provider


class TestBaselineCosineeDelta:
    """Verify baseline cosine similarity delta scoring."""

    def test_first_turn_zero_risk(self) -> None:
        """First turn has no previous embedding, risk is 0."""
        provider = _make_provider()
        tracker = IntentTracker(provider=provider)

        score = tracker.compute_risk([0.1, 0.2, 0.3])
        assert score == 0.0

    def test_identical_embeddings_zero_risk(self) -> None:
        """Identical consecutive embeddings produce zero risk."""
        provider = _make_provider()
        tracker = IntentTracker(provider=provider)

        tracker.compute_risk([1.0, 0.0, 0.0])
        score = tracker.compute_risk([1.0, 0.0, 0.0])
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_orthogonal_embeddings_high_risk(self) -> None:
        """Orthogonal embeddings produce high risk."""
        provider = _make_provider()
        tracker = IntentTracker(provider=provider)

        tracker.compute_risk([1.0, 0.0, 0.0])
        score = tracker.compute_risk([0.0, 1.0, 0.0])
        assert score >= 0.5

    def test_opposite_embeddings_max_risk(self) -> None:
        """Opposite embeddings produce maximum risk."""
        provider = _make_provider()
        tracker = IntentTracker(provider=provider)

        tracker.compute_risk([1.0, 0.0, 0.0])
        score = tracker.compute_risk([-1.0, 0.0, 0.0])
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_gradually_increasing_risk(self) -> None:
        """Gradual drift produces increasing risk scores."""
        provider = _make_provider()
        tracker = IntentTracker(provider=provider)

        # Stable start
        tracker.compute_risk([1.0, 0.0, 0.0])
        score1 = tracker.compute_risk([0.9, 0.1, 0.0])
        score2 = tracker.compute_risk([0.5, 0.5, 0.0])
        score3 = tracker.compute_risk([0.0, 1.0, 0.0])

        assert score1 < score2 < score3


class TestSessionStatePersistence:
    """Verify state persistence across calls via session state."""

    def test_stores_prev_embedding_in_session(self) -> None:
        """Previous embedding is stored in session state."""
        state: dict[str, object] = {}
        provider = _make_provider(session_state=state)
        tracker = IntentTracker(provider=provider)

        embedding = [0.1, 0.2, 0.3]
        tracker.compute_risk(embedding)

        assert PREV_EMBEDDING_KEY in state
        assert state[PREV_EMBEDDING_KEY] == embedding

    def test_reads_prev_embedding_from_session(self) -> None:
        """Read previous embedding from session state on compute."""
        state: dict[str, object] = {
            PREV_EMBEDDING_KEY: [1.0, 0.0, 0.0],
        }
        provider = _make_provider(session_state=state)
        tracker = IntentTracker(provider=provider)

        # Should compute delta against stored embedding
        score = tracker.compute_risk([0.0, 1.0, 0.0])
        assert score >= 0.5

    def test_new_session_fresh_state(self) -> None:
        """New session ID starts with fresh state."""
        state1: dict[str, object] = {}
        provider1 = _make_provider(session_id="session-1", session_state=state1)
        tracker1 = IntentTracker(provider=provider1)

        tracker1.compute_risk([1.0, 0.0, 0.0])
        tracker1.compute_risk([0.0, 1.0, 0.0])

        # New session, empty state
        state2: dict[str, object] = {}
        provider2 = _make_provider(session_id="session-2", session_state=state2)
        tracker2 = IntentTracker(provider=provider2)
        score = tracker2.compute_risk([0.0, 1.0, 0.0])

        # First turn in new session => zero risk
        assert score == 0.0


class TestTurnCounting:
    """Verify turn count tracking."""

    def test_turn_count_increments(self) -> None:
        """Turn count increments on each compute_risk call."""
        provider = _make_provider()
        tracker = IntentTracker(provider=provider)

        assert tracker.turn_count == 0
        tracker.compute_risk([1.0, 0.0])
        assert tracker.turn_count == 1
        tracker.compute_risk([0.9, 0.1])
        assert tracker.turn_count == 2


class TestGruForwardPass:
    """Verify optional GRU forward pass when weights are available."""

    def test_gru_risk_when_weights_provided(self) -> None:
        """GRU forward pass produces a risk score when weights given."""
        provider = _make_provider()
        # Provide mock GRU weights as simple matrices
        hidden_size = 3
        input_size = 3
        gru_weights = _make_gru_weights(input_size, hidden_size)
        tracker = IntentTracker(
            provider=provider, gru_weights=gru_weights,
        )

        tracker.compute_risk([0.5, 0.3, 0.2])
        score = tracker.compute_risk([0.1, 0.8, 0.1])
        assert 0.0 <= score <= 1.0

    def test_risk_is_max_of_baseline_and_gru(self) -> None:
        """Risk score is the maximum of baseline and GRU scores."""
        provider = _make_provider()
        hidden_size = 3
        input_size = 3
        gru_weights = _make_gru_weights(input_size, hidden_size)
        tracker = IntentTracker(
            provider=provider, gru_weights=gru_weights,
        )

        # First turn
        tracker.compute_risk([1.0, 0.0, 0.0])
        # Second turn with orthogonal vector -> high baseline
        score = tracker.compute_risk([0.0, 1.0, 0.0])
        # Score should be >= baseline cosine delta
        baseline_risk = _cosine_delta(
            [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
        )
        assert score >= baseline_risk - 1e-6

    def test_gru_hidden_state_stored_in_session(self) -> None:
        """GRU hidden state is persisted in session state."""
        state: dict[str, object] = {}
        provider = _make_provider(session_state=state)
        hidden_size = 3
        input_size = 3
        gru_weights = _make_gru_weights(input_size, hidden_size)
        tracker = IntentTracker(
            provider=provider, gru_weights=gru_weights,
        )

        tracker.compute_risk([0.5, 0.3, 0.2])
        assert HIDDEN_STATE_KEY in state


def _make_gru_weights(
    input_size: int, hidden_size: int,
) -> dict[str, list[list[float]]]:
    """Create simple GRU weight matrices for testing."""
    import random

    random.seed(42)

    def rand_matrix(rows: int, cols: int) -> list[list[float]]:
        return [
            [random.uniform(-0.5, 0.5) for _ in range(cols)]  # noqa: S311
            for _ in range(rows)
        ]

    return {
        "W_z": rand_matrix(input_size, hidden_size),
        "U_z": rand_matrix(hidden_size, hidden_size),
        "b_z": [[random.uniform(-0.1, 0.1) for _ in range(hidden_size)]],  # noqa: S311
        "W_r": rand_matrix(input_size, hidden_size),
        "U_r": rand_matrix(hidden_size, hidden_size),
        "b_r": [[random.uniform(-0.1, 0.1) for _ in range(hidden_size)]],  # noqa: S311
        "W_h": rand_matrix(input_size, hidden_size),
        "U_h": rand_matrix(hidden_size, hidden_size),
        "b_h": [[random.uniform(-0.1, 0.1) for _ in range(hidden_size)]],  # noqa: S311
    }


def _cosine_delta(a: list[float], b: list[float]) -> float:
    """Compute cosine delta (1 - cosine_similarity) / 2."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    similarity = dot / (norm_a * norm_b)
    return (1.0 - similarity) / 2.0
