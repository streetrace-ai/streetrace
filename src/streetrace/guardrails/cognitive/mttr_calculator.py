"""MTTR-A Calculator for measuring cognitive recovery latency.

Measure recovery turns and wall-clock time after a drift
intervention, emitting OTEL metrics for compliance reporting.
"""

from __future__ import annotations

import time

from streetrace.log import get_logger

logger = get_logger(__name__)


class MttrCalculator:
    """Measure recovery after drift intervention.

    Track the number of turns and wall-clock time between an
    intervention event and recovery (risk returning below threshold).
    """

    def __init__(self) -> None:
        """Initialize with no active intervention."""
        self._intervention_turn: int | None = None
        self._intervention_time: float | None = None
        self._recovery_turns: int | None = None
        self._recovery_time_ms: float | None = None
        self._is_recovering = False

    @property
    def intervention_turn(self) -> int | None:
        """Return the turn number of the most recent intervention."""
        return self._intervention_turn

    @property
    def is_recovering(self) -> bool:
        """Return True if currently in recovery phase."""
        return self._is_recovering

    @property
    def recovery_turns(self) -> int | None:
        """Return the number of turns taken to recover."""
        return self._recovery_turns

    @property
    def recovery_time_ms(self) -> float | None:
        """Return recovery wall-clock time in milliseconds."""
        return self._recovery_time_ms

    def record_intervention(
        self, *, turn_number: int, risk_score: float,
    ) -> None:
        """Record a drift intervention event.

        Args:
            turn_number: Turn where intervention occurred.
            risk_score: Risk score that triggered intervention.

        """
        self._intervention_turn = turn_number
        self._intervention_time = time.monotonic()
        self._is_recovering = True
        self._recovery_turns = None
        self._recovery_time_ms = None

        logger.info(
            "Intervention at turn %d, risk=%.4f",
            turn_number, risk_score,
        )

    def record_recovery(
        self, *, turn_number: int, risk_score: float,
    ) -> None:
        """Record a recovery event (risk back below threshold).

        Only effective if an intervention was previously recorded.

        Args:
            turn_number: Turn where recovery was detected.
            risk_score: Risk score at recovery.

        """
        if self._intervention_turn is None or not self._is_recovering:
            return

        self._recovery_turns = turn_number - self._intervention_turn
        if self._intervention_time is not None:
            elapsed = time.monotonic() - self._intervention_time
            self._recovery_time_ms = elapsed * 1000.0

        self._is_recovering = False

        logger.info(
            "Recovery at turn %d (took %d turns, %.1f ms), risk=%.4f",
            turn_number,
            self._recovery_turns,
            self._recovery_time_ms or 0.0,
            risk_score,
        )
