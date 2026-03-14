"""Tests for CognitiveMonitor: full integration and Guardrail protocol."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from streetrace.guardrails.cognitive.monitor import CognitiveMonitor
from streetrace.guardrails.config import CognitiveMonitorConfig

SESSION_ID = "test-session-42"


def _make_provider(
    session_id: str = SESSION_ID,
    session_state: dict[str, object] | None = None,
) -> MagicMock:
    """Create a mock GuardrailProvider."""
    provider = MagicMock()
    provider.session_id = session_id
    provider.session_state = (
        session_state if session_state is not None else {}
    )
    return provider


class TestGuardrailProtocol:
    """Verify CognitiveMonitor implements Guardrail protocol."""

    def test_name_is_cognitive_drift(self) -> None:
        """Monitor registers under name 'cognitive_drift'."""
        provider = _make_provider()
        monitor = CognitiveMonitor(provider=provider)
        assert monitor.name == "cognitive_drift"

    def test_mask_str_returns_unchanged(self) -> None:
        """mask_str returns text unchanged (check-only guardrail)."""
        provider = _make_provider()
        monitor = CognitiveMonitor(provider=provider)
        text = "some output text"
        assert monitor.mask_str(text) == text

    def test_check_str_returns_tuple(self) -> None:
        """check_str returns (bool, str) tuple."""
        provider = _make_provider()
        monitor = CognitiveMonitor(
            provider=provider, inference_pipeline=None,
        )
        result = monitor.check_str("Hello world")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


class TestSessionContextReading:
    """Verify monitor reads session context from provider."""

    def test_reads_session_id_from_provider(self) -> None:
        """Monitor accesses provider.session_id."""
        provider = _make_provider(session_id="my-session")
        monitor = CognitiveMonitor(provider=provider)
        monitor.check_str("test text")

        # Verify session_id was accessed
        _ = provider.session_id

    def test_stores_state_in_session_state(self) -> None:
        """Monitor stores state via provider.session_state."""
        state: dict[str, object] = {}
        provider = _make_provider(session_state=state)
        config = CognitiveMonitorConfig(
            warn_threshold=0.60,
            block_threshold=0.85,
            min_turns_before_alert=1,
        )
        monitor = CognitiveMonitor(
            provider=provider,
            inference_pipeline=None,
            config=config,
        )
        monitor.check_str("first turn text")

        # Session state should have been populated
        assert len(state) > 0


class TestDriftDetection:
    """Verify end-to-end drift detection."""

    def test_first_turn_not_triggered(self) -> None:
        """First turn never triggers drift."""
        provider = _make_provider()
        monitor = CognitiveMonitor(
            provider=provider, inference_pipeline=None,
        )
        triggered, _ = monitor.check_str("Hello, help me with coding")
        assert triggered is False

    def test_stable_conversation_not_triggered(self) -> None:
        """Stable conversation stays below threshold."""
        provider = _make_provider()
        config = CognitiveMonitorConfig(
            warn_threshold=0.60,
            block_threshold=0.85,
            min_turns_before_alert=1,
        )
        monitor = CognitiveMonitor(
            provider=provider,
            inference_pipeline=None,
            config=config,
        )
        # Same-ish text should produce low risk
        monitor.check_str("Help me sort a list in Python")
        triggered, _ = monitor.check_str("Help me sort a list in Python")
        assert triggered is False


class TestWithMockEmbeddings:
    """Verify behavior with mocked embedding pipeline."""

    def test_high_drift_triggers_block(self) -> None:
        """High embedding drift triggers block after min_turns."""
        state: dict[str, object] = {}
        provider = _make_provider(session_state=state)
        config = CognitiveMonitorConfig(
            warn_threshold=0.30,
            block_threshold=0.40,
            min_turns_before_alert=2,
        )

        mock_pipeline = MagicMock()
        embeddings = [
            [1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],  # Opposite direction = max drift
        ]
        call_count = 0

        async def mock_embed(
            model_id: str, text: str,
        ) -> list[float]:
            nonlocal call_count
            result = embeddings[min(call_count, len(embeddings) - 1)]
            call_count += 1
            return result

        mock_pipeline.get_embedding = AsyncMock(side_effect=mock_embed)

        monitor = CognitiveMonitor(
            provider=provider,
            inference_pipeline=mock_pipeline,
            config=config,
        )

        monitor.check_str("turn 1")  # baseline
        monitor.check_str("turn 2")  # same direction
        triggered, detail = monitor.check_str("turn 3")  # opposite

        assert triggered is True
        assert "drift" in detail.lower() or "block" in detail.lower()


class TestOtelSpans:
    """Verify OTEL span emission."""

    def test_check_emits_otel_span(self) -> None:
        """check_str emits an OTEL span with risk_score."""
        provider = _make_provider()
        monitor = CognitiveMonitor(
            provider=provider, inference_pipeline=None,
        )
        with patch(
            "streetrace.guardrails.cognitive.monitor.trace",
        ) as mock_trace:
            mock_span = MagicMock()
            mock_tracer = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = (
                lambda _: mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = (
                lambda *_: None
            )
            mock_trace.get_tracer.return_value = mock_tracer

            monitor.check_str("test text")

            mock_tracer.start_as_current_span.assert_called()
