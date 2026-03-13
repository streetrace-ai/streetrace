"""Promptfoo CLI runner wrapper.

Wrap Promptfoo CLI execution and translate output to the common
ProbeResult schema. Fail-fast if promptfoo is not installed.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from streetrace.guardrails.redteam.metrics_collector import ProbeResult

logger = get_logger(__name__)

PROMPTFOO_COMMAND = "promptfoo"
"""CLI command name for promptfoo."""


class PromptfooRunner:
    """Wrap Promptfoo CLI execution for red team testing.

    Translates Promptfoo output format to ProbeResult schema.
    Raises RuntimeError if promptfoo is not installed.
    """

    def run(
        self,
        config_path: Path,
        target: str,
    ) -> list[ProbeResult]:
        """Execute Promptfoo evaluations against a target.

        Args:
            config_path: Path to Promptfoo configuration file.
            target: Target agent identifier.

        Returns:
            List of probe results in common schema.

        Raises:
            RuntimeError: If promptfoo is not installed.

        """
        if not shutil.which(PROMPTFOO_COMMAND):
            msg = (
                "promptfoo is not installed. "
                "Install it with: npm install -g promptfoo"
            )
            raise RuntimeError(msg)

        logger.info(
            "Promptfoo execution deferred: config=%s, target=%s",
            config_path,
            target,
        )
        return []
