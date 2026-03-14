"""Probe library for red team CI testing.

Discover and load probe definitions from YAML files. Each probe
defines attack strings, expected guardrail action, and category.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, model_validator

from streetrace.guardrails.types import GuardrailAction  # noqa: TC001
from streetrace.log import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

YAML_EXTENSIONS = frozenset({".yaml", ".yml"})
"""File extensions recognized as YAML probe definitions."""


class ProbeCategory(StrEnum):
    """Category of a red team probe."""

    INJECTION = "injection"
    DRIFT = "drift"
    TOOL_ABUSE = "tool_abuse"


class ProbeDefinition(BaseModel):
    """Define a single red team probe.

    Attributes:
        name: Unique probe identifier.
        description: Human-readable description of the attack.
        category: Attack category (injection, drift, tool_abuse).
        attack_strings: List of attack payloads to send.
        expected_action: Expected guardrail response.

    """

    name: str
    description: str
    category: ProbeCategory
    attack_strings: list[str]
    expected_action: GuardrailAction

    @model_validator(mode="after")
    def _validate_fields(self) -> ProbeDefinition:
        """Ensure required fields are non-empty."""
        if not self.name.strip():
            msg = "name must not be empty"
            raise ValueError(msg)
        if not self.attack_strings:
            msg = "attack_strings must contain at least one entry"
            raise ValueError(msg)
        return self


class ProbeLibrary:
    """Discover and load probe definitions from YAML files."""

    def __init__(self) -> None:
        """Initialize an empty probe library."""
        self._probes: list[ProbeDefinition] = []

    def load_directory(self, path: Path) -> None:
        """Load all YAML probe definitions from a directory.

        Args:
            path: Directory containing probe YAML files.

        Raises:
            FileNotFoundError: If the directory does not exist.
            ValueError: If a probe fails validation.

        """
        if not path.exists():
            msg = f"Probe directory does not exist: {path}"
            raise FileNotFoundError(msg)

        for file_path in sorted(path.iterdir()):
            if file_path.suffix not in YAML_EXTENSIONS:
                continue
            logger.debug("Loading probe from %s", file_path)
            with file_path.open() as f:
                data = yaml.safe_load(f)
            probe = ProbeDefinition.model_validate(data)
            self.validate_probe(probe)
            self._probes.append(probe)

    def get_probes(
        self,
        *,
        category: ProbeCategory | None = None,
    ) -> list[ProbeDefinition]:
        """Return probes, optionally filtered by category.

        Args:
            category: If provided, return only probes in this category.

        Returns:
            List of matching probe definitions.

        """
        if category is None:
            return list(self._probes)
        return [p for p in self._probes if p.category == category]

    def validate_probe(self, probe: ProbeDefinition) -> None:
        """Validate a probe definition.

        Re-runs Pydantic validation to confirm all fields are valid.

        Args:
            probe: The probe definition to validate.

        """
        ProbeDefinition.model_validate(probe.model_dump())
