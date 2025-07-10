"""Core data models for step-based execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(Enum):
    """Status of a step in the execution plan."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(Enum):
    """Type of step to execute."""

    ANALYZE = "analyze"
    GENERATE = "generate"
    MODIFY = "modify"
    VALIDATE = "validate"
    CLEANUP = "cleanup"


@dataclass
class StepContext:
    """Minimal context for a single step execution."""

    step_id: str
    step_type: StepType
    goal: str
    relevant_files: list[str] = field(default_factory=list)
    dependencies: set[str] = field(default_factory=set)
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_artifact(self, key: str, value: Any) -> None:
        """Add an artifact to the context."""
        self.artifacts[key] = value

    def get_artifact(self, key: str) -> Any:
        """Get an artifact from the context."""
        return self.artifacts.get(key)

    def has_artifact(self, key: str) -> bool:
        """Check if an artifact exists in the context."""
        return key in self.artifacts


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""

    id: str
    name: str
    description: str
    step_type: StepType
    goal: str
    relevant_files: list[str] = field(default_factory=list)
    dependencies: set[str] = field(default_factory=set)
    expected_artifacts: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: str | None = None
    error: str | None = None

    def can_execute(self, completed_steps: set[str]) -> bool:
        """Check if this step can be executed based on its dependencies."""
        return self.dependencies.issubset(completed_steps)

    def mark_running(self) -> None:
        """Mark step as running."""
        self.status = StepStatus.RUNNING

    def mark_completed(self, result: str) -> None:
        """Mark step as completed with result."""
        self.status = StepStatus.COMPLETED
        self.result = result

    def mark_failed(self, error: str) -> None:
        """Mark step as failed with error."""
        self.status = StepStatus.FAILED
        self.error = error

    def mark_skipped(self) -> None:
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED


@dataclass
class ExecutionPlan:
    """A plan containing multiple steps with dependencies."""

    id: str
    name: str
    description: str
    steps: list[ExecutionStep] = field(default_factory=list)
    global_context: dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: ExecutionStep) -> None:
        """Add a step to the execution plan."""
        self.steps.append(step)

    def get_step(self, step_id: str) -> ExecutionStep | None:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_ready_steps(self) -> list[ExecutionStep]:
        """Get steps that are ready to execute."""
        completed_steps = {step.id for step in self.steps if step.status == StepStatus.COMPLETED}
        return [
            step for step in self.steps
            if step.status == StepStatus.PENDING and step.can_execute(completed_steps)
        ]

    def get_completed_steps(self) -> list[ExecutionStep]:
        """Get all completed steps."""
        return [step for step in self.steps if step.status == StepStatus.COMPLETED]

    def get_failed_steps(self) -> list[ExecutionStep]:
        """Get all failed steps."""
        return [step for step in self.steps if step.status == StepStatus.FAILED]

    def is_complete(self) -> bool:
        """Check if all steps are completed or skipped."""
        return all(
            step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]
            for step in self.steps
        )

    def has_failures(self) -> bool:
        """Check if any steps have failed."""
        return any(step.status == StepStatus.FAILED for step in self.steps)


@dataclass
class ExecutionResult:
    """Result of executing a step or plan."""

    success: bool
    message: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    token_usage: int | None = None
    execution_time: float | None = None

    @classmethod
    def success_result(
        cls,
        message: str,
        artifacts: dict[str, Any] | None = None,
        token_usage: int | None = None,
        execution_time: float | None = None,
    ) -> ExecutionResult:
        """Create a success result."""
        return cls(
            success=True,
            message=message,
            artifacts=artifacts or {},
            token_usage=token_usage,
            execution_time=execution_time,
        )

    @classmethod
    def failure_result(
        cls,
        message: str,
        artifacts: dict[str, Any] | None = None,
        token_usage: int | None = None,
        execution_time: float | None = None,
    ) -> ExecutionResult:
        """Create a failure result."""
        return cls(
            success=False,
            message=message,
            artifacts=artifacts or {},
            token_usage=token_usage,
            execution_time=execution_time,
        )
