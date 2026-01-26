"""Agent validation exceptions.

This module provides exception classes for agent validation errors.
These exceptions are used by the workload loaders for validation errors.
"""

from pathlib import Path


class AgentValidationError(Exception):
    """Raised when agent validation fails."""

    def __init__(
        self,
        message: str,
        file_path: Path | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize the Agent Validation Error."""
        self.file_path = file_path
        self.cause = cause
        super().__init__(message)


class AgentCycleError(AgentValidationError):
    """Raised when circular references are detected."""
