"""Workload metadata dataclass.

This module provides the WorkloadMetadata dataclass that holds immutable
metadata about a workload definition.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class WorkloadMetadata:
    """Immutable metadata about a workload definition.

    This dataclass holds the essential metadata for identifying and describing
    a workload. It is frozen (immutable) to ensure that once created, the
    metadata cannot be modified, providing consistency throughout the workload
    lifecycle.

    Attributes:
        name: Unique identifier for the workload
        description: Human-readable description of what the workload does
        source_path: Path to the source file (None for HTTP sources)
        format: The format type of the workload source (dsl, yaml, or python)

    """

    name: str
    description: str
    source_path: Path | None
    format: Literal["dsl", "yaml", "python"]
