"""Tests for step executor models."""


from streetrace.agents.step_executor.models import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionStep,
    StepContext,
    StepStatus,
    StepType,
)


class TestStepContext:
    """Test StepContext functionality."""

    def test_init(self) -> None:
        """Test StepContext initialization."""
        context = StepContext(
            step_id="test_step",
            step_type=StepType.ANALYZE,
            goal="Test goal",
        )

        assert context.step_id == "test_step"
        assert context.step_type == StepType.ANALYZE
        assert context.goal == "Test goal"
        assert context.relevant_files == []
        assert context.dependencies == set()
        assert context.artifacts == {}

    def test_add_artifact(self) -> None:
        """Test adding artifacts to context."""
        context = StepContext(
            step_id="test",
            step_type=StepType.ANALYZE,
            goal="test",
        )

        context.add_artifact("key1", "value1")
        assert context.get_artifact("key1") == "value1"
        assert context.has_artifact("key1")

    def test_get_missing_artifact(self) -> None:
        """Test getting missing artifact."""
        context = StepContext(
            step_id="test",
            step_type=StepType.ANALYZE,
            goal="test",
        )

        assert context.get_artifact("missing") is None
        assert not context.has_artifact("missing")


class TestExecutionStep:
    """Test ExecutionStep functionality."""

    def test_init(self) -> None:
        """Test ExecutionStep initialization."""
        step = ExecutionStep(
            id="step1",
            name="Test Step",
            description="A test step",
            step_type=StepType.GENERATE,
            goal="Generate test code",
        )

        assert step.id == "step1"
        assert step.name == "Test Step"
        assert step.status == StepStatus.PENDING
        assert step.result is None
        assert step.error is None

    def test_can_execute_no_dependencies(self) -> None:
        """Test can_execute with no dependencies."""
        step = ExecutionStep(
            id="step1",
            name="Test",
            description="Test",
            step_type=StepType.ANALYZE,
            goal="Test",
        )

        assert step.can_execute(set())
        assert step.can_execute({"other_step"})

    def test_can_execute_with_dependencies(self) -> None:
        """Test can_execute with dependencies."""
        step = ExecutionStep(
            id="step1",
            name="Test",
            description="Test",
            step_type=StepType.ANALYZE,
            goal="Test",
            dependencies={"dep1", "dep2"},
        )

        assert not step.can_execute(set())
        assert not step.can_execute({"dep1"})
        assert step.can_execute({"dep1", "dep2"})
        assert step.can_execute({"dep1", "dep2", "extra"})

    def test_mark_running(self) -> None:
        """Test marking step as running."""
        step = ExecutionStep(
            id="step1",
            name="Test",
            description="Test",
            step_type=StepType.ANALYZE,
            goal="Test",
        )

        step.mark_running()
        assert step.status == StepStatus.RUNNING

    def test_mark_completed(self) -> None:
        """Test marking step as completed."""
        step = ExecutionStep(
            id="step1",
            name="Test",
            description="Test",
            step_type=StepType.ANALYZE,
            goal="Test",
        )

        step.mark_completed("Success result")
        assert step.status == StepStatus.COMPLETED
        assert step.result == "Success result"

    def test_mark_failed(self) -> None:
        """Test marking step as failed."""
        step = ExecutionStep(
            id="step1",
            name="Test",
            description="Test",
            step_type=StepType.ANALYZE,
            goal="Test",
        )

        step.mark_failed("Error message")
        assert step.status == StepStatus.FAILED
        assert step.error == "Error message"


