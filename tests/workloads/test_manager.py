"""Tests for the WorkloadManager class."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from a2a.types import AgentCapabilities
from google.adk.agents import BaseAgent
from google.adk.sessions.base_session_service import BaseSessionService

from streetrace.agents.base_agent_loader import AgentInfo
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool, ToolProvider
from streetrace.workloads.manager import WorkloadManager
from streetrace.workloads.protocol import Workload


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
    return Path(tempfile.mkdtemp(prefix="streetrace_test_workload_manager_"))


@pytest.fixture
def mock_session_service() -> BaseSessionService:
    """Create a mock BaseSessionService."""
    return MagicMock(spec=BaseSessionService)


@pytest.fixture
def workload_manager(
    mock_model_factory: ModelFactory,
    mock_tool_provider: ToolProvider,
    mock_system_context: SystemContext,
    mock_session_service: BaseSessionService,
    work_dir: Path,
) -> WorkloadManager:
    """Create a WorkloadManager instance for testing."""
    return WorkloadManager(
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider,
        system_context=mock_system_context,
        work_dir=work_dir,
        session_service=mock_session_service,
    )


@pytest.fixture
def mock_agent_info() -> AgentInfo:
    """Create a mock AgentInfo."""
    mock_module = MagicMock()
    return AgentInfo(name="Test Agent", description="A test agent", module=mock_module)


class TestWorkloadManagerInstantiation:
    """Test cases for WorkloadManager instantiation."""

    def test_init(
        self,
        mock_model_factory: ModelFactory,
        mock_tool_provider: ToolProvider,
        mock_system_context: SystemContext,
        work_dir: Path,
    ) -> None:
        """Test WorkloadManager initialization."""
        manager = WorkloadManager(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            work_dir=work_dir,
        )

        assert manager.model_factory is mock_model_factory
        assert manager.tool_provider is mock_tool_provider
        assert manager.work_dir == work_dir

    def test_has_format_loaders(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that WorkloadManager has format loaders configured."""
        assert "yaml" in workload_manager.format_loaders
        assert "python" in workload_manager.format_loaders
        assert "dsl" in workload_manager.format_loaders


