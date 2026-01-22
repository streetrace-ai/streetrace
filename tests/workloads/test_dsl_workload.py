"""Tests for DSL workload routing in WorkloadManager.

Test that WorkloadManager properly routes DSL definitions (DslStreetRaceAgent)
to DslAgentWorkflow and PY/YAML definitions to BasicAgentWorkload.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from streetrace.workloads.basic_workload import BasicAgentWorkload
from streetrace.workloads.manager import WorkloadManager
from streetrace.workloads.protocol import Workload

# Valid DSL source for testing
VALID_DSL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello! How can I help you today?\"\"\"

tool fs = builtin streetrace.filesystem

agent:
    tools fs
    instruction greeting
"""


class MockBasicAgent(StreetRaceAgent):
    """Mock basic agent implementation for testing."""

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
        return []

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
    mock_factory.get_llm_interface.return_value = MagicMock()
    return mock_factory


@pytest.fixture
def mock_tool_provider() -> ToolProvider:
    """Create a mock ToolProvider."""
    return MagicMock(spec=ToolProvider)


@pytest.fixture
def work_dir() -> Path:
    """Create a temporary work directory."""
    return Path(tempfile.mkdtemp(prefix="streetrace_test_dsl_workload_"))


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


class TestDslWorkloadRouting:
    """Test cases for DSL definition routing to DslAgentWorkflow."""

    async def test_dsl_definition_creates_dsl_workload(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test that DSL definition routes to DslAgentWorkflow."""
        # Create DSL file
        dsl_file = work_dir / "test_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        # Load via workload manager
        async with workload_manager.create_workload(str(dsl_file)) as workload:
            # Should create a DslAgentWorkflow, not BasicAgentWorkload
            assert workload is not None
            assert isinstance(workload, Workload)
            # Check it's NOT BasicAgentWorkload
            assert not isinstance(workload, BasicAgentWorkload)

    async def test_basic_definition_creates_basic_workload(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that PY/YAML definitions route to BasicAgentWorkload."""
        mock_basic_agent = MockBasicAgent("Test Agent")
        mock_agent_info = AgentInfo(
            name="Test Agent",
            description="A test agent",
            module=MagicMock(),
        )

        workload_manager._discovery_cache = {  # noqa: SLF001
            "test agent": ("cwd", mock_agent_info),
        }

        with patch.object(
            workload_manager.format_loaders["python"],
            "load_agent",
            return_value=mock_basic_agent,
        ):
            async with workload_manager.create_workload("Test Agent") as workload:
                # Should create BasicAgentWorkload
                assert workload is not None
                assert isinstance(workload, BasicAgentWorkload)

    async def test_dsl_workload_receives_dependencies(
        self,
        workload_manager: WorkloadManager,
        mock_model_factory: ModelFactory,
        mock_tool_provider: ToolProvider,
        mock_system_context: SystemContext,
        mock_session_service: BaseSessionService,
        work_dir: Path,
    ) -> None:
        """Test that DslAgentWorkflow receives all required dependencies."""
        # Create DSL file
        dsl_file = work_dir / "test_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        async with workload_manager.create_workload(str(dsl_file)) as workload:
            # Check workload has the dependencies
            # DslAgentWorkflow stores these as instance variables
            assert hasattr(workload, "_model_factory")
            assert hasattr(workload, "_tool_provider")
            assert hasattr(workload, "_system_context")
            assert hasattr(workload, "_session_service")
            assert workload._model_factory is mock_model_factory  # noqa: SLF001
            assert workload._tool_provider is mock_tool_provider  # noqa: SLF001
            assert workload._system_context is mock_system_context  # noqa: SLF001
            assert workload._session_service is mock_session_service  # noqa: SLF001

    async def test_dsl_workload_receives_agent_definition(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test that DslAgentWorkflow receives the agent_definition for composition."""
        # Create DSL file
        dsl_file = work_dir / "test_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        async with workload_manager.create_workload(str(dsl_file)) as workload:
            # DslAgentWorkflow should have _agent_def set
            assert hasattr(workload, "_agent_def")
            assert workload._agent_def is not None  # noqa: SLF001

    async def test_dsl_workload_satisfies_workload_protocol(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test that DSL workload satisfies the Workload protocol."""
        # Create DSL file
        dsl_file = work_dir / "test_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        async with workload_manager.create_workload(str(dsl_file)) as workload:
            # Should satisfy Workload protocol
            assert isinstance(workload, Workload)
            # Should have run_async method
            assert hasattr(workload, "run_async")
            assert callable(workload.run_async)
            # Should have close method
            assert hasattr(workload, "close")
            assert callable(workload.close)


class TestDslWorkloadDiscovery:
    """Test cases for DSL workload discovery and loading."""

    async def test_load_dsl_by_name_creates_dsl_workload(
        self,
        mock_model_factory: ModelFactory,
        mock_tool_provider: ToolProvider,
        mock_system_context: SystemContext,
        mock_session_service: BaseSessionService,
        work_dir: Path,
    ) -> None:
        """Test loading DSL agent by name creates DslAgentWorkflow."""
        # Create agents directory and DSL file
        agents_dir = work_dir / "agents"
        agents_dir.mkdir()
        dsl_file = agents_dir / "my_dsl_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        # Create workload manager with work_dir that includes the agents directory
        workload_manager = WorkloadManager(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            work_dir=work_dir,
            session_service=mock_session_service,
        )

        # Load by name
        async with workload_manager.create_workload("my_dsl_agent") as workload:
            assert workload is not None
            assert isinstance(workload, Workload)
            # Should NOT be BasicAgentWorkload for DSL
            assert not isinstance(workload, BasicAgentWorkload)


class TestDslWorkloadCleanup:
    """Test cases for DSL workload cleanup."""

    async def test_dsl_workload_cleanup_on_context_exit(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test that DSL workload is properly cleaned up on context exit."""
        # Create DSL file
        dsl_file = work_dir / "test_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_ref: Workload | None = None

        async with workload_manager.create_workload(str(dsl_file)) as workload:
            workload_ref = workload

        # After context exit, workload should have been closed
        # For DslAgentWorkflow, this means _created_agents should be empty
        assert workload_ref is not None
        if hasattr(workload_ref, "_created_agents"):
            assert workload_ref._created_agents == []  # noqa: SLF001


class TestWorkloadManagerHelperMethods:
    """Test cases for WorkloadManager helper methods."""

    def test_is_dsl_definition_true_for_dsl_agent(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test _is_dsl_definition returns True for DslStreetRaceAgent."""
        from streetrace.agents.dsl_agent_loader import DslStreetRaceAgent

        # Create a mock DslStreetRaceAgent
        mock_dsl_agent = MagicMock(spec=DslStreetRaceAgent)
        mock_dsl_agent._workflow_class = MagicMock()  # noqa: SLF001

        # Check helper method (if it exists)
        if hasattr(workload_manager, "_is_dsl_definition"):
            result = workload_manager._is_dsl_definition(mock_dsl_agent)  # noqa: SLF001
            assert result is True

    def test_is_dsl_definition_false_for_basic_agent(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test _is_dsl_definition returns False for basic agents."""
        mock_basic_agent = MockBasicAgent("Test")

        # Check helper method (if it exists)
        if hasattr(workload_manager, "_is_dsl_definition"):
            result = workload_manager._is_dsl_definition(mock_basic_agent)  # noqa: SLF001
            assert result is False

    def test_create_dsl_workload_method_exists(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that _create_dsl_workload method exists."""
        assert hasattr(workload_manager, "_create_dsl_workload")
        assert callable(workload_manager._create_dsl_workload)  # noqa: SLF001

    def test_create_basic_workload_method_exists(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that _create_basic_workload method exists."""
        assert hasattr(workload_manager, "_create_basic_workload")
        assert callable(workload_manager._create_basic_workload)  # noqa: SLF001