class TestExecutionPlan:
    """Test ExecutionPlan functionality."""

    def test_init(self) -> None:
        """Test ExecutionPlan initialization."""
        plan = ExecutionPlan(
            id="plan1",
            name="Test Plan",
            description="A test plan",
        )

        assert plan.id == "plan1"
        assert plan.name == "Test Plan"
        assert plan.description == "A test plan"
        assert plan.steps == []

    def test_add_step(self) -> None:
        """Test adding steps to plan."""
        plan = ExecutionPlan(
            id="plan1",
            name="Test Plan",
            description="A test plan",
        )

        step = ExecutionStep(
            id="step1",
            name="Test",
            description="Test",
            step_type=StepType.ANALYZE,
            goal="Test",
        )

        plan.add_step(step)
        assert len(plan.steps) == 1
        assert plan.steps[0] == step

    def test_get_step(self) -> None:
        """Test getting step by ID."""
        plan = ExecutionPlan(
            id="plan1",
            name="Test Plan",
            description="A test plan",
        )

        step = ExecutionStep(
            id="step1",
            name="Test",
            description="Test",
            step_type=StepType.ANALYZE,
            goal="Test",
        )

        plan.add_step(step)

        assert plan.get_step("step1") == step
        assert plan.get_step("missing") is None

    def test_get_ready_steps(self) -> None:
        """Test getting ready steps."""
        plan = ExecutionPlan(
            id="plan1",
            name="Test Plan",
            description="A test plan",
        )

        step1 = ExecutionStep(
            id="step1",
            name="Test1",
            description="Test1",
            step_type=StepType.ANALYZE,
            goal="Test1",
        )

        step2 = ExecutionStep(
            id="step2",
            name="Test2",
            description="Test2",
            step_type=StepType.GENERATE,
            goal="Test2",
            dependencies={"step1"},
        )

        plan.add_step(step1)
        plan.add_step(step2)

        # Initially only step1 is ready
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0] == step1

        # After step1 completes, step2 becomes ready
        step1.mark_completed("Done")
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0] == step2

    def test_is_complete(self) -> None:
        """Test checking if plan is complete."""
        plan = ExecutionPlan(
            id="plan1",
            name="Test Plan",
            description="A test plan",
        )

        step1 = ExecutionStep(
            id="step1",
            name="Test1",
            description="Test1",
            step_type=StepType.ANALYZE,
            goal="Test1",
        )

        step2 = ExecutionStep(
            id="step2",
            name="Test2",
            description="Test2",
            step_type=StepType.GENERATE,
            goal="Test2",
        )

        plan.add_step(step1)
        plan.add_step(step2)

        assert not plan.is_complete()

        step1.mark_completed("Done")
        assert not plan.is_complete()

        step2.mark_completed("Done")
        assert plan.is_complete()

    def test_has_failures(self) -> None:
        """Test checking if plan has failures."""
        plan = ExecutionPlan(
            id="plan1",
            name="Test Plan",
            description="A test plan",
        )

        step1 = ExecutionStep(
            id="step1",
            name="Test1",
            description="Test1",
            step_type=StepType.ANALYZE,
            goal="Test1",
        )

        plan.add_step(step1)

        assert not plan.has_failures()

        step1.mark_failed("Error")
        assert plan.has_failures()


class TestExecutionResult:
    """Test ExecutionResult functionality."""

    def test_success_result(self) -> None:
        """Test creating success result."""
        result = ExecutionResult.success_result(
            message="Success",
            artifacts={"key": "value"},
            token_usage=100,
            execution_time=1.5,
        )

        assert result.success
        assert result.message == "Success"
        assert result.artifacts == {"key": "value"}
        assert result.token_usage == 100
        assert result.execution_time == 1.5

    def test_failure_result(self) -> None:
        """Test creating failure result."""
        result = ExecutionResult.failure_result(
            message="Failed",
            artifacts={"error": "details"},
            token_usage=50,
            execution_time=0.5,
        )

        assert not result.success
        assert result.message == "Failed"
        assert result.artifacts == {"error": "details"}
        assert result.token_usage == 50
        assert result.execution_time == 0.5

    def test_success_result_defaults(self) -> None:
        """Test success result with defaults."""
        result = ExecutionResult.success_result("Success")

        assert result.success
        assert result.message == "Success"
        assert result.artifacts == {}
        assert result.token_usage is None
        assert result.execution_time is None