class TestWorkloadManagerDiscovery:
    """Test cases for WorkloadManager discovery functionality."""

    def test_discover_returns_list(
        self,
        workload_manager: WorkloadManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test that discover returns a list of agents."""
        expected_agents = [mock_agent_info]

        with (
            patch.object(
                workload_manager.format_loaders["yaml"],
                "discover_in_paths",
                return_value=[],
            ),
            patch.object(
                workload_manager.format_loaders["python"],
                "discover_in_paths",
                return_value=expected_agents,
            ),
            patch.object(
                workload_manager.format_loaders["dsl"],
                "discover_in_paths",
                return_value=[],
            ),
        ):
            agents = workload_manager.discover()
            assert agents == expected_agents

    def test_discover_empty_directories(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test discover with empty directories."""
        with (
            patch.object(
                workload_manager.format_loaders["yaml"],
                "discover_in_paths",
                return_value=[],
            ),
            patch.object(
                workload_manager.format_loaders["python"],
                "discover_in_paths",
                return_value=[],
            ),
            patch.object(
                workload_manager.format_loaders["dsl"],
                "discover_in_paths",
                return_value=[],
            ),
        ):
            agents = workload_manager.discover()
            assert agents == []


class TestWorkloadManagerCreateWorkload:
    """Test cases for WorkloadManager.create_workload context manager."""

    async def test_create_workload_context_manager_works(
        self,
        workload_manager: WorkloadManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test that create_workload works as an async context manager."""
        mock_agent_instance = MockAgent("Test Agent")

        workload_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with patch.object(
            workload_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_agent_instance,
        ):
            async with workload_manager.create_workload("Test Agent") as workload:
                assert workload is not None
                # Workload should satisfy the Workload protocol
                assert isinstance(workload, Workload)

    async def test_create_workload_not_found_raises_error(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that create_workload raises ValueError when workload not found."""
        workload_manager._discovery_cache = {}  # noqa: SLF001

        with pytest.raises(ValueError, match="Agent 'Nonexistent' not found"):
            async with workload_manager.create_workload("Nonexistent"):
                pass

    async def test_create_workload_cleanup_on_success(
        self,
        workload_manager: WorkloadManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test that workload.close is called on successful exit."""
        mock_agent_instance = MockAgent("Test Agent")

        workload_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with patch.object(
            workload_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_agent_instance,
        ):
            async with workload_manager.create_workload("Test Agent") as workload:
                # Mock the close method to verify it's called
                original_close = workload.close
                close_called = []

                async def tracking_close() -> None:
                    close_called.append(True)
                    await original_close()

                workload.close = tracking_close  # type: ignore[method-assign]

            # Verify close was called after context exit
            assert len(close_called) == 1

    async def test_create_workload_cleanup_on_exception(
        self,
        workload_manager: WorkloadManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test that workload.close is called even when exception occurs."""
        mock_agent_instance = MockAgent("Test Agent")

        workload_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        close_called = []

        async def run_test() -> None:
            async with workload_manager.create_workload("Test Agent") as workload:
                # Mock the close method
                original_close = workload.close

                async def tracking_close() -> None:
                    close_called.append(True)
                    await original_close()

                workload.close = tracking_close  # type: ignore[method-assign]
                raise ValueError("Test exception")

        with (
            patch.object(
                workload_manager.format_loaders["python"],
                "load_agent",
                return_value=mock_agent_instance,
            ),
            pytest.raises(ValueError, match="Test exception"),
        ):
            await run_test()

        # Verify close was still called
        assert len(close_called) == 1

    async def test_create_workload_default_alias(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that 'default' alias resolves to default agent."""
        mock_agent_instance = MockAgent("Streetrace_Coding_Agent")
        mock_agent_info = AgentInfo(
            name="Streetrace_Coding_Agent",
            description="Default coding agent",
            module=MagicMock(),
        )

        workload_manager._discovery_cache = {  # noqa: SLF001
            "streetrace_coding_agent": ("bundled", mock_agent_info),
        }

        with patch.object(
            workload_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_agent_instance,
        ):
            async with workload_manager.create_workload("default") as workload:
                assert workload is not None


class TestWorkloadManagerBackwardCompatibility:
    """Test cases ensuring WorkloadManager maintains AgentManager compatibility."""

    def test_has_search_locations(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that WorkloadManager has search_locations like AgentManager."""
        assert hasattr(workload_manager, "search_locations")
        assert len(workload_manager.search_locations) > 0

    def test_has_discovery_cache(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that WorkloadManager has _discovery_cache like AgentManager."""
        assert hasattr(workload_manager, "_discovery_cache")

    async def test_create_agent_still_works(
        self,
        workload_manager: WorkloadManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test that create_agent context manager still works for compatibility."""
        mock_agent_instance = MockAgent("Test Agent")

        workload_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with patch.object(
            workload_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_agent_instance,
        ):
            # create_agent should still work
            async with workload_manager.create_agent("Test Agent") as agent:
                assert agent is not None
                assert hasattr(agent, "name")


class TestWorkloadManagerLoadDefinition:
    """Test cases for WorkloadManager._load_definition method."""

    def test_load_definition_by_name(
        self,
        workload_manager: WorkloadManager,
        mock_agent_info: AgentInfo,
    ) -> None:
        """Test loading definition by name."""
        mock_agent_instance = MockAgent("Test Agent")

        workload_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with patch.object(
            workload_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_agent_instance,
        ):
            definition = workload_manager._load_definition("Test Agent")  # noqa: SLF001
            assert definition is mock_agent_instance

    def test_load_definition_not_found_returns_none(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that _load_definition returns None when not found."""
        workload_manager._discovery_cache = {}  # noqa: SLF001
        definition = workload_manager._load_definition("Nonexistent")  # noqa: SLF001
        assert definition is None
