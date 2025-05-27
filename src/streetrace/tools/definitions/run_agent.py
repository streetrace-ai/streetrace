"""run_agent tool implementation.

Executes a specified agent with input and returns the result.
"""

from pathlib import Path
from typing import Optional

from google.adk import Runner
from google.genai import types as genai_types

from streetrace.agents.agent_manager import AgentManager
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.tools.definitions.result import OpResult, OpResultCode

logger = get_logger(__name__)


class RunAgentResult(OpResult):
    """Result from running an agent."""

    output: str | None  # type: ignore[misc]


class RunAgentContext:
    """Context for running agents that maintains singleton instances."""

    _instance: Optional["RunAgentContext"] = None

    def __init__(self) -> None:
        """Initialize RunAgentContext."""
        self.agent_manager: AgentManager | None = None
        self.model_factory: ModelFactory | None = None

    @classmethod
    def get_instance(cls) -> "RunAgentContext":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = RunAgentContext()
        return cls._instance

    def initialize(
        self,
        agent_manager: AgentManager,
        model_factory: ModelFactory,
    ) -> None:
        """Initialize the context with required components.
        
        Args:
            agent_manager: Agent manager instance
            model_factory: Model factory instance

        """
        self.agent_manager = agent_manager
        self.model_factory = model_factory


async def run_agent(
    work_dir: Path,
    agent_name: str,
    input_text: str,
    model_name: str = "default",
) -> RunAgentResult:
    """Run a specified agent with the provided input.
    
    Args:
        work_dir: Current working directory
        agent_name: Name of the agent to run
        input_text: Input text to send to the agent
        model_name: Name of the model to use (default: "default")
        
    Returns:
        RunAgentResult containing the agent's response
        
    Note:
        This tool requires RunAgentContext to be initialized with an AgentManager
        and ModelFactory before it can be used.

    """
    context = RunAgentContext.get_instance()

    if not context.agent_manager or not context.model_factory:
        error_message = "RunAgentContext not properly initialized. Unable to run agent."
        logger.error(error_message)
        return RunAgentResult(
            tool_name="run_agent",
            result=OpResultCode.FAILURE,
            output=None,
            error=error_message,
        )

    try:
        # Create content from input text
        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=input_text)],
        )

        # Create the agent
        async with context.agent_manager.create_agent(agent_name, model_name) as agent:
            # Create a runner for the agent
            runner = Runner(
                app_name="StreetRace",
                agent=agent,
            )

            # Collect all responses
            final_response = "Agent did not produce a final response."
            async for event in runner.run_async(
                user_id="user",
                session_id="temp_session",
                new_message=content,
            ):
                # Check if this is the final response
                if event.is_final_response():
                    if event.content and event.content.parts:
                        final_response = event.content.parts[0].text
                    elif event.actions and event.actions.escalate:
                        error_msg = event.error_message or "No specific message."
                        final_response = f"Agent escalated: {error_msg}"
                    break

            return RunAgentResult(
                tool_name="run_agent",
                result=OpResultCode.SUCCESS,
                output=final_response,
                error=None,
            )

    except Exception as ex:
        error_message = f"Failed to run agent '{agent_name}': {ex}"
        logger.exception(error_message)
        return RunAgentResult(
            tool_name="run_agent",
            result=OpResultCode.FAILURE,
            output=None,
            error=error_message,
        )
