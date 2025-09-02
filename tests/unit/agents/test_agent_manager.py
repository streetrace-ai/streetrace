"""Tests for the AgentManager class."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from a2a.types import AgentCapabilities
from google.adk.agents import BaseAgent

from streetrace.agents.agent_manager import AgentManager
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.agents.yaml_agent_loader import AgentInfo
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

    async def get_required_tools(self) -> list[AnyTool]:
        """Return list of required tools."""
        return [
            MagicMock(name="test_tool_1"),
            MagicMock(name="test_tool_2"),
        ]

    async def create_agent(
        self,
        model_factory: ModelFactory,  # noqa: ARG002
        tool_provider: ToolProvider,  # noqa: ARG002
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
    mock_module = MagicMock()
    return AgentInfo(name="Test Agent", description="A test agent", module=mock_module)


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

    def test_list_available_agents(
        self,
        agent_manager: AgentManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test listing available agents."""
        # Arrange
        expected_agents = [mock_agent_info]

        with (
            patch.object(agent_manager.yaml_loader, "discover", return_value=[]),
            patch.object(
                agent_manager.python_loader,
                "discover",
                return_value=expected_agents,
            ),
        ):
            # Act
            agents = agent_manager.discover()

            # Assert
            assert agents == expected_agents

    async def test_create_agent_success(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test successful agent creation."""
        # Arrange
        mock_agent_instance = MockAgent("Test Agent")

        with (
            patch.object(
                agent_manager.yaml_loader,
                "load_agent",
                side_effect=ValueError,
            ),
            patch.object(
                agent_manager.python_loader,
                "load_agent",
                return_value=mock_agent_instance,
            ),
        ):
            # Act
            async with agent_manager.create_agent("Test Agent") as agent:
                # Assert
                assert agent is not None
                assert hasattr(agent, "name")

    async def test_create_agent_not_found(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test agent creation when agent is not found."""
        # Arrange - both loaders will raise ValueError
        with (
            patch.object(
                agent_manager.yaml_loader,
                "load_agent",
                side_effect=ValueError,
            ),
            patch.object(
                agent_manager.python_loader,
                "load_agent",
                side_effect=ValueError,
            ),
            pytest.raises(ValueError, match="Specified agent not found"),
        ):
            # Act & Assert
            async with agent_manager.create_agent("Nonexistent Agent"):
                pass

    async def test_create_agent_default_name(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test creating agent with 'default' name maps to DEFAULT_AGENT."""
        # Arrange
        mock_agent_instance = MockAgent("Streetrace_Coding_Agent")

        with (
            patch.object(
                agent_manager.yaml_loader,
                "load_agent",
                side_effect=ValueError,
            ),
            patch.object(
                agent_manager.python_loader,
                "load_agent",
                return_value=mock_agent_instance,
            ),
        ):
            # Act & Assert
            async with agent_manager.create_agent("default") as agent:
                assert agent is not None

    async def test_create_agent_tool_provider_integration(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test that agent creation properly integrates with tool provider."""
        # Arrange
        mock_agent_instance = MockAgent("Test Agent")

        with (
            patch.object(
                agent_manager.yaml_loader,
                "load_agent",
                side_effect=ValueError,
            ),
            patch.object(
                agent_manager.python_loader,
                "load_agent",
                return_value=mock_agent_instance,
            ),
        ):
            # Act
            async with agent_manager.create_agent("Test Agent"):
                pass

    async def test_create_agent_exception_handling(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test exception handling during agent creation."""

        # Mock agent that raises exception during initialization
        class FailingAgent(StreetRaceAgent):
            msg = "Agent initialization failed"

            def get_agent_card(self) -> StreetRaceAgentCard:
                raise RuntimeError(self.msg)

            async def get_required_tools(self) -> list[AnyTool]:
                raise RuntimeError(self.msg)

            async def create_agent(
                self,
                model_factory,  # noqa: ARG002
                tool_provider: ToolProvider,  # noqa: ARG002
                system_context,  # noqa: ARG002
            ) -> BaseAgent:
                raise RuntimeError(self.msg)

        failing_agent_instance = FailingAgent()

        with (
            patch.object(
                agent_manager.yaml_loader,
                "load_agent",
                side_effect=ValueError,
            ),
            patch.object(
                agent_manager.python_loader,
                "load_agent",
                return_value=failing_agent_instance,
            ),
            pytest.raises(RuntimeError, match="Agent initialization failed"),
        ):
            # Act & Assert
            async with agent_manager.create_agent("Test Agent"):
                pass

    def test_list_available_agents_empty_directories(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test listing agents when directories don't exist or are empty."""
        with (
            patch.object(agent_manager.yaml_loader, "discover", return_value=[]),
            patch.object(agent_manager.python_loader, "discover", return_value=[]),
        ):
            agents = agent_manager.discover()
            assert agents == []

    def test_list_available_agents_multiple_agents(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test listing multiple available agents."""
        # Arrange
        agent_info_1 = AgentInfo(
            name="Agent 1",
            description="First agent",
            module=MagicMock(),
        )
        agent_info_2 = AgentInfo(
            name="Agent 2",
            description="Second agent",
            module=MagicMock(),
        )
        yaml_agents = [agent_info_1]
        python_agents = [agent_info_2]
        expected_agents = yaml_agents + python_agents

        with (
            patch.object(
                agent_manager.yaml_loader,
                "discover",
                return_value=yaml_agents,
            ),
            patch.object(
                agent_manager.python_loader,
                "discover",
                return_value=python_agents,
            ),
        ):
            # Act
            agents = agent_manager.discover()

            # Assert
            assert len(agents) == 2
            assert agents == expected_agents

    def test_agent_manager_paths_configuration(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test that AgentManager configures correct base directories."""
        # Verify the loaders are initialized with correct paths
        expected_paths = list(
            {
                agent_manager.work_dir / Path("./agents"),
                Path.cwd() / Path("./agents"),
                agent_manager.work_dir / ".",
                Path.cwd() / ".",
                Path("~/.streetrace/agents").expanduser(),
                Path("/etc/streetrace/agents"),
            },
        )

        # The paths are stored as Path objects in the loaders
        assert agent_manager.yaml_loader.base_paths == expected_paths
        assert agent_manager.python_loader.base_paths == expected_paths


class TestAgentManagerResourceManagement:
    """Test cases for AgentManager resource management functionality."""

    @pytest.fixture
    def mock_tool_provider(self, mock_tool_provider) -> ToolProvider:
        """Create a mock ToolProvider."""
        mock_tools = [MagicMock(), MagicMock()]
        mock_tool_provider.get_tools = AsyncMock(return_value=mock_tools)
        return mock_tool_provider

    @pytest.fixture
    def mock_agent_manager(
        self,
        mock_model_factory: ModelFactory,
        mock_tool_provider: ToolProvider,
        mock_system_context: SystemContext,
        work_dir: Path,
    ) -> AgentManager:
        """Create an AgentManager instance with proper resource management."""
        return AgentManager(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            work_dir=work_dir,
        )

    async def test_create_agent_calls_close_on_success(
        self,
        mock_tool_provider: Mock,
        mock_agent_manager: AgentManager,
    ) -> None:
        """Test that agent.close is called when agent creation succeeds."""
        # Arrange
        mock_agent_instance = MockAgent("Test Agent")
        mock_agent_manager.tool_provider = mock_tool_provider

        with (
            patch.object(
                mock_agent_instance,
                "close",
                new_callable=AsyncMock,
            ) as mock_close,
            patch.object(
                mock_agent_manager.yaml_loader,
                "load_agent",
                side_effect=ValueError,
            ),
            patch.object(
                mock_agent_manager.python_loader,
                "load_agent",
                return_value=mock_agent_instance,
            ),
        ):
            # Act
            async with mock_agent_manager.create_agent("Test Agent") as agent:
                assert agent is not None

            # Assert
            mock_close.assert_awaited_once()

    async def test_create_agent_calls_close_on_exception(
        self,
        mock_tool_provider: Mock,
        mock_agent_manager: AgentManager,
    ) -> None:
        """Test that agent.close is called even when agent creation fails."""
        # Arrange
        mock_agent_manager.tool_provider = mock_tool_provider

        # Mock agent that raises exception during agent creation
        class FailingAgent(StreetRaceAgent):
            def __init__(self) -> None:
                self.close_called = False

            def get_agent_card(self) -> StreetRaceAgentCard:
                return StreetRaceAgentCard(
                    name="Failing Agent",
                    description="Agent that fails",
                    capabilities=AgentCapabilities(streaming=False),
                    skills=[],
                    defaultInputModes=["text"],
                    defaultOutputModes=["text"],
                    version="1.0.0",
                )

            async def get_required_tools(self) -> list[AnyTool]:
                return [
                    MagicMock(name="test_tool_1"),
                    MagicMock(name="test_tool_2"),
                ]

            async def create_agent(
                self,
                model_factory,  # noqa: ARG002
                tool_provider: ToolProvider,  # noqa: ARG002
                system_context,  # noqa: ARG002
            ) -> BaseAgent:
                raise RuntimeError("Agent creation failed")

            async def close(self, agent_instance: BaseAgent | None = None) -> None:  # noqa: ARG002
                self.close_called = True

        failing_agent_instance = FailingAgent()

        with (
            patch.object(
                mock_agent_manager.yaml_loader,
                "load_agent",
                side_effect=ValueError,
            ),
            patch.object(
                mock_agent_manager.python_loader,
                "load_agent",
                return_value=failing_agent_instance,
            ),
        ):
            # Act & Assert
            with pytest.raises(RuntimeError, match="Agent creation failed"):
                async with mock_agent_manager.create_agent("Test Agent"):
                    pass

            # Verify that close was not called since agent creation failed
            assert not failing_agent_instance.close_called

    async def test_create_agent_calls_close_on_context_exit_exception(
        self,
        mock_tool_provider: Mock,
        mock_agent_manager: AgentManager,
    ) -> None:
        """Test that agent.close is called when exception occurs in context."""
        # Arrange
        mock_agent_instance = MockAgent("Test Agent")
        mock_agent_manager.tool_provider = mock_tool_provider

        with (
            patch.object(
                mock_agent_instance,
                "close",
                new_callable=AsyncMock,
            ) as mock_close,
            patch.object(
                mock_agent_manager.yaml_loader,
                "load_agent",
                side_effect=ValueError,
            ),
            patch.object(
                mock_agent_manager.python_loader,
                "load_agent",
                return_value=mock_agent_instance,
            ),
        ):
            # Act & Assert
            with pytest.raises(ValueError, match="Test exception"):
                async with mock_agent_manager.create_agent("Test Agent"):
                    raise ValueError("Test exception")

            # Verify that close was still called despite the exception
            mock_close.assert_awaited_once()
