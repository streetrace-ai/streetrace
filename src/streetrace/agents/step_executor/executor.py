"""Step executor implementation for running individual steps."""

from __future__ import annotations

import time
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.sessions import Session

from streetrace.agents.step_executor.models import (
    ExecutionResult,
    ExecutionStep,
    StepContext,
    StepType,
)
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.tools.tool_provider import AnyTool

logger = get_logger(__name__)


class StepExecutor:
    """Executes individual steps with minimal context."""

    def __init__(
        self,
        agent: BaseAgent,
        session: Session,
        model_factory: ModelFactory,
        tools: list[AnyTool],
    ) -> None:
        """Initialize the step executor.
        
        Args:
            agent: The ADK agent to use for execution
            session: The session to use for execution
            model_factory: Factory for creating models
            tools: Available tools for the agent

        """
        self.agent = agent
        self.session = session
        self.model_factory = model_factory
        self.tools = tools

    async def execute_step(
        self,
        step: ExecutionStep,
        context: StepContext,
        global_artifacts: dict[str, Any],
    ) -> ExecutionResult:
        """Execute a single step with minimal context.
        
        Args:
            step: The step to execute
            context: The step context
            global_artifacts: Artifacts from previous steps
            
        Returns:
            ExecutionResult with success/failure and artifacts

        """
        logger.info(f"Executing step: {step.name} ({step.id})")
        step.mark_running()

        start_time = time.time()

        try:
            # Build minimal prompt for this step
            prompt = self._build_step_prompt(step, context, global_artifacts)

            # Execute the step
            result = await self._execute_with_agent(prompt)

            # Extract artifacts from the result
            artifacts = self._extract_artifacts(result, step.expected_artifacts)

            # Mark step as completed
            step.mark_completed(result)

            execution_time = time.time() - start_time

            logger.info(f"Step {step.id} completed in {execution_time:.2f}s")

            return ExecutionResult.success_result(
                message=result,
                artifacts=artifacts,
                execution_time=execution_time,
            )

        except Exception as e:
            error_msg = f"Step {step.id} failed: {e!s}"
            logger.error(error_msg)
            step.mark_failed(error_msg)

            execution_time = time.time() - start_time

            return ExecutionResult.failure_result(
                message=error_msg,
                execution_time=execution_time,
            )

    def _build_step_prompt(
        self,
        step: ExecutionStep,
        context: StepContext,
        global_artifacts: dict[str, Any],
    ) -> str:
        """Build a minimal prompt for the step.
        
        Args:
            step: The step to execute
            context: The step context
            global_artifacts: Artifacts from previous steps
            
        Returns:
            Formatted prompt string

        """
        prompt_parts = [
            f"STEP: {step.name}",
            f"GOAL: {step.goal}",
            f"DESCRIPTION: {step.description}",
            f"TYPE: {step.step_type.value}",
        ]

        # Add relevant files if any
        if step.relevant_files:
            prompt_parts.append(f"RELEVANT FILES: {', '.join(step.relevant_files)}")

        # Add dependency artifacts
        if step.dependencies:
            dependency_artifacts = []
            for dep_id in step.dependencies:
                if dep_id in global_artifacts:
                    artifact = global_artifacts[dep_id]
                    if isinstance(artifact, dict):
                        dependency_artifacts.append(f"{dep_id}: {artifact}")
                    else:
                        dependency_artifacts.append(f"{dep_id}: {artifact!s}")

            if dependency_artifacts:
                prompt_parts.append("DEPENDENCY ARTIFACTS:")
                prompt_parts.extend(dependency_artifacts)

        # Add step-specific context
        if context.artifacts:
            prompt_parts.append("CONTEXT ARTIFACTS:")
            for key, value in context.artifacts.items():
                prompt_parts.append(f"{key}: {value}")

        # Add expected artifacts
        if step.expected_artifacts:
            prompt_parts.append(f"EXPECTED ARTIFACTS: {', '.join(step.expected_artifacts)}")

        # Add step-specific instructions based on type
        prompt_parts.append(self._get_step_instructions(step.step_type))

        return "\n\n".join(prompt_parts)

    def _get_step_instructions(self, step_type: StepType) -> str:
        """Get type-specific instructions for the step.
        
        Args:
            step_type: The type of step
            
        Returns:
            Instructions for the step type

        """
        instructions = {
            StepType.ANALYZE: """
INSTRUCTIONS:
- Analyze the relevant files and context
- Identify key patterns, structures, and requirements
- Provide clear findings and recommendations
- Focus on essential information only
- Output should be concise and actionable
""",
            StepType.GENERATE: """
INSTRUCTIONS:
- Generate code based on the analysis and requirements
- Follow best practices and existing code patterns
- Ensure generated code is complete and functional
- Include necessary imports and error handling
- Focus on the specific functionality required
""",
            StepType.MODIFY: """
INSTRUCTIONS:
- Modify existing code based on requirements
- Preserve existing functionality where possible
- Make minimal, targeted changes
- Ensure modifications are compatible with existing code
- Test changes if possible
""",
            StepType.VALIDATE: """
INSTRUCTIONS:
- Validate the code or artifacts from previous steps
- Check for correctness, completeness, and quality
- Identify any issues or improvements needed
- Provide specific feedback and recommendations
- Focus on critical issues first
""",
            StepType.CLEANUP: """
INSTRUCTIONS:
- Clean up code and artifacts
- Remove unnecessary files or code
- Optimize and refactor where beneficial
- Ensure consistency and maintainability
- Document any changes made
""",
        }

        return instructions.get(step_type, "Execute the step according to its description.")

    async def _execute_with_agent(self, prompt: str) -> str:
        """Execute the prompt with the agent.
        
        Args:
            prompt: The prompt to execute
            
        Returns:
            The agent's response

        """
        # Create a new session context for this step
        # This ensures minimal context is used
        response = await self.session.run(prompt)

        # Extract text content from the response
        if hasattr(response, "content"):
            return response.content
        return str(response)

    def _extract_artifacts(
        self,
        result: str,
        expected_artifacts: list[str],
    ) -> dict[str, Any]:
        """Extract artifacts from the step result.
        
        Args:
            result: The step result
            expected_artifacts: List of expected artifact names
            
        Returns:
            Dictionary of extracted artifacts

        """
        artifacts = {}

        # For now, we'll store the full result as the main artifact
        # In a more sophisticated implementation, we could parse
        # specific artifacts from the result based on expected_artifacts
        artifacts["result"] = result

        # Try to extract code blocks
        code_blocks = self._extract_code_blocks(result)
        if code_blocks:
            artifacts["code_blocks"] = code_blocks

        # Try to extract file paths
        file_paths = self._extract_file_paths(result)
        if file_paths:
            artifacts["file_paths"] = file_paths

        return artifacts

    def _extract_code_blocks(self, text: str) -> list[dict[str, str]]:
        """Extract code blocks from text.
        
        Args:
            text: The text to extract from
            
        Returns:
            List of code blocks with language and content

        """
        import re

        code_blocks = []
        pattern = r"```(\w+)?\n(.*?)```"
        matches = re.finditer(pattern, text, re.DOTALL)

        for match in matches:
            language = match.group(1) or "text"
            content = match.group(2).strip()
            code_blocks.append({
                "language": language,
                "content": content,
            })

        return code_blocks

    def _extract_file_paths(self, text: str) -> list[str]:
        """Extract file paths from text.
        
        Args:
            text: The text to extract from
            
        Returns:
            List of file paths

        """
        import re

        # Look for common file path patterns
        patterns = [
            r"(?:^|\s)([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*\.py)(?:\s|$)",
            r"(?:^|\s)([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*\.js)(?:\s|$)",
            r"(?:^|\s)([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*\.ts)(?:\s|$)",
            r"(?:^|\s)([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*\.json)(?:\s|$)",
            r"(?:^|\s)([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*\.md)(?:\s|$)",
        ]

        file_paths = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                file_paths.append(match.group(1))

        return list(set(file_paths))  # Remove duplicates
