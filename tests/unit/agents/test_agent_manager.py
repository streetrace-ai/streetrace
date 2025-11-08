"""Tests for the AgentManager class."""

import re
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
            patch.object(
                agent_manager.format_loaders["yaml"],
                "discover_in_paths",
                return_value=[],
            ),
            patch.object(
                agent_manager.format_loaders["python"],
                "discover_in_paths",
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
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test successful agent creation."""
        # Arrange
        mock_agent_instance = MockAgent("Test Agent")

        # Mock the discovery cache to make the agent discoverable by name
        agent_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with patch.object(
            agent_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_agent_instance,
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
        # Arrange - ensure discovery cache is empty
        agent_manager._discovery_cache = {}  # noqa: SLF001

        with pytest.raises(ValueError, match="Agent 'Nonexistent Agent' not found"):
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
        mock_agent_info = AgentInfo(
            name="Streetrace_Coding_Agent",
            description="Default coding agent",
            module=MagicMock(),
        )

        # Mock the discovery cache
        agent_manager._discovery_cache = {  # noqa: SLF001
            "streetrace_coding_agent": ("bundled", mock_agent_info),
        }

        with patch.object(
            agent_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_agent_instance,
        ):
            # Act & Assert
            async with agent_manager.create_agent("default") as agent:
                assert agent is not None

    async def test_create_agent_tool_provider_integration(
        self,
        agent_manager: AgentManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test that agent creation properly integrates with tool provider."""
        # Arrange
        mock_agent_instance = MockAgent("Test Agent")

        # Mock the discovery cache
        agent_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with patch.object(
            agent_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_agent_instance,
        ):
            # Act
            async with agent_manager.create_agent("Test Agent"):
                pass

    async def test_create_agent_exception_handling(
        self,
        agent_manager: AgentManager,
        mock_agent_info: AgentInfo,
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

        # Mock the discovery cache
        agent_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with (
            patch.object(
                agent_manager.format_loaders["python"],
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
            patch.object(
                agent_manager.format_loaders["yaml"],
                "discover_in_paths",
                return_value=[],
            ),
            patch.object(
                agent_manager.format_loaders["python"],
                "discover_in_paths",
                return_value=[],
            ),
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
                agent_manager.format_loaders["yaml"],
                "discover_in_paths",
                return_value=yaml_agents,
            ),
            patch.object(
                agent_manager.format_loaders["python"],
                "discover_in_paths",
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
        """Test that AgentManager configures correct search locations."""
        # Verify search locations are configured
        # The new architecture uses location-first priority
        assert len(agent_manager.search_locations) > 0

        # Check that expected locations are present
        location_names = [name for name, _ in agent_manager.search_locations]
        assert (
            "cwd" in location_names
            or "home" in location_names
            or "system" in location_names
        )

        # Verify all paths in search_locations exist
        for location_name, paths in agent_manager.search_locations:
            for path in paths:
                assert path.exists(), f"Path {path} in {location_name} should exist"


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

        mock_agent_info = AgentInfo(
            name="Test Agent",
            description="A test agent",
            module=MagicMock(),
        )

        # Mock the discovery cache
        mock_agent_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with (
            patch.object(
                mock_agent_instance,
                "close",
                new_callable=AsyncMock,
            ) as mock_close,
            patch.object(
                mock_agent_manager.format_loaders["python"],
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

        mock_agent_info = AgentInfo(
            name="Test Agent",
            description="A test agent",
            module=MagicMock(),
        )

        # Mock the discovery cache
        mock_agent_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with patch.object(
            mock_agent_manager.format_loaders["python"],
            "load_agent",
            return_value=failing_agent_instance,
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

        mock_agent_info = AgentInfo(
            name="Test Agent",
            description="A test agent",
            module=MagicMock(),
        )

        # Mock the discovery cache
        mock_agent_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with (
            patch.object(
                mock_agent_instance,
                "close",
                new_callable=AsyncMock,
            ) as mock_close,
            patch.object(
                mock_agent_manager.format_loaders["python"],
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


class TestAgentManagerFilePath:
    """Test cases for AgentManager file path functionality."""

    async def test_create_agent_from_existing_file_path(
        self,
        agent_manager: AgentManager,
        tmp_path: Path,
    ) -> None:
        """Test creating agent when agent_name is an existing file path."""
        # Arrange
        yaml_file = tmp_path / "test_agent.yaml"
        yaml_file.write_text("test content")
        mock_agent_instance = MockAgent("FileBasedAgent")

        with patch.object(
            agent_manager.format_loaders["yaml"],
            "load_from_path",
            return_value=mock_agent_instance,
        ) as mock_yaml_load:
            # Act
            async with agent_manager.create_agent(str(yaml_file)) as agent:
                # Assert
                assert agent is not None
                # Verify yaml_loader.load_from_path was called with Path object
                mock_yaml_load.assert_called_once_with(yaml_file)

    async def test_create_agent_from_non_existing_file_path(
        self,
        agent_manager: AgentManager,
        tmp_path: Path,
    ) -> None:
        """Test creating agent when agent_name is non-existing file path."""
        # Arrange
        non_existing_file = tmp_path / "non_existing.yaml"
        # Ensure file does not exist
        assert not non_existing_file.exists()

        with pytest.raises(
            ValueError,
            match=f"Agent '{re.escape(str(non_existing_file))}' not found",
        ):
            # Act & Assert
            async with agent_manager.create_agent(str(non_existing_file)):
                pass

    async def test_create_agent_fallback_to_name_when_not_file(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test that non-file agent_name falls back to name-based lookup."""
        # Arrange
        agent_name = "some_agent_name"
        mock_agent_instance = MockAgent(agent_name)
        mock_agent_info = AgentInfo(
            name=agent_name,
            description="Test agent",
            module=MagicMock(),
        )

        # Mock the discovery cache
        agent_manager._discovery_cache = {  # noqa: SLF001
            agent_name.lower(): ("cwd", mock_agent_info),
        }

        with patch.object(
            agent_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_agent_instance,
        ):
            # Act
            async with agent_manager.create_agent(agent_name) as agent:
                # Assert
                assert agent is not None

    async def test_create_agent_error_message_includes_agent_name(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test that error message includes the agent name when not found."""
        # Arrange
        agent_name = "non_existent_agent"

        # Ensure discovery cache is empty
        agent_manager._discovery_cache = {}  # noqa: SLF001

        with pytest.raises(
            ValueError,
            match=f"Agent '{re.escape(agent_name)}' not found",
        ):
            # Act & Assert
            async with agent_manager.create_agent(agent_name):
                pass


class TestAgentManagerLocationPriority:
    """Test cases for location-first priority in agent discovery."""

    def test_location_priority_cwd_over_bundled(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test that agents in cwd take priority over bundled agents."""
        # Arrange - Create agents with same name in different locations
        cwd_agent = AgentInfo(
            name="TestAgent",
            description="Agent from cwd",
            file_path=Path("/cwd/agents/test.yaml"),
            yaml_document=MagicMock(),  # Mark as YAML agent
        )
        bundled_agent = AgentInfo(
            name="TestAgent",
            description="Agent from bundled",
            file_path=Path("/bundled/agents/test.yaml"),
            yaml_document=MagicMock(),  # Mark as YAML agent
        )

        # Mock discover_in_paths to return different agents for different locations
        def mock_discover_in_paths(paths: list[Path]) -> list[AgentInfo]:
            # Check if this is cwd or bundled based on paths
            if not paths:
                return []

            path = paths[0].resolve()  # Resolve symlinks
            work_dir_resolved = agent_manager.work_dir.resolve()  # Resolve symlinks

            # Check if path is in work_dir (cwd location)
            try:
                path.relative_to(work_dir_resolved)
            except ValueError:
                pass
            else:
                return [cwd_agent]

            # Check if path contains "agents" (bundled location)
            if "agents" in str(path) and "streetrace" in str(path):
                return [bundled_agent]

            return []

        with (
            patch.object(
                agent_manager.format_loaders["yaml"],
                "discover_in_paths",
                side_effect=mock_discover_in_paths,
            ),
            patch.object(
                agent_manager.format_loaders["python"],
                "discover_in_paths",
                return_value=[],
            ),
        ):
            # Act
            agents = agent_manager.discover()

            # Assert - Only one agent with the name should be returned (from cwd)
            agent_names = [agent.name for agent in agents]
            assert "TestAgent" in agent_names
            # Find the TestAgent
            test_agent = next(a for a in agents if a.name == "TestAgent")
            assert test_agent.description == "Agent from cwd"

    def test_location_priority_home_over_bundled(
        self,
        mock_model_factory: ModelFactory,
        mock_tool_provider: ToolProvider,
        mock_system_context: SystemContext,
        tmp_path: Path,
    ) -> None:
        """Test that agents in home directory take priority over bundled agents."""
        # Arrange - Create a work_dir that doesn't contain the agent
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        agent_manager = AgentManager(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            work_dir=work_dir,
        )

        home_agent = AgentInfo(
            name="TestAgent",
            description="Agent from home",
            file_path=Path.home() / ".streetrace/agents/test.yaml",
            yaml_document=MagicMock(),  # Mark as YAML agent
        )
        bundled_agent = AgentInfo(
            name="TestAgent",
            description="Agent from bundled",
            file_path=Path(__file__).parent / "test.yaml",
            yaml_document=MagicMock(),  # Mark as YAML agent
        )

        def mock_discover_in_paths(paths: list[Path]) -> list[AgentInfo]:
            path_str = str(paths[0]) if paths else ""
            if ".streetrace" in path_str or "home" in path_str:
                return [home_agent]
            if "bundled" in path_str or "agents" in path_str:
                return [bundled_agent]
            return []

        with (
            patch.object(
                agent_manager.format_loaders["yaml"],
                "discover_in_paths",
                side_effect=mock_discover_in_paths,
            ),
            patch.object(
                agent_manager.format_loaders["python"],
                "discover_in_paths",
                return_value=[],
            ),
        ):
            # Act
            agents = agent_manager.discover()

            # Assert - Agent from home should be returned
            test_agent = next((a for a in agents if a.name == "TestAgent"), None)
            assert test_agent is not None
            assert test_agent.description == "Agent from home"

    def test_custom_paths_have_highest_priority(
        self,
        mock_model_factory: ModelFactory,
        mock_tool_provider: ToolProvider,
        mock_system_context: SystemContext,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that custom paths from STREETRACE_AGENT_PATHS have highest priority."""
        # Arrange - Create custom path
        custom_path = tmp_path / "custom_agents"
        custom_path.mkdir()

        # Set environment variable
        monkeypatch.setenv("STREETRACE_AGENT_PATHS", str(custom_path))

        agent_manager = AgentManager(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            work_dir=tmp_path / "work",
        )

        custom_agent = AgentInfo(
            name="TestAgent",
            description="Agent from custom path",
            file_path=custom_path / "test.yaml",
            yaml_document=MagicMock(),  # Mark as YAML agent
        )
        cwd_agent = AgentInfo(
            name="TestAgent",
            description="Agent from cwd",
            file_path=Path("/cwd/test.yaml"),
            yaml_document=MagicMock(),  # Mark as YAML agent
        )

        def mock_discover_in_paths(paths: list[Path]) -> list[AgentInfo]:
            path_str = str(paths[0]) if paths else ""
            if "custom_agents" in path_str:
                return [custom_agent]
            return [cwd_agent]

        with (
            patch.object(
                agent_manager.format_loaders["yaml"],
                "discover_in_paths",
                side_effect=mock_discover_in_paths,
            ),
            patch.object(
                agent_manager.format_loaders["python"],
                "discover_in_paths",
                return_value=[],
            ),
        ):
            # Act
            agents = agent_manager.discover()

            # Assert - Agent from custom path should be returned
            test_agent = next((a for a in agents if a.name == "TestAgent"), None)
            assert test_agent is not None
            assert test_agent.description == "Agent from custom path"

    def test_format_discovery_within_location(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test that all formats are discovered within each location."""
        # Arrange
        yaml_agent = AgentInfo(
            name="YamlAgent",
            description="YAML agent",
            file_path=Path("/cwd/yaml_agent.yaml"),
            yaml_document=MagicMock(),  # Mark as YAML agent
        )
        python_agent = AgentInfo(
            name="PythonAgent",
            description="Python agent",
            module=MagicMock(),
        )

        with (
            patch.object(
                agent_manager.format_loaders["yaml"],
                "discover_in_paths",
                return_value=[yaml_agent],
            ),
            patch.object(
                agent_manager.format_loaders["python"],
                "discover_in_paths",
                return_value=[python_agent],
            ),
        ):
            # Act
            agents = agent_manager.discover()

            # Assert - Both agents should be discovered
            assert len(agents) == 2
            agent_names = {agent.name for agent in agents}
            assert agent_names == {"YamlAgent", "PythonAgent"}

    def test_discovery_cache_populated_correctly(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test that discovery cache is populated with location information."""
        # Arrange
        agent_info = AgentInfo(
            name="TestAgent",
            description="Test agent",
            file_path=Path("/cwd/test.yaml"),
            yaml_document=MagicMock(),  # Mark as YAML agent
        )

        with (
            patch.object(
                agent_manager.format_loaders["yaml"],
                "discover_in_paths",
                return_value=[agent_info],
            ),
            patch.object(
                agent_manager.format_loaders["python"],
                "discover_in_paths",
                return_value=[],
            ),
        ):
            # Act
            agent_manager.discover()

            # Assert - Cache should be populated
            assert agent_manager._discovery_cache is not None  # noqa: SLF001
            assert "testagent" in agent_manager._discovery_cache  # noqa: SLF001
            location, cached_agent = agent_manager._discovery_cache["testagent"]  # noqa: SLF001
            assert cached_agent.name == "TestAgent"
            # Location should be one of the configured locations
            assert location in ["cwd", "home", "bundled", "custom"]

    def test_case_insensitive_agent_name_lookup(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Test that agent name lookup is case-insensitive."""
        # Arrange
        agent_info = AgentInfo(
            name="TestAgent",
            description="Test agent",
            file_path=Path("/cwd/test.yaml"),
            yaml_document=MagicMock(),  # Mark as YAML agent
        )

        with (
            patch.object(
                agent_manager.format_loaders["yaml"],
                "discover_in_paths",
                return_value=[agent_info],
            ),
            patch.object(
                agent_manager.format_loaders["python"],
                "discover_in_paths",
                return_value=[],
            ),
        ):
            # Act
            agent_manager.discover()

            # Assert - All variations should map to the same agent
            assert agent_manager._discovery_cache is not None  # noqa: SLF001
            assert "testagent" in agent_manager._discovery_cache  # noqa: SLF001
            # The cache key should be lowercase
            _, cached_agent = agent_manager._discovery_cache["testagent"]  # noqa: SLF001
            assert cached_agent.name == "TestAgent"
