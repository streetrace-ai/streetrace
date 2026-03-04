"""Basic Python test agent for workload abstraction testing."""

from typing import override

from a2a.types import AgentCapabilities, AgentSkill
from google.adk.agents import Agent, BaseAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool, ToolProvider


class BasicPythonAgent(StreetRaceAgent):
    """Basic Python test agent."""

    @override
    def get_agent_card(self) -> StreetRaceAgentCard:
        """Return the agent card."""
        skill = AgentSkill(
            id="test",
            name="Test",
            description="Test skill for workload abstraction testing",
            tags=["test"],
            examples=["Hello"],
        )

        return StreetRaceAgentCard(
            name="basic_python_agent",
            description="Basic Python test agent for workload abstraction testing",
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
        )

    @override
    async def get_required_tools(self) -> list[AnyTool]:
        """Return empty list - no tools needed for test."""
        return []

    @override
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create the agent."""
        agent_card = self.get_agent_card()
        return Agent(
            name=agent_card.name,
            model=model_factory.get_current_model(),
            description=agent_card.description,
            instruction="You are a test assistant. Respond briefly with: Python agent responding.",
            tools=[],
            sub_agents=[],
        )
