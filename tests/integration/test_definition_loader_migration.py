"""Integration tests for the definition-loader migration.

This module tests that after the migration to the unified DefinitionLoader system,
all agent types (YAML, Python, DSL) work correctly through the WorkloadManager.

Tests verify:
1. WorkloadManager can discover all agent types
2. WorkloadManager can load YAML agents from path
3. WorkloadManager can load Python agents from path
4. WorkloadManager can load DSL agents from path
5. Each loaded definition can create a workload

These tests use real agent files from the repository to ensure the actual
agent loading code paths work correctly.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from google.adk.sessions.base_session_service import BaseSessionService

from streetrace.agents.resolver import SourceResolution, SourceType
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.ui.ui_bus import UiBus
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.dsl_definition import DslWorkloadDefinition
from streetrace.workloads.dsl_workload import DslWorkload
from streetrace.workloads.manager import WorkloadManager
from streetrace.workloads.python_definition import PythonWorkloadDefinition
from streetrace.workloads.yaml_definition import YamlWorkloadDefinition


@pytest.fixture
def mock_ui_bus() -> UiBus:
    """Create a mock UiBus."""
    return Mock(spec=UiBus)


@pytest.fixture
def mock_system_context(tmp_path: Path, mock_ui_bus: UiBus) -> SystemContext:
    """Create a mock SystemContext."""
    system_context = Mock(spec=SystemContext)
    system_context.ui_bus = mock_ui_bus
    system_context.config_dir = tmp_path / "context"
    return system_context


@pytest.fixture
def mock_model_factory() -> ModelFactory:
    """Create a mock ModelFactory."""
    mock_factory = MagicMock(spec=ModelFactory)
    mock_factory.get_current_model.return_value = MagicMock()
    return mock_factory


@pytest.fixture
def mock_tool_provider() -> ToolProvider:
    """Create a mock ToolProvider."""
    return MagicMock(spec=ToolProvider)


@pytest.fixture
def mock_session_service() -> BaseSessionService:
    """Create a mock BaseSessionService."""
    return MagicMock(spec=BaseSessionService)


@pytest.fixture
def mock_session_manager(mock_session_service: BaseSessionService) -> MagicMock:
    """Create a mock SessionManager."""
    mock_sm = MagicMock()
    mock_sm.session_service = mock_session_service
    return mock_sm


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def agents_dir(project_root: Path) -> Path:
    """Get the top-level agents directory."""
    return project_root / "agents"


@pytest.fixture
def bundled_agents_dir(project_root: Path) -> Path:
    """Get the bundled agents directory."""
    return project_root / "src" / "streetrace" / "agents"


@pytest.fixture
def integration_work_dir() -> Path:
    """Create a temporary work directory for integration tests."""
    return Path(tempfile.mkdtemp(prefix="streetrace_migration_test_"))


@pytest.fixture
def workload_manager(
    mock_model_factory: ModelFactory,
    mock_tool_provider: ToolProvider,
    mock_system_context: SystemContext,
    mock_session_manager: MagicMock,
    integration_work_dir: Path,
) -> WorkloadManager:
    """Create a WorkloadManager for integration testing."""
    return WorkloadManager(
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider,
        system_context=mock_system_context,
        work_dir=integration_work_dir,
        session_manager=mock_session_manager,
    )


class TestWorkloadDiscovery:
    """Test that WorkloadManager can discover all agent types."""

    def test_discovers_yaml_agents(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test that YAML agents are discovered from the agents directory."""
        workload_manager.search_locations = [("agents", [agents_dir])]

        definitions = workload_manager.discover_definitions()

        # Should find at least one YAML agent
        yaml_defs = [d for d in definitions if isinstance(d, YamlWorkloadDefinition)]
        assert len(yaml_defs) >= 1, "Expected at least one YAML agent"

        # Verify basic_yaml.yaml is found (via its name field)
        # Note: generic.yml conflicts with generic.sr (same stem), DSL wins
        yaml_names = {d.name for d in yaml_defs}
        assert "yaml_test_agent" in yaml_names, (
            f"Expected yaml_test_agent, found: {yaml_names}"
        )

    def test_discovers_dsl_agents(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test that DSL agents are discovered from the agents directory."""
        workload_manager.search_locations = [("agents", [agents_dir])]

        definitions = workload_manager.discover_definitions()

        # Should find at least one DSL agent
        dsl_defs = [d for d in definitions if isinstance(d, DslWorkloadDefinition)]
        assert len(dsl_defs) >= 1, "Expected at least one DSL agent"

        # Verify reviewer.sr is found (DSL names use filename stem, lowercase)
        dsl_names = {d.name for d in dsl_defs}
        assert "reviewer" in dsl_names, f"Expected reviewer, found: {dsl_names}"

    def test_discovers_python_agents(
        self,
        workload_manager: WorkloadManager,
        bundled_agents_dir: Path,
    ) -> None:
        """Test that Python agents are discovered from the bundled agents directory."""
        workload_manager.search_locations = [("bundled", [bundled_agents_dir])]

        definitions = workload_manager.discover_definitions()

        # Should find at least one Python agent
        python_defs = [
            d for d in definitions if isinstance(d, PythonWorkloadDefinition)
        ]
        assert len(python_defs) >= 1, "Expected at least one Python agent"

        # Verify coder agent is found
        python_names = {d.name for d in python_defs}
        assert "Streetrace_Coding_Agent" in python_names, (
            f"Expected Streetrace_Coding_Agent, found: {python_names}"
        )

    def test_discovers_all_formats_together(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
        bundled_agents_dir: Path,
    ) -> None:
        """Test that all agent formats are discovered together."""
        workload_manager.search_locations = [
            ("agents", [agents_dir]),
            ("bundled", [bundled_agents_dir]),
        ]

        definitions = workload_manager.discover_definitions()

        # Should find agents of all three types
        formats = {d.metadata.format for d in definitions}
        assert "yaml" in formats, "Expected YAML agents"
        assert "dsl" in formats, "Expected DSL agents"
        assert "python" in formats, "Expected Python agents"

        # Verify at least 3 total agents
        min_expected = 3
        assert len(definitions) >= min_expected, (
            f"Expected at least {min_expected} agents, found {len(definitions)}"
        )


class TestLoadFromPath:
    """Test that WorkloadManager can load agents from explicit paths."""

    def test_load_yaml_agent_from_path(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test loading a YAML agent directly from its path."""
        yaml_path = agents_dir / "generic.yml"
        assert yaml_path.exists(), f"Test fixture not found: {yaml_path}"

        # Load via identifier (path)
        definition = workload_manager._load_definition_from_identifier(  # noqa: SLF001
            str(yaml_path),
        )

        assert definition is not None
        assert isinstance(definition, YamlWorkloadDefinition)
        assert definition.name == "GenericCodingAssistant"
        assert definition.metadata.format == "yaml"

    def test_load_dsl_agent_from_path(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test loading a DSL agent directly from its path."""
        dsl_path = agents_dir / "reviewer.sr"
        assert dsl_path.exists(), f"Test fixture not found: {dsl_path}"

        # Load via identifier (path)
        definition = workload_manager._load_definition_from_identifier(  # noqa: SLF001
            str(dsl_path),
        )

        assert definition is not None
        assert isinstance(definition, DslWorkloadDefinition)
        # DSL names use filename stem (lowercase)
        assert definition.name == "reviewer"
        assert definition.metadata.format == "dsl"

    def test_load_python_agent_from_path(
        self,
        workload_manager: WorkloadManager,
        bundled_agents_dir: Path,
    ) -> None:
        """Test loading a Python agent directly from its directory path."""
        python_path = bundled_agents_dir / "coder"
        assert python_path.exists(), f"Test fixture not found: {python_path}"
        assert (python_path / "agent.py").exists(), "agent.py not found"

        # Load via identifier (path)
        definition = workload_manager._load_definition_from_identifier(  # noqa: SLF001
            str(python_path),
        )

        assert definition is not None
        assert isinstance(definition, PythonWorkloadDefinition)
        assert definition.name == "Streetrace_Coding_Agent"
        assert definition.metadata.format == "python"


class TestLoadByName:
    """Test that WorkloadManager can load agents by name after discovery."""

    def test_load_yaml_agent_by_name(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test loading a YAML agent by its name."""
        workload_manager.search_locations = [("agents", [agents_dir])]

        # First discover
        workload_manager.discover_definitions()

        # Then load by name (yaml_test_agent from basic_yaml.yaml)
        # Note: generic.yml conflicts with generic.sr (same stem), DSL wins
        definition = workload_manager._load_by_name("yaml_test_agent")  # noqa: SLF001

        assert definition is not None
        assert isinstance(definition, YamlWorkloadDefinition)

    def test_load_dsl_agent_by_name(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test loading a DSL agent by its name."""
        workload_manager.search_locations = [("agents", [agents_dir])]

        # First discover
        workload_manager.discover_definitions()

        # Then load by name (DSL uses filename stem)
        definition = workload_manager._load_by_name("reviewer")  # noqa: SLF001

        assert definition is not None
        assert isinstance(definition, DslWorkloadDefinition)

    def test_load_python_agent_by_name(
        self,
        workload_manager: WorkloadManager,
        bundled_agents_dir: Path,
    ) -> None:
        """Test loading a Python agent by its name."""
        workload_manager.search_locations = [("bundled", [bundled_agents_dir])]

        # First discover
        workload_manager.discover_definitions()

        # Then load by name (case-insensitive)
        definition = workload_manager._load_by_name("Streetrace_Coding_Agent")  # noqa: SLF001

        assert definition is not None
        assert isinstance(definition, PythonWorkloadDefinition)

    def test_load_by_name_case_insensitive(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test that name lookup is case-insensitive."""
        workload_manager.search_locations = [("agents", [agents_dir])]
        workload_manager.discover_definitions()

        # These should all find the same agent
        lower = workload_manager._load_by_name("reviewer")  # noqa: SLF001
        upper = workload_manager._load_by_name("REVIEWER")  # noqa: SLF001
        mixed = workload_manager._load_by_name("ReViEwEr")  # noqa: SLF001

        assert lower is not None
        assert upper is not None
        assert mixed is not None
        assert lower.name == upper.name == mixed.name


class TestCreateWorkload:
    """Test that definitions can create runnable workloads."""

    def test_yaml_definition_creates_workload(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test that a YAML definition can create a BasicAgentWorkload."""
        from streetrace.workloads.basic_workload import BasicAgentWorkload

        workload_manager.search_locations = [("agents", [agents_dir])]
        workload_manager.discover_definitions()

        # Note: generic.yml conflicts with generic.sr (same stem), DSL wins
        # Use yaml_test_agent from basic_yaml.yaml instead
        workload = workload_manager.create_workload_from_definition(
            "yaml_test_agent",
        )

        assert workload is not None
        assert isinstance(workload, BasicAgentWorkload)

    def test_dsl_definition_creates_workload(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test that a DSL definition can create a DslWorkload."""
        workload_manager.search_locations = [("agents", [agents_dir])]
        workload_manager.discover_definitions()

        # DSL uses filename stem as name
        workload = workload_manager.create_workload_from_definition("reviewer")

        assert workload is not None
        assert isinstance(workload, DslWorkload)

    def test_python_definition_creates_workload(
        self,
        workload_manager: WorkloadManager,
        bundled_agents_dir: Path,
    ) -> None:
        """Test that a Python definition can create a BasicAgentWorkload."""
        from streetrace.workloads.basic_workload import BasicAgentWorkload

        workload_manager.search_locations = [("bundled", [bundled_agents_dir])]
        workload_manager.discover_definitions()

        workload = workload_manager.create_workload_from_definition(
            "Streetrace_Coding_Agent",
        )

        assert workload is not None
        assert isinstance(workload, BasicAgentWorkload)


class TestMetadataConsistency:
    """Test that loaded definitions have consistent metadata."""

    def test_yaml_metadata_populated(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test that YAML agent metadata is fully populated."""
        yaml_path = agents_dir / "generic.yml"
        definition = workload_manager._load_from_path(yaml_path)  # noqa: SLF001

        assert definition is not None
        assert definition.metadata.name == "GenericCodingAssistant"
        assert definition.metadata.format == "yaml"
        assert definition.metadata.source_path is not None
        assert definition.metadata.description is not None

    def test_dsl_metadata_populated(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
    ) -> None:
        """Test that DSL agent metadata is fully populated."""
        dsl_path = agents_dir / "reviewer.sr"
        definition = workload_manager._load_from_path(dsl_path)  # noqa: SLF001

        assert definition is not None
        # DSL uses filename stem as name
        assert definition.metadata.name == "reviewer"
        assert definition.metadata.format == "dsl"
        assert definition.metadata.source_path is not None

    def test_python_metadata_populated(
        self,
        workload_manager: WorkloadManager,
        bundled_agents_dir: Path,
    ) -> None:
        """Test that Python agent metadata is fully populated."""
        python_path = bundled_agents_dir / "coder"
        definition = workload_manager._load_from_path(python_path)  # noqa: SLF001

        assert definition is not None
        assert definition.metadata.name == "Streetrace_Coding_Agent"
        assert definition.metadata.format == "python"
        assert definition.metadata.source_path is not None
        assert definition.metadata.description is not None


class TestLocationPriority:
    """Test that location-first priority works correctly."""

    def test_first_location_wins_for_same_name(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
        agents_dir: Path,
    ) -> None:
        """Test that the first location wins when agents have the same name."""
        # Create a local agent with the same name as a bundled one
        local_agents = integration_work_dir / "agents"
        local_agents.mkdir()

        # Create a YAML agent with name "Reviewer" (same as the DSL one in agents/)
        local_yaml = local_agents / "local_reviewer.yaml"
        local_yaml.write_text("""\
version: 1
kind: agent
name: Reviewer
description: Local override reviewer
instruction: "Local reviewer instruction"
""")

        # Set up locations: local first, then agents dir
        workload_manager.search_locations = [
            ("local", [local_agents]),
            ("agents", [agents_dir]),
        ]

        definitions = workload_manager.discover_definitions()

        # Find the Reviewer definition
        reviewers = [d for d in definitions if d.name == "Reviewer"]

        # Should only have one (deduplication)
        assert len(reviewers) == 1

        # Should be YAML (from local), not DSL (from agents/)
        assert reviewers[0].metadata.format == "yaml"
        assert "Local override" in reviewers[0].metadata.description


class TestDefinitionLoaderProtocol:
    """Test that all loaders implement the DefinitionLoader protocol correctly."""

    def test_all_loaders_have_load_method(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test that all definition loaders have the load() method.

        After SourceResolver consolidation, the DefinitionLoader protocol only
        requires load(resolution: SourceResolution). Discovery and can_load
        are handled by SourceResolver.
        """
        for key, loader in workload_manager._definition_loaders.items():  # noqa: SLF001
            assert hasattr(loader, "load"), f"Loader {key} missing load()"

    def test_loaders_return_workload_definitions(
        self,
        workload_manager: WorkloadManager,
        agents_dir: Path,
        bundled_agents_dir: Path,
    ) -> None:
        """Test that all loaders return WorkloadDefinition instances."""
        # Test YAML loader with SourceResolution
        yaml_path = agents_dir / "generic.yml"
        yaml_resolution = SourceResolution(
            content=yaml_path.read_text(),
            source=str(yaml_path),
            source_type=SourceType.FILE_PATH,
            file_path=yaml_path,
            format="yaml",
        )
        yaml_loader = workload_manager._definition_loaders[".yaml"]  # noqa: SLF001
        yaml_def = yaml_loader.load(yaml_resolution)
        assert isinstance(yaml_def, WorkloadDefinition)

        # Test DSL loader with SourceResolution
        dsl_path = agents_dir / "reviewer.sr"
        dsl_resolution = SourceResolution(
            content=dsl_path.read_text(),
            source=str(dsl_path),
            source_type=SourceType.FILE_PATH,
            file_path=dsl_path,
            format="dsl",
        )
        dsl_loader = workload_manager._definition_loaders[".sr"]  # noqa: SLF001
        dsl_def = dsl_loader.load(dsl_resolution)
        assert isinstance(dsl_def, WorkloadDefinition)

        # Test Python loader with SourceResolution
        python_path = bundled_agents_dir / "coder"
        agent_py_path = python_path / "agent.py"
        python_resolution = SourceResolution(
            content=agent_py_path.read_text(),
            source=str(python_path),
            source_type=SourceType.FILE_PATH,
            file_path=python_path,
            format="python",
        )
        python_loader = workload_manager._definition_loaders["python"]  # noqa: SLF001
        python_def = python_loader.load(python_resolution)
        assert isinstance(python_def, WorkloadDefinition)
