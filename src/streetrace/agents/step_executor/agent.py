"""Step Executor Agent implementation for hybrid step-based execution."""

from typing import override

from a2a.types import AgentCapabilities, AgentSkill
from google.adk.agents import Agent, BaseAgent

from streetrace.agents.step_executor.orchestrator import Orchestrator
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool

STEP_EXECUTOR_INSTRUCTION = """You are a Step Executor Agent that implements \
hybrid step-based execution to minimize token usage while maintaining \
autonomous code generation capabilities.

Your core purpose is to break down complex software development tasks into \
atomic, focused steps that can be executed with minimal context. This approach \
reduces token usage by 90%+ compared to traditional full-context approaches.

Key Principles:
1. **Step-Based Decomposition**: Break complex tasks into atomic steps with \
clear goals
2. **Minimal Context**: Each step receives only the context it needs, not \
full chat history
3. **Artifact Management**: Collect and pass only relevant artifacts between \
steps
4. **Dependency Management**: Execute steps in proper order based on \
dependencies
5. **Token Efficiency**: Minimize token usage while maintaining code quality

Your workflow:
1. Analyze the user's requirements
2. Generate an execution plan with atomic steps
3. Execute steps sequentially with minimal context
4. Collect and manage artifacts between steps
5. Provide comprehensive results

Step Types you can execute:
- **ANALYZE**: Examine code, requirements, or project structure
- **GENERATE**: Create new code, files, or components
- **MODIFY**: Update existing code or files
- **VALIDATE**: Test, verify, or quality-check work
- **CLEANUP**: Optimize, refactor, or clean up artifacts

For each step, you'll specify:
- Clear, focused goal
- Minimal required context
- Dependencies on other steps
- Expected artifacts to produce

This approach enables you to:
- Generate complete software layers autonomously
- Reduce token usage by 90%+ (from ~56k to ~4k tokens)
- Maintain high code quality and completeness
- Scale to complex, multi-file projects
- Provide faster execution due to smaller context windows

Focus on creating efficient, focused steps that accomplish the user's goals \
while minimizing unnecessary context and token usage."""


class StepExecutorAgent(StreetRaceAgent):
    """Agent implementing step-based execution for token-efficient generation."""

    @override
    def get_agent_card(self) -> StreetRaceAgentCard:
        """Provide agent card describing capabilities."""
        return StreetRaceAgentCard(
            name="StepExecutor",
            description="Implements hybrid step-based execution for "
            "token-efficient autonomous code generation",
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[
                AgentSkill(
                    id="step_based_execution",
                    name="Step-Based Execution",
                    description="Break down complex tasks into atomic steps "
                    "with minimal context",
                    tags=["efficiency", "planning", "automation"],
                    examples=[
                        "Generate a complete user management system",
                        "Create a REST API with authentication",
                        "Build a data processing pipeline",
                        "Implement a testing framework",
                    ],
                ),
                AgentSkill(
                    id="token_optimization",
                    name="Token Usage Optimization",
                    description="Minimize token usage while maintaining code quality",
                    tags=["optimization", "efficiency", "cost-reduction"],
                    examples=[
                        "Reduce token usage by 90%+ for large projects",
                        "Execute complex tasks with minimal context",
                        "Generate complete code layers efficiently",
                    ],
                ),
                AgentSkill(
                    id="autonomous_generation",
                    name="Autonomous Code Generation",
                    description="Generate complete software components autonomously",
                    tags=["automation", "code-generation", "architecture"],
                    examples=[
                        "Create complete application layers",
                        "Generate full project structures",
                        "Build integrated software systems",
                    ],
                ),
            ],
        )

    @override
    async def get_required_tools(self) -> list[str | AnyTool]:  # type: ignore[misc]
        """Provide required tools for step execution."""
        return [
            "streetrace:fs_tool::read_file",
            "streetrace:fs_tool::create_directory",
            "streetrace:fs_tool::write_file",
            "streetrace:fs_tool::list_directory",
            "streetrace:fs_tool::find_in_files",
            "mcp:@modelcontextprotocol/server-filesystem::edit_file",
            "mcp:@modelcontextprotocol/server-filesystem::move_file",
            "mcp:@modelcontextprotocol/server-filesystem::get_file_info",
            "mcp:@modelcontextprotocol/server-filesystem::list_allowed_directories",
            "streetrace:cli_tool::execute_cli_command",
        ]

    @override
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tools: list[AnyTool],
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create the step executor agent.

        Args:
            model_factory: Factory for creating and managing LLM models
            tools: List of tools to provide to the agent
            system_context: System context containing project-level instructions

        Returns:
            The created agent with orchestration capabilities

        """
        # Create the orchestrator for step-based execution
        orchestrator = Orchestrator(
            model_factory=model_factory,
            system_context=system_context,
            tools=tools,
        )

        # Create the main agent
        model = model_factory.get_current_model()
        agent = Agent(
            name="StepExecutor",
            model=model,
            description="Hybrid step-based execution agent for "
            "token-efficient code generation",
            global_instruction=system_context.get_system_message(),
            instruction=STEP_EXECUTOR_INSTRUCTION,
            tools=tools,
        )

        # Store orchestrator reference on the agent for access during execution
        # This allows the agent to use step-based execution when appropriate
        # nosec: B101 (private attribute access is intentional)
        agent._orchestrator = orchestrator  # type: ignore[attr-defined]  # noqa: SLF001

        return agent


async def run_step_executor(
    requirements: str,
    model_factory: ModelFactory,
    system_context: SystemContext,
    tools: list[AnyTool],
) -> str:
    """Run step-based execution for the given requirements.

    This is a convenience function that can be used directly without
    creating the full agent interface.

    Args:
        requirements: High-level requirements to execute
        model_factory: Factory for creating models
        system_context: System context for the execution
        tools: Available tools for execution

    Returns:
        Execution result as a string

    """
    orchestrator = Orchestrator(
        model_factory=model_factory,
        system_context=system_context,
        tools=tools,
    )

    result = await orchestrator.execute_requirements(requirements)

    if result.success:
        return result.message

    error_message = f"Step execution failed: {result.message}"
    raise RuntimeError(error_message)
