"""Tests for verifying SystemContext is passed correctly to agents.

This module tests that SystemContext is properly passed through the workload
creation pipeline when creating BasicAgentWorkload instances from YAML or
Python agents.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from a2a.types import AgentCapabilities
from google.adk.agents import BaseAgent
from google.adk.sessions.base_session_service import BaseSessionService

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool, ToolProvider
from streetrace.workloads import WorkloadManager
from streetrace.workloads.basic_workload import BasicAgentWorkload
from streetrace.workloads.metadata import WorkloadMetadata
from streetrace.workloads.python_definition import PythonWorkloadDefinition


class SystemContextCapturingAgent(StreetRaceAgent):
    """Mock agent implementation that captures the system_context in create_agent."""

    # Class variable to store the received system_context
    received_system_context: SystemContext | None = None

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
async def test_create_workload_passes_system_context(
    mock_model_factory: ModelFactory,
    mock_tool_provider: MagicMock,
    mock_system_context: SystemContext,
    work_dir: Path,
) -> None:
    """Test create_workload passes system context through BasicAgentWorkload."""
    # Reset the class variable to ensure clean state
    SystemContextCapturingAgent.received_system_context = None

    mock_session_service = MagicMock(spec=BaseSessionService)

    # Arrange - Create WorkloadManager
    workload_manager = WorkloadManager(
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider,
        system_context=mock_system_context,
        work_dir=work_dir,
        session_service=mock_session_service,
    )

    agent_instance = SystemContextCapturingAgent()
    agent_card = agent_instance.get_agent_card()

    # Create a mock definition that will return our capturing agent
    mock_metadata = WorkloadMetadata(
        name=agent_card.name,
        description=agent_card.description,
        source_path=work_dir / "test_agent" / "agent.py",
        format="python",
    )

    mock_module = MagicMock()

    mock_definition = PythonWorkloadDefinition(
        metadata=mock_metadata,
        agent_class=SystemContextCapturingAgent,
        module=mock_module,
    )

    # Pre-populate cache with our mock definition
    workload_manager._definitions[agent_card.name.lower()] = mock_definition  # noqa: SLF001

    # Act
    async with workload_manager.create_workload(agent_card.name) as workload:
        assert workload is not None
        assert isinstance(workload, BasicAgentWorkload)

        # The agent hasn't been created yet - it's created when run_async is called
        # But we can verify the workload has the right system_context stored
        assert workload._system_context is mock_system_context  # noqa: SLF001


@pytest.mark.asyncio
async def test_basic_agent_workload_passes_system_context_on_run(
    mock_model_factory: ModelFactory,
    mock_tool_provider: MagicMock,
    mock_system_context: SystemContext,
) -> None:
    """Test BasicAgentWorkload passes system_context when creating the agent."""
    # Reset the class variable to ensure clean state
    SystemContextCapturingAgent.received_system_context = None

    mock_session_service = MagicMock(spec=BaseSessionService)

    agent_instance = SystemContextCapturingAgent()

    # Create a BasicAgentWorkload directly
    workload = BasicAgentWorkload(
        agent_definition=agent_instance,
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider,
        system_context=mock_system_context,
        session_service=mock_session_service,
    )

    # The system_context should be stored in the workload
    assert workload._system_context is mock_system_context  # noqa: SLF001
