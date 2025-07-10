"""Orchestrator for managing execution plans and step coordination."""

from __future__ import annotations

import time
from typing import Any

from google.adk.agents import Agent, BaseAgent

from streetrace.agents.step_executor.executor import StepExecutor
from streetrace.agents.step_executor.models import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionStep,
    StepContext,
    StepType,
)
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool

logger = get_logger(__name__)


class PlanGenerator:
    """Generates execution plans from high-level requirements."""

    def __init__(self, model_factory: ModelFactory, system_context: SystemContext) -> None:
        """Initialize the plan generator.
        
        Args:
            model_factory: Factory for creating models
            system_context: System context for the agent

        """
        self.model_factory = model_factory
        self.system_context = system_context

    async def generate_plan(self, requirements: str, context: dict[str, Any]) -> ExecutionPlan:
        """Generate an execution plan from requirements.
        
        Args:
            requirements: High-level requirements description
            context: Additional context for plan generation
            
        Returns:
            Generated execution plan

        """
        logger.info("Generating execution plan from requirements")

        # Create a planning agent
        model = self.model_factory.get_current_model()
        planning_agent = Agent(
            name="PlanGenerator",
            model=model,
            description="Generates step-based execution plans",
            global_instruction=self.system_context.get_system_message(),
            instruction=self._get_planning_instruction(),
            tools=[],  # Planning doesn't need tools
        )

        # Generate the plan
        session = planning_agent.create_session()
        prompt = self._build_planning_prompt(requirements, context)

        response = await session.run(prompt)

        # Parse the response into an execution plan
        plan = self._parse_plan_response(response.content if hasattr(response, "content") else str(response))

        logger.info(f"Generated plan with {len(plan.steps)} steps")
        return plan

    def _get_planning_instruction(self) -> str:
        """Get instructions for the planning agent."""
        return """You are a planning agent that breaks down complex software development tasks into step-based execution plans.

Your goal is to create efficient execution plans that minimize token usage by:
1. Breaking tasks into atomic, focused steps
2. Identifying minimal context needed for each step
3. Establishing clear dependencies between steps
4. Defining expected artifacts for each step

For each step, specify:
- A unique ID and descriptive name
- Clear goal and description
- Step type (analyze, generate, modify, validate, cleanup)
- Relevant files (only those needed for this specific step)
- Dependencies on other steps
- Expected artifacts to be produced

Focus on creating steps that can be executed independently with minimal context.
Avoid sending full chat history - each step should have only the context it needs.

Output your plan in the following format:

PLAN: [Plan Name]
DESCRIPTION: [Plan Description]

STEP: [step_id]
NAME: [Step Name]
TYPE: [analyze|generate|modify|validate|cleanup]
GOAL: [Specific goal for this step]
DESCRIPTION: [Detailed description]
FILES: [file1.py, file2.py, ...]
DEPENDENCIES: [step1_id, step2_id, ...]
ARTIFACTS: [artifact1, artifact2, ...]

[Repeat for each step]

END_PLAN"""

    def _build_planning_prompt(self, requirements: str, context: dict[str, Any]) -> str:
        """Build the planning prompt.
        
        Args:
            requirements: Requirements to plan for
            context: Additional context
            
        Returns:
            Formatted planning prompt

        """
        prompt_parts = [
            "TASK: Generate a step-based execution plan",
            f"REQUIREMENTS: {requirements}",
        ]

        # Add context information
        if context:
            prompt_parts.append("CONTEXT:")
            for key, value in context.items():
                prompt_parts.append(f"- {key}: {value}")

        prompt_parts.append("""
INSTRUCTIONS:
1. Break down the requirements into atomic steps
2. Each step should be focused on a single task
3. Minimize context and dependencies between steps
4. Identify the most efficient execution order
5. Specify only the files and context needed for each step
6. Define clear artifacts that each step should produce

Remember: The goal is to reduce token usage by avoiding full chat history in each step.
Each step should be executable with minimal, targeted context.""")

        return "\n\n".join(prompt_parts)

    def _parse_plan_response(self, response: str) -> ExecutionPlan:
        """Parse the planning response into an ExecutionPlan.
        
        Args:
            response: Response from the planning agent
            
        Returns:
            Parsed execution plan

        """
        lines = response.strip().split("\n")
        plan = None
        current_step = None

        for line in lines:
            line = line.strip()

            if line.startswith("PLAN:"):
                plan_name = line[5:].strip()
                plan = ExecutionPlan(
                    id=f"plan_{int(time.time())}",
                    name=plan_name,
                    description="",
                )

            elif line.startswith("DESCRIPTION:") and plan:
                plan.description = line[12:].strip()

            elif line.startswith("STEP:"):
                if current_step and plan:
                    plan.add_step(current_step)

                step_id = line[5:].strip()
                current_step = ExecutionStep(
                    id=step_id,
                    name="",
                    description="",
                    step_type=StepType.ANALYZE,
                    goal="",
                )

            elif line.startswith("NAME:") and current_step:
                current_step.name = line[5:].strip()

            elif line.startswith("TYPE:") and current_step:
                step_type_str = line[5:].strip().lower()
                try:
                    current_step.step_type = StepType(step_type_str)
                except ValueError:
                    current_step.step_type = StepType.ANALYZE

            elif line.startswith("GOAL:") and current_step:
                current_step.goal = line[5:].strip()

            elif line.startswith("DESCRIPTION:") and current_step:
                current_step.description = line[12:].strip()

            elif line.startswith("FILES:") and current_step:
                files_str = line[6:].strip()
                if files_str:
                    current_step.relevant_files = [f.strip() for f in files_str.split(",")]

            elif line.startswith("DEPENDENCIES:") and current_step:
                deps_str = line[13:].strip()
                if deps_str:
                    current_step.dependencies = set(d.strip() for d in deps_str.split(","))

            elif line.startswith("ARTIFACTS:") and current_step:
                artifacts_str = line[10:].strip()
                if artifacts_str:
                    current_step.expected_artifacts = [a.strip() for a in artifacts_str.split(",")]

            elif line == "END_PLAN":
                if current_step and plan:
                    plan.add_step(current_step)
                break

        # Add the last step if not added
        if current_step and plan:
            plan.add_step(current_step)

        # If parsing failed, create a simple fallback plan
        if not plan:
            plan = ExecutionPlan(
                id=f"fallback_plan_{int(time.time())}",
                name="Fallback Plan",
                description="Auto-generated fallback plan",
            )
            plan.add_step(ExecutionStep(
                id="step_1",
                name="Execute Requirements",
                description="Execute the given requirements",
                step_type=StepType.GENERATE,
                goal="Complete the requested task",
            ))

        return plan


