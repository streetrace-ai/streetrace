"""Hello World agent implementation.

A simple example agent that demonstrates the StreetRaceAgent interface.
"""

from a2a.types import AgentCapabilities, AgentSkill
from google.adk.agents import Agent, BaseAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool


class HelloWorldAgent(StreetRaceAgent):
    """Hello World agent that implements the StreetRaceAgent interface."""

    def get_agent_card(self) -> StreetRaceAgentCard:
        """Provide an A2A AgentCard.

        Returns:
            A card describing this agent

        """
        return StreetRaceAgentCard(
            name="Hello World",
            description="A simple example agent that greets the user and lists files.",
            capabilities=AgentCapabilities(streaming=False),
            skills=[
                AgentSkill(
                    id="hello_world",
                    name="Hello World",
                    description="Say Hello!",
                    tags=["hello_world"],
                ),
            ],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            version="0.0.1",
        )

    def get_extended_agent_card(self) -> StreetRaceAgentCard:
        """Provide an extended A2A AgentCard.

        Returns:
            An extended card with additional information

        """
        return self.get_agent_card()

    async def get_required_tools(self) -> list[AnyTool | str]:
        """Provide a list of required tools.

        Returns:
            List of required tool references

        """
        return [
            "streetrace:fs_tool::list_directory",
            "streetrace:fs_tool::read_file",
        ]

    async def create_agent(
        self,
        model_factory: ModelFactory,
        tools: list[AnyTool],
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create the Hello World agent.

        Args:
            model_factory: Factory for creating and managing LLM models
            tools: List of tools to provide to the agent
            system_context: System context containing project-level instructions

        Returns:
            The created agent

        """
        model = model_factory.get_current_model()

        return Agent(
            name="Hello World",
            model=model,
            description="A simple example agent that greets the user and lists files.",
            global_instruction=system_context.get_system_message(),
            instruction="""You are the Hello World agent.

Your main purpose is to:
1. Greet the user in a friendly manner
2. List files in the current directory when asked
3. Read files when requested

Always be helpful, concise, and friendly in your responses.""",
            tools=tools,
        )
