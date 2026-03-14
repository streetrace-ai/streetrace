"""Trust evaluator for MCP server trust scoring.

Maintain per-server trust scores and manifest hashes for
rug-pull detection. Trust scores decrease when manifests change.
"""

from __future__ import annotations

from dataclasses import dataclass

from streetrace.log import get_logger

logger = get_logger(__name__)

DEFAULT_TRUST_SCORE = 0.7
"""Default trust score for newly seen servers."""

RUG_PULL_PENALTY = 0.5
"""Trust score reduction when manifest hash changes."""


@dataclass(frozen=True)
class TrustResult:
    """Result of trust evaluation.

    Attributes:
        trust_score: Current trust score for the server.
        is_trusted: Whether the score meets the threshold.
        reason: Explanation of the trust decision.

    """

    trust_score: float
    is_trusted: bool
    reason: str


class TrustEvaluator:
    """Evaluate MCP server trustworthiness.

    Track per-server trust scores and manifest hashes.
    Detect rug-pull attacks by comparing current manifest
    hashes against stored values.
    """

    def __init__(self, *, trust_threshold: float) -> None:
        """Initialize the trust evaluator.

        Args:
            trust_threshold: Minimum trust score to consider
                a server trusted.

        """
        self._threshold = trust_threshold
        self._trust_scores: dict[str, float] = {}
        self._manifest_hashes: dict[str, str] = {}

    def evaluate(self, server_id: str) -> TrustResult:
        """Evaluate trust for a server.

        Args:
            server_id: Identifier of the MCP server.

        Returns:
            TrustResult with current trust status.

        """
        score = self._trust_scores.get(server_id, DEFAULT_TRUST_SCORE)
        is_trusted = score >= self._threshold

        if is_trusted:
            reason = "Server trust score meets threshold"
        else:
            reason = (
                f"Server trust score {score:.2f} "
                f"below threshold {self._threshold:.2f}"
            )

        return TrustResult(
            trust_score=score,
            is_trusted=is_trusted,
            reason=reason,
        )

    def set_trust_score(
        self,
        server_id: str,
        score: float,
    ) -> None:
        """Set the trust score for a server.

        Args:
            server_id: Server identifier.
            score: New trust score (0.0 to 1.0).

        """
        self._trust_scores[server_id] = max(0.0, min(1.0, score))
        logger.info(
            "Trust score for %s set to %.2f",
            server_id,
            self._trust_scores[server_id],
        )

    def register_manifest(
        self,
        server_id: str,
        manifest_hash: str,
    ) -> None:
        """Register the initial manifest hash for a server.

        Args:
            server_id: Server identifier.
            manifest_hash: SHA-256 hash of the server manifest.

        """
        self._manifest_hashes[server_id] = manifest_hash
        logger.info(
            "Registered manifest hash for %s: %s",
            server_id,
            manifest_hash[:16],
        )

    def check_manifest(
        self,
        server_id: str,
        current_hash: str,
    ) -> TrustResult:
        """Check manifest hash and evaluate trust.

        Compare current manifest hash against stored value.
        If the hash has changed, reduce trust score and flag
        the change. First-time registrations are trusted.

        Args:
            server_id: Server identifier.
            current_hash: Current manifest hash.

        Returns:
            TrustResult reflecting manifest check outcome.

        """
        stored_hash = self._manifest_hashes.get(server_id)

        if stored_hash is None:
            # First time seeing this server
            self.register_manifest(server_id, current_hash)
            return TrustResult(
                trust_score=self._trust_scores.get(
                    server_id, DEFAULT_TRUST_SCORE,
                ),
                is_trusted=True,
                reason="First manifest registration",
            )

        if stored_hash == current_hash:
            return self.evaluate(server_id)

        # Manifest changed -- possible rug pull
        logger.warning(
            "Manifest hash changed for %s: %s -> %s",
            server_id,
            stored_hash[:16],
            current_hash[:16],
        )

        old_score = self._trust_scores.get(
            server_id, DEFAULT_TRUST_SCORE,
        )
        new_score = max(0.0, old_score - RUG_PULL_PENALTY)
        self._trust_scores[server_id] = new_score
        self._manifest_hashes[server_id] = current_hash

        return TrustResult(
            trust_score=new_score,
            is_trusted=False,
            reason=(
                f"Manifest hash changed for server '{server_id}'. "
                f"Trust reduced from {old_score:.2f} to {new_score:.2f}"
            ),
        )
