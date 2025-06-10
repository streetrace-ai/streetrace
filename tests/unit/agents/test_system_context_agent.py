"""Tests for verifying SystemContext is passed correctly to agents."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from a2a.types import AgentCapabilities
from google.adk.agents import BaseAgent

from streetrace.agents.agent_loader import AgentInfo
from streetrace.agents.agent_manager import AgentManager
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool


class SystemContextCapturingAgent(StreetRaceAgent):
    """Mock agent implementation that captures the system_context passed to create_agent."""

    # Class variable to store the received system_context
    received_system_context = None

    def __init__(self, name: str = "System Context Capturing Agent") -> None:
        """Initialize the agent with the given name."""
        self.agent_name = name

    def get_agent_card(self) -> StreetRaceAgentCard:
        """Return a mock agent card."""
        return StreetRaceAgentCard(
            name=self.agent_name,
            description="Agent that captures the system_context passed to create_agent",
            capabilities=AgentCapabilities(streaming=False),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            version="1.0.0",
        )

    async def get_required_tools(self) -> list[str | AnyTool]:
        """Return an empty list of required tools."""
        return []

    async def create_agent(
        self,
        model_factory: ModelFactory,  # noqa: ARG002
        tools: list[AnyTool],  # noqa: ARG002
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create a mock agent and capture the system_context.

        Args:
            model_factory: Factory for creating models
            tools: List of tools to use
            system_context: The system context to capture

        Returns:
            A mock BaseAgent

        """
        # Store the system_context in the class variable so it can be accessed in tests
        SystemContextCapturingAgent.received_system_context = system_context

        # Create and return a mock agent
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.name = self.agent_name
        return mock_agent


@pytest.fixture
def mock_tool_provider_for_async() -> MagicMock:
    """Create a mock ToolProvider with proper async context manager support."""
    mock_provider = MagicMock()

    # Set up the context manager behavior
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=[])
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    # Make get_tools return our mock context manager
    mock_provider.get_tools.return_value = mock_cm

    return mock_provider


@pytest.mark.asyncio
async def test_create_agent_passes_system_context(
    mock_model_factory: ModelFactory,
    mock_tool_provider_for_async: MagicMock,
    mock_system_context: SystemContext,
    work_dir,
):
    """Test that create_agent passes the system context to the agent."""
    # Reset the class variable to ensure clean state
    SystemContextCapturingAgent.received_system_context = None

    # Arrange
    agent_manager = AgentManager(
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider_for_async,
        system_context=mock_system_context,
        work_dir=work_dir,
    )

    agent_card = SystemContextCapturingAgent().get_agent_card()
    agent_info = AgentInfo(
        agent_card=agent_card,
        module=MagicMock(),
    )

    # Act
    with patch(
        "streetrace.agents.agent_manager.get_available_agents",
    ) as mock_get_agents:
        mock_get_agents.return_value = [agent_info]

        with patch("streetrace.agents.agent_manager.get_agent_impl") as mock_get_impl:
            mock_get_impl.return_value = SystemContextCapturingAgent

            async with agent_manager.create_agent(agent_card.name) as agent:
                assert agent is not None

    # Assert
    assert SystemContextCapturingAgent.received_system_context is mock_system_context, (
        "The system context was not correctly passed to the agent's create_agent method"
    )
