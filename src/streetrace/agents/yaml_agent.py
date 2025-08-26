"""YAML-based agent implementation."""

from typing import TYPE_CHECKING, override

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.agents.yaml_agent_builder import YamlAgentBuilder
from streetrace.agents.yaml_models import YamlAgentDocument
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool, ToolProvider

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent

logger = get_logger(__name__)


class YamlAgent(StreetRaceAgent):
    """StreetRace agent implementation based on YAML specification."""

    def __init__(self, agent_doc: YamlAgentDocument) -> None:
        """Initialize with agent document.

        Args:
            agent_doc: Agent document containing YAML specification

        """
        self.agent_doc = agent_doc
        self._builder: YamlAgentBuilder | None = None

    @override
    def get_agent_card(self) -> StreetRaceAgentCard:
        """Provide an A2A AgentCard."""
        spec = self.agent_doc.spec

        from a2a.types import (
            AgentCapabilities,
            AgentProvider,
            AgentSkill,
            SecurityScheme,
        )

        # Create a generic skill for YAML agents
        # In a more sophisticated implementation, skills could be specified in YAML
        skill = AgentSkill(
            id="general_assistance",
            name="General Assistance",
            description=spec.description,
            tags=["general"],
            examples=[f"Help me with {spec.name.lower()} tasks."],
        )

        card = StreetRaceAgentCard(
            name=spec.name,
            description=spec.description,
            version="1.0.0",  # Could be made configurable in YAML
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
        )

        card.model_rebuild(
            _types_namespace={
                "AgentCapabilities": AgentCapabilities,
                "AgentProvider": AgentProvider,
                "AgentSkill": AgentSkill,
                "SecurityScheme": SecurityScheme,
            },
        )

        return card

    @override
    async def get_required_tools(self) -> list[AnyTool]:
        """Provide a list of required tool references.

        Returns:
            List of structured tool references from YAML specification

        """
        return []

    @override
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
    ) -> "BaseAgent":
        """Create the agent from YAML specification.

        Args:
            model_factory: Interface to access configured models
            tool_provider: Tool provider to create tools for the agents.
            system_context: System context for the agent

        Returns:
            The root ADK agent

        """
        # Create the proper builder with injected dependencies
        self._builder = YamlAgentBuilder(model_factory, tool_provider, system_context)

        # Create and return the agent
        return self._builder.create_agent(self.agent_doc)

    async def close(self, agent_instance: "BaseAgent") -> None:
        """Deallocate all resources allocated by this agent."""
        if self._builder:
            await self._builder.close(agent_instance)
