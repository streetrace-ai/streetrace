"""YAML-based agent implementation."""

from typing import override

from a2a.types import AgentCapabilities, AgentSkill
from google.adk.agents import BaseAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.agents.yaml_agent_builder import YamlAgentBuilder
from streetrace.agents.yaml_models import AgentDocument
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AdkTool, AnyTool

logger = get_logger(__name__)


class YamlAgent(StreetRaceAgent):
    """StreetRace agent implementation based on YAML specification."""

    def __init__(self, agent_doc: AgentDocument) -> None:
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

        # Create a generic skill for YAML agents
        # In a more sophisticated implementation, skills could be specified in YAML
        skill = AgentSkill(
            id="general_assistance",
            name="General Assistance",
            description=spec.description,
            tags=["general"],
            examples=[f"Help me with {spec.name.lower()} tasks."],
        )

        return StreetRaceAgentCard(
            name=spec.name,
            description=spec.description,
            version="1.0.0",  # Could be made configurable in YAML
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
        )

    @override
    async def get_required_tools(self) -> list[AnyTool]:
        """Provide a list of required tool references.

        Returns:
            List of structured tool references from YAML specification

        """
        # Use a temporary builder just for tool extraction without dependencies
        from streetrace.agents.yaml_agent_builder import YamlAgentBuilder
        from streetrace.llm.model_factory import ModelFactory
        from streetrace.system_context import SystemContext

        # Create minimal components for tool extraction
        try:
            temp_model_factory = ModelFactory()
            temp_system_context = SystemContext()
            temp_builder = YamlAgentBuilder(temp_model_factory, temp_system_context)
            return temp_builder.get_required_tools(self.agent_doc.spec)
        except Exception:
            # If we can't create the full builder, extract tools directly
            return self._extract_tools_directly()

    def _extract_tools_directly(self) -> list[AnyTool]:
        """Extract tools directly from spec without full builder initialization."""
        from streetrace.tools.mcp_transport import HttpTransport, StdioTransport
        from streetrace.tools.tool_refs import McpToolRef, StreetraceToolRef

        tool_refs: list[AnyTool] = []

        for tool_spec in self.agent_doc.spec.tools:
            if tool_spec.streetrace:
                tool_refs.append(StreetraceToolRef(
                    module=tool_spec.streetrace.module,
                    function=tool_spec.streetrace.function,
                ))
            elif tool_spec.mcp:
                mcp_spec = tool_spec.mcp
                if hasattr(mcp_spec.server, "command"):  # stdio
                    transport = StdioTransport(
                        command=mcp_spec.server.command,
                        args=mcp_spec.server.args,
                        env=getattr(mcp_spec.server, "env", {}),
                    )
                else:  # http/sse
                    transport = HttpTransport(
                        url=mcp_spec.server.url,
                        headers=getattr(mcp_spec.server, "headers", {}),
                        timeout=getattr(mcp_spec.server, "timeout", 10),
                    )

                tool_refs.append(McpToolRef(
                    name=mcp_spec.name,
                    server=transport,
                    tools=mcp_spec.tools,
                ))

        return tool_refs

    @override
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tools: list[AdkTool],
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create the agent from YAML specification.

        Args:
            model_factory: Interface to access configured models
            tools: Tools requested by the agent
            system_context: System context for the agent

        Returns:
            The root ADK agent

        """
        # Create the proper builder with injected dependencies
        self._builder = YamlAgentBuilder(model_factory, system_context)

        # Create and return the agent
        return self._builder.create_agent(self.agent_doc, tools)

    @override
    async def process_request(self) -> None:
        """Process the request through the agent workflow."""
        msg = (
            "YAML agents use the standard workflow - "
            "this method should not be called directly"
        )
        raise NotImplementedError(msg)

    @override
    async def send_message(self) -> None:
        """Send a message through the agent workflow."""
        msg = (
            "YAML agents use the standard workflow - "
            "this method should not be called directly"
        )
        raise NotImplementedError(msg)
