"""Base class for StreetRace agents."""

from abc import ABC, abstractmethod

from a2a.types import AgentCard
from google.adk.agents import BaseAgent

from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool


class StreetRaceAgent(ABC):
    """Base class for StreetRace agents."""

    @abstractmethod
    def get_agent_card(self) -> AgentCard | StreetRaceAgentCard:
        """Provide an A2A AgentCard."""
        msg = "This method should be implemented by subclasses."
        raise NotImplementedError(msg)

    def get_extended_agent_card(self) -> AgentCard | StreetRaceAgentCard:
        """Provide an extended A2A AgentCard.

        If the default agent card reports supportsAuthenticatedExtendedCard,
        this card will be used as the extended agent card.
        """
        msg = "This method should be implemented by subclasses."
        raise NotImplementedError(msg)

    async def get_required_tools(self) -> list[str | AnyTool]:
        """Provide a list of required tools from known libraries, or tool functions.

        Optional. If not implemented, create_agent will be called without tools.
        """
        msg = "This method should be implemented by subclasses."
        raise NotImplementedError(msg)

    @abstractmethod
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tools: list[AnyTool],
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create the agent Run the Hello World agent with the provided input.

        Args:
            model_factory: Interface to access configured models.
            tools: Tools requested by the agent.
            system_context: System context for the agent.

        Returns:
            The root ADK agent.

        """
        msg = "This method should be implemented by subclasses."
        raise NotImplementedError(msg)

    async def process_request(self) -> None:
        """Process the request through the agent workflow.

        This method orchestrates the full interaction cycle between the user and agent.
        """
        msg = "This method should be implemented by subclasses."
        raise NotImplementedError(msg)

    async def send_message(self) -> None:
        """Send a message through the agent workflow."""
        msg = "This method should be implemented by subclasses."
        raise NotImplementedError(msg)
