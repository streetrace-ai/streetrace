"""Hello World Agent implementation.

A simple example agent that demonstrates the basic structure of a StreetRace agent.
"""

from typing import override

from a2a.types import AgentCapabilities, AgentSkill
from google.adk.agents import Agent, BaseAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.messages import SYSTEM
from streetrace.tools.tool_provider import AnyTool


class CoderAgent(StreetRaceAgent):
    """StreetRace Coder agent implementation."""

    @override
    def get_agent_card(self) -> StreetRaceAgentCard:
        """Provide an A2A AgentCard."""
        skill = AgentSkill(
            id="implement_feature",
            name="Implement Feature",
            description="Analyze the requirements and implement a feature in code.",
            tags=["coding"],
            examples=["Create a function that calculates the factorial of a number."],
        )

        return StreetRaceAgentCard(
            name="Streetrace Coding Agent",
            description="A peer engineer agent that can help you with coding tasks.",
            version="0.2.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
        )

    @override
    async def get_required_tools(self) -> list[str | AnyTool]:
        """Provide a list of required tools from known libraries, or tool functions.

        Optional. If not implemented, create_agent will be called without tools.
        """
        return [
            "streetrace:fs_tool::create_directory",
            "streetrace:fs_tool::find_in_files",
            "streetrace:fs_tool::list_directory",
            "streetrace:fs_tool::read_file",
            "streetrace:fs_tool::write_file",
            "streetrace:cli_tool::execute_cli_command",
        ]

    @override
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tools: list[AnyTool],
    ) -> BaseAgent:
        """Create the agent Run the Hello World agent with the provided input.

        Args:
            model_factory: Interface to access configured models.
            tools: Tools requested by the agent.

        Returns:
            The root ADK agent.

        """
        agent_card = self.get_agent_card()
        return Agent(
            name="StreetRace",
            model=model_factory.get_current_model(),
            description=agent_card.description,
            instruction=SYSTEM,
            tools=tools,
        )
