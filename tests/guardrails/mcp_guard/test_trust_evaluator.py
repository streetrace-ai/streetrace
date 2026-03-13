"""Tests for TrustEvaluator: trust scoring and rug-pull detection."""

from __future__ import annotations

from streetrace.guardrails.mcp_guard.trust_evaluator import TrustEvaluator


class TestTrustScoring:
    """Verify per-server trust scoring."""

    def test_new_server_gets_default_trust(self) -> None:
        """New server starts with default trust score."""
        evaluator = TrustEvaluator(trust_threshold=0.5)
        result = evaluator.evaluate("new-server")
        assert result.trust_score > 0.0
        assert result.is_trusted is True

    def test_server_below_threshold_is_untrusted(self) -> None:
        """Server with trust below threshold is untrusted."""
        evaluator = TrustEvaluator(trust_threshold=0.8)
        # Set a low trust score manually
        evaluator.set_trust_score("low-trust-server", 0.3)
        result = evaluator.evaluate("low-trust-server")
        assert result.is_trusted is False
        assert "below threshold" in result.reason.lower()

    def test_server_above_threshold_is_trusted(self) -> None:
        """Server with trust above threshold is trusted."""
        evaluator = TrustEvaluator(trust_threshold=0.5)
        evaluator.set_trust_score("good-server", 0.9)
        result = evaluator.evaluate("good-server")
        assert result.is_trusted is True
        assert result.trust_score == 0.9


class TestRugPullDetection:
    """Verify rug-pull detection via manifest hash comparison."""

    def test_stable_manifest_trusted(self) -> None:
        """Server with stable manifest hash remains trusted."""
        evaluator = TrustEvaluator(trust_threshold=0.5)
        evaluator.register_manifest("server-a", "hash-abc123")
        result = evaluator.check_manifest("server-a", "hash-abc123")
        assert result.is_trusted is True

    def test_changed_manifest_triggers_re_evaluation(self) -> None:
        """Manifest hash change triggers trust re-evaluation."""
        evaluator = TrustEvaluator(trust_threshold=0.5)
        evaluator.register_manifest("server-a", "hash-abc123")
        evaluator.set_trust_score("server-a", 0.9)

        result = evaluator.check_manifest("server-a", "hash-xyz789")
        assert result.is_trusted is False
        assert "manifest" in result.reason.lower()

    def test_unknown_server_manifest_registered(self) -> None:
        """First manifest registration for unknown server succeeds."""
        evaluator = TrustEvaluator(trust_threshold=0.5)
        result = evaluator.check_manifest("new-server", "hash-first")
        # First time seeing this server, register and trust
        assert result.is_trusted is True

    def test_trust_score_decreases_on_manifest_change(self) -> None:
        """Trust score decreases when manifest changes."""
        evaluator = TrustEvaluator(trust_threshold=0.5)
        evaluator.register_manifest("server-a", "hash-original")
        evaluator.set_trust_score("server-a", 0.9)

        evaluator.check_manifest("server-a", "hash-changed")
        result = evaluator.evaluate("server-a")
        assert result.trust_score < 0.9


class TestTrustResult:
    """Verify TrustResult structure."""

    def test_result_has_required_fields(self) -> None:
        """TrustResult has trust_score, is_trusted, and reason."""
        evaluator = TrustEvaluator(trust_threshold=0.5)
        result = evaluator.evaluate("any-server")
        assert hasattr(result, "trust_score")
        assert hasattr(result, "is_trusted")
        assert hasattr(result, "reason")
        assert isinstance(result.trust_score, float)
        assert isinstance(result.is_trusted, bool)
        assert isinstance(result.reason, str)
