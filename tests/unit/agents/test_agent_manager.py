"""Tests for the AgentManager class."""

import tempfile
from pathlib import Path
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
from streetrace.tools.tool_provider import AnyTool, ToolProvider


class MockAgent(StreetRaceAgent):
    """Mock agent implementation for testing."""

    def __init__(self, name: str = "Test Agent") -> None:
        """Initialize mock agent with given name."""
        self.agent_name = name

    def get_agent_card(self) -> StreetRaceAgentCard:
        """Return a mock agent card."""
        return StreetRaceAgentCard(
            name=self.agent_name,
            description=f"A test agent named {self.agent_name}",
            capabilities=AgentCapabilities(streaming=False),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            version="1.0.0",
        )

    async def get_required_tools(self) -> list[AnyTool | str]:
        """Return list of required tools."""
        return ["test_tool_1", "test_tool_2"]

    async def create_agent(
        self,
        model_factory: ModelFactory,  # noqa: ARG002
        tools: list[AnyTool],  # noqa: ARG002
        system_context: SystemContext,  # noqa: ARG002
    ) -> BaseAgent:
        """Create a mock BaseAgent."""
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.name = self.agent_name
        return mock_agent


@pytest.fixture
def mock_model_factory() -> ModelFactory:
    """Create a mock ModelFactory."""
    mock_factory = MagicMock(spec=ModelFactory)
    mock_factory.get_current_model.return_value = MagicMock()
    return mock_factory


@pytest.fixture
def mock_tool_provider() -> ToolProvider:
    """Create a mock ToolProvider."""
    mock_provider = MagicMock(spec=ToolProvider)
    mock_tools = [MagicMock(), MagicMock()]
    mock_provider.get_tools.return_value.__aenter__ = AsyncMock(return_value=mock_tools)
    mock_provider.get_tools.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_provider


@pytest.fixture
def work_dir() -> Path:
    """Create a temporary work directory."""
    return Path(tempfile.mkdtemp(prefix="streetrace_test_agent_manager_"))


@pytest.fixture
def agent_manager(
    mock_model_factory: ModelFactory,
    mock_tool_provider: ToolProvider,
    mock_system_context: SystemContext,
    work_dir: Path,
) -> AgentManager:
    """Create an AgentManager instance for testing."""
    return AgentManager(
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider,
        system_context=mock_system_context,
        work_dir=work_dir,
    )


@pytest.fixture
def mock_agent_info() -> AgentInfo:
    """Create a mock AgentInfo."""
    mock_card = StreetRaceAgentCard(
        name="Test Agent",
        description="A test agent",
        capabilities=AgentCapabilities(streaming=False),
        skills=[],
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        version="1.0.0",
    )
    mock_module = MagicMock()
    return AgentInfo(agent_card=mock_card, module=mock_module)