class Orchestrator:
    """Orchestrates the execution of step-based plans."""

    def __init__(
        self,
        model_factory: ModelFactory,
        system_context: SystemContext,
        tools: list[AnyTool],
    ) -> None:
        """Initialize the orchestrator.
        
        Args:
            model_factory: Factory for creating models
            system_context: System context for agents
            tools: Available tools for step execution

        """
        self.model_factory = model_factory
        self.system_context = system_context
        self.tools = tools
        self.plan_generator = PlanGenerator(model_factory, system_context)

    async def execute_requirements(
        self,
        requirements: str,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Execute requirements using step-based approach.
        
        Args:
            requirements: High-level requirements to execute
            context: Additional context for execution
            
        Returns:
            ExecutionResult with overall success/failure

        """
        logger.info("Starting step-based execution")
        context = context or {}

        try:
            # Generate execution plan
            plan = await self.plan_generator.generate_plan(requirements, context)

            # Execute the plan
            result = await self.execute_plan(plan)

            return result

        except Exception as e:
            error_msg = f"Failed to execute requirements: {e!s}"
            logger.error(error_msg)
            return ExecutionResult.failure_result(error_msg)

    async def execute_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        """Execute a complete execution plan.
        
        Args:
            plan: The execution plan to run
            
        Returns:
            ExecutionResult with overall success/failure

        """
        logger.info(f"Executing plan: {plan.name} with {len(plan.steps)} steps")

        start_time = time.time()
        global_artifacts: dict[str, Any] = {}
        total_token_usage = 0

        # Create execution agent
        agent = await self._create_execution_agent()
        session = agent.create_session()
        step_executor = StepExecutor(agent, session, self.model_factory, self.tools)

        try:
            while not plan.is_complete() and not plan.has_failures():
                # Get ready steps
                ready_steps = plan.get_ready_steps()

                if not ready_steps:
                    if not plan.is_complete():
                        # Deadlock - no ready steps but plan not complete
                        failed_msg = "Execution deadlock: no ready steps available"
                        logger.error(failed_msg)
                        return ExecutionResult.failure_result(failed_msg)
                    break

                # Execute ready steps (could be parallelized in the future)
                for step in ready_steps:
                    context = StepContext(
                        step_id=step.id,
                        step_type=step.step_type,
                        goal=step.goal,
                        relevant_files=step.relevant_files,
                        dependencies=step.dependencies,
                    )

                    # Execute the step
                    step_result = await step_executor.execute_step(
                        step, context, global_artifacts,
                    )

                    # Collect artifacts
                    if step_result.success:
                        global_artifacts[step.id] = step_result.artifacts
                        if step_result.token_usage:
                            total_token_usage += step_result.token_usage
                    else:
                        # Step failed - mark it and continue
                        logger.warning(f"Step {step.id} failed: {step_result.message}")

            execution_time = time.time() - start_time

            if plan.has_failures():
                failed_steps = plan.get_failed_steps()
                failure_msg = f"Plan execution failed. Failed steps: {[s.id for s in failed_steps]}"
                return ExecutionResult.failure_result(
                    message=failure_msg,
                    artifacts=global_artifacts,
                    token_usage=total_token_usage,
                    execution_time=execution_time,
                )

            completed_steps = plan.get_completed_steps()
            success_msg = f"Plan execution completed. Completed {len(completed_steps)} steps."

            return ExecutionResult.success_result(
                message=success_msg,
                artifacts=global_artifacts,
                token_usage=total_token_usage,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Plan execution error: {e!s}"
            logger.error(error_msg)

            return ExecutionResult.failure_result(
                message=error_msg,
                artifacts=global_artifacts,
                token_usage=total_token_usage,
                execution_time=execution_time,
            )

    async def _create_execution_agent(self) -> BaseAgent:
        """Create an agent for step execution.
        
        Returns:
            Configured agent for step execution

        """
        model = self.model_factory.get_current_model()

        return Agent(
            name="StepExecutor",
            model=model,
            description="Executes individual steps with minimal context",
            global_instruction=self.system_context.get_system_message(),
            instruction="""You are a step executor that performs focused, atomic tasks.

You receive:
- A specific goal and description for the current step
- Minimal, relevant context (no full chat history)
- Dependencies and artifacts from previous steps
- List of relevant files for this step only

Your responsibilities:
- Focus only on the current step's goal
- Use only the provided context and dependencies
- Produce the expected artifacts for this step
- Be efficient and avoid unnecessary work
- Provide clear, actionable output

Key principles:
- Work with minimal context to reduce token usage
- Focus on the specific task at hand
- Produce clear, usable artifacts
- Avoid assumptions beyond the provided context
- Be precise and efficient in your responses""",
            tools=self.tools,
        )
