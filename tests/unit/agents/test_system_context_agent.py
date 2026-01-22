"""Tests for verifying SystemContext is passed correctly to agents."""

from unittest.mock import MagicMock, patch

import pytest
from a2a.types import AgentCapabilities
from google.adk.agents import BaseAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool, ToolProvider
from streetrace.workloads import WorkloadManager


class SystemContextCapturingAgent(StreetRaceAgent):
    """Mock agent implementation that captures the system_context in create_agent."""

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

    async def get_required_tools(self) -> list[AnyTool]:
        """Return an empty list of required tools."""
        return []

    async def create_agent(
        self,
        model_factory: ModelFactory,  # noqa: ARG002
        tool_provider: ToolProvider,  # noqa: ARG002
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create a mock agent and capture the system_context.

        Args:
            model_factory: Factory for creating models
            tool_provider: List of tools to use
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


@pytest.mark.asyncio
async def test_create_agent_passes_system_context(
    mock_model_factory: ModelFactory,
    mock_tool_provider: MagicMock,
    mock_system_context: SystemContext,
    work_dir,
):
    """Test that create_agent passes the system context to the agent."""
    # Reset the class variable to ensure clean state
    SystemContextCapturingAgent.received_system_context = None

    # Arrange
    workload_manager = WorkloadManager(
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider,
        system_context=mock_system_context,
        work_dir=work_dir,
    )

    agent_card = SystemContextCapturingAgent().get_agent_card()

    # Create mock AgentInfo
    from unittest.mock import MagicMock

    from streetrace.agents.yaml_agent_loader import AgentInfo

    mock_agent_info = AgentInfo(
        name=agent_card.name,
        description=agent_card.description,
        module=MagicMock(),
    )

    # Mock the discovery cache
    workload_manager._discovery_cache = {  # noqa: SLF001
        agent_card.name.lower(): ("cwd", mock_agent_info),
    }

    # Act
    # Mock the python loader to return our test agent
    with patch.object(
        workload_manager.format_loaders["python"],
        "load_agent",
        return_value=SystemContextCapturingAgent(),
    ):
        async with workload_manager.create_agent(agent_card.name) as agent:
            assert agent is not None

    # Assert
    assert SystemContextCapturingAgent.received_system_context is mock_system_context, (
        "The system context was not correctly passed to the agent's create_agent method"
    )
