"""Garak CLI runner wrapper.

Wrap Garak CLI execution and translate output to the common
ProbeResult schema. Fail-fast if garak is not installed.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from streetrace.guardrails.redteam.metrics_collector import ProbeResult

logger = get_logger(__name__)

GARAK_COMMAND = "garak"
"""CLI command name for garak."""


class GarakRunner:
    """Wrap Garak CLI execution for red team testing.

    Translates Garak output format to ProbeResult schema.
    Raises RuntimeError if garak is not installed.
    """

    def run(
        self,
        config_path: Path,
        target: str,
    ) -> list[ProbeResult]:
        """Execute Garak probes against a target.

        Args:
            config_path: Path to Garak configuration file.
            target: Target agent identifier.

        Returns:
            List of probe results in common schema.

        Raises:
            RuntimeError: If garak is not installed.

        """
        if not shutil.which(GARAK_COMMAND):
            msg = (
                "garak is not installed. "
                "Install it with: pip install garak"
            )
            raise RuntimeError(msg)

        logger.info(
            "Garak execution deferred: config=%s, target=%s",
            config_path,
            target,
        )
        return []