class TestAgentManager:
    """Test cases for AgentManager class."""

    def test_init(
        self,
        mock_model_factory: ModelFactory,
        mock_tool_provider: ToolProvider,
        mock_system_context: SystemContext,
        work_dir: Path,
    ) -> None:
        """Test AgentManager initialization."""
        manager = AgentManager(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            work_dir=work_dir,
        )

        assert manager.model_factory is mock_model_factory
        assert manager.tool_provider is mock_tool_provider
        assert manager.work_dir == work_dir

    @patch("streetrace.agents.agent_manager.get_available_agents")
    def test_list_available_agents(
        self,
        mock_get_available_agents: MagicMock,
        agent_manager: AgentManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test listing available agents."""
        # Arrange
        expected_agents = [mock_agent_info]
        mock_get_available_agents.return_value = expected_agents

        # Act
        agents = agent_manager.list_available_agents()

        # Assert
        assert agents == expected_agents
        mock_get_available_agents.assert_called_once()

        # Verify the base directories passed to get_available_agents
        call_args = mock_get_available_agents.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0] == agent_manager.work_dir / "agents"
        assert str(call_args[1]).endswith("agents")

    @patch("streetrace.agents.agent_manager.get_available_agents")
    @patch("streetrace.agents.agent_manager.get_agent_impl")
    async def test_create_agent_success(
        self,
        mock_get_agent_impl: MagicMock,
        mock_get_available_agents: MagicMock,
        agent_manager: AgentManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test successful agent creation."""
        # Arrange
        mock_get_available_agents.return_value = [mock_agent_info]
        mock_agent_class = MockAgent
        mock_get_agent_impl.return_value = mock_agent_class

        # Act
        async with agent_manager.create_agent("Test Agent") as agent:
            # Assert
            assert agent is not None
            assert hasattr(agent, "name")

        # Verify that the correct methods were called
        mock_get_available_agents.assert_called_once()
        mock_get_agent_impl.assert_called_once_with(mock_agent_info)

    @patch("streetrace.agents.agent_manager.get_available_agents")
    async def test_create_agent_not_found(
        self,
        mock_get_available_agents: MagicMock,
        agent_manager: AgentManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test agent creation when agent is not found."""
        # Arrange
        mock_get_available_agents.return_value = [mock_agent_info]

        # Act & Assert
        with pytest.raises(ValueError, match="Specified agent not found"):
            async with agent_manager.create_agent("Nonexistent Agent"):
                pass

    @patch("streetrace.agents.agent_manager.get_available_agents")
    async def test_create_agent_default_name(
        self,
        mock_get_available_agents: MagicMock,
        agent_manager: AgentManager,
    ) -> None:
        """Test creating agent with 'default' name maps to DEFAULT_AGENT."""
        # Arrange
        default_agent_card = StreetRaceAgentCard(
            name="Streetrace Coding Agent",
            description="Default agent",
            capabilities=AgentCapabilities(streaming=False),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            version="1.0.0",
        )
        default_agent_info = AgentInfo(
            agent_card=default_agent_card,
            module=MagicMock(),
        )
        mock_get_available_agents.return_value = [default_agent_info]

        # Act & Assert
        with patch("streetrace.agents.agent_manager.get_agent_impl") as mock_get_impl:
            mock_get_impl.return_value = MockAgent

            async with agent_manager.create_agent("default") as agent:
                assert agent is not None

    @patch("streetrace.agents.agent_manager.get_available_agents")
    @patch("streetrace.agents.agent_manager.get_agent_impl")
    async def test_create_agent_tool_provider_integration(
        self,
        mock_get_agent_impl: MagicMock,
        mock_get_available_agents: MagicMock,
        agent_manager: MagicMock,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test that agent creation properly integrates with tool provider."""
        # Arrange
        mock_get_available_agents.return_value = [mock_agent_info]
        mock_agent_class = MockAgent
        mock_get_agent_impl.return_value = mock_agent_class

        # Act
        async with agent_manager.create_agent("Test Agent"):
            pass

        # Assert
        agent_manager.tool_provider.get_tools.assert_called_once_with(
            ["test_tool_1", "test_tool_2"],
        )

    @patch("streetrace.agents.agent_manager.get_available_agents")
    @patch("streetrace.agents.agent_manager.get_agent_impl")
    async def test_create_agent_exception_handling(
        self,
        mock_get_agent_impl: MagicMock,
        mock_get_available_agents: MagicMock,
        agent_manager: AgentManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test exception handling during agent creation."""
        # Arrange
        mock_get_available_agents.return_value = [mock_agent_info]

        # Mock agent that raises exception during initialization
        class FailingAgent(StreetRaceAgent):
            msg = "Agent initialization failed"

            def get_agent_card(self) -> StreetRaceAgentCard:
                raise RuntimeError(self.msg)

            async def get_required_tools(self) -> list[AnyTool | str]:
                raise RuntimeError(self.msg)

            async def create_agent(
                self,
                model_factory,  # noqa: ARG002
                tools,  # noqa: ARG002
                system_context,  # noqa: ARG002
            ) -> BaseAgent:
                raise RuntimeError(self.msg)

        mock_get_agent_impl.return_value = FailingAgent

        # Act & Assert
        with pytest.raises(RuntimeError, match="Agent initialization failed"):
            async with agent_manager.create_agent("Test Agent"):
                pass

    def test_list_available_agents_empty_directories(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test listing agents when directories don't exist or are empty."""
        with patch("streetrace.agents.agent_manager.get_available_agents") as mock_get:
            mock_get.return_value = []

            agents = agent_manager.list_available_agents()
            assert agents == []

    @patch("streetrace.agents.agent_manager.get_available_agents")
    def test_list_available_agents_multiple_agents(
        self,
        mock_get_available_agents: MagicMock,
        agent_manager: AgentManager,
    ) -> None:
        """Test listing multiple available agents."""
        # Arrange
        agent1_card = StreetRaceAgentCard(
            name="Agent 1",
            description="First agent",
            capabilities=AgentCapabilities(streaming=False),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            version="1.0.0",
        )
        agent2_card = StreetRaceAgentCard(
            name="Agent 2",
            description="Second agent",
            capabilities=AgentCapabilities(streaming=False),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            version="1.0.0",
        )

        agent_info_1 = AgentInfo(agent_card=agent1_card, module=MagicMock())
        agent_info_2 = AgentInfo(agent_card=agent2_card, module=MagicMock())
        expected_agents = [agent_info_1, agent_info_2]

        mock_get_available_agents.return_value = expected_agents

        # Act
        agents = agent_manager.list_available_agents()

        # Assert
        assert len(agents) == 2
        assert agents == expected_agents

    @patch("streetrace.agents.agent_manager.get_available_agents")
    @patch("streetrace.agents.agent_manager.get_agent_impl")
    async def test_create_agent_resource_cleanup(
        self,
        mock_get_agent_impl: MagicMock,
        mock_get_available_agents: MagicMock,
        agent_manager: MagicMock,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test that resources are properly cleaned up when exiting context."""
        # Arrange
        mock_get_available_agents.return_value = [mock_agent_info]
        mock_agent_class = MockAgent
        mock_get_agent_impl.return_value = mock_agent_class

        # Act
        async with agent_manager.create_agent("Test Agent"):
            pass

        # Assert that __aexit__ was called on the tool provider's context manager
        agent_manager.tool_provider.get_tools.return_value.__aexit__.assert_called_once()

    @patch("streetrace.agents.agent_manager.get_available_agents")
    @patch("streetrace.agents.agent_manager.get_agent_impl")
    async def test_create_agent_with_exception_in_context(
        self,
        mock_get_agent_impl: MagicMock,
        mock_get_available_agents: MagicMock,
        agent_manager: MagicMock,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test that resources are cleaned up even when exception occurs in context."""
        # Arrange
        mock_get_available_agents.return_value = [mock_agent_info]
        mock_agent_class = MockAgent
        mock_get_agent_impl.return_value = mock_agent_class
        err_msg = "Simulated error"

        # Act & Assert
        with pytest.raises(RuntimeError, match="Simulated error"):
            async with agent_manager.create_agent("Test Agent"):
                raise RuntimeError(err_msg)

        # Assert that __aexit__ was still called for cleanup
        agent_manager.tool_provider.get_tools.return_value.__aexit__.assert_called_once()

    def test_agent_manager_paths_configuration(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test that AgentManager configures correct base directories."""
        with patch("streetrace.agents.agent_manager.get_available_agents") as mock_get:
            mock_get.return_value = []

            agent_manager.list_available_agents()

            # Verify the correct paths are being used
            call_args = mock_get.call_args[0][0]
            assert len(call_args) == 2

            # First path should be work_dir/agents
            assert call_args[0] == agent_manager.work_dir / "agents"

            # Second path should be relative to the repo root
            assert call_args[1].name == "agents"
            assert "src/streetrace/agents" in str(call_args[1])
