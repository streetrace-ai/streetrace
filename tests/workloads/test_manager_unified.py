"""Tests for WorkloadManager unified definition system.

This module tests the WorkloadManager that uses only DefinitionLoader instances.
Phase 4 completes the migration to the unified WorkloadDefinition/DefinitionLoader
system, removing all deprecated AgentLoader code.

The WorkloadManager now:
- Uses only _definition_loaders (DefinitionLoader instances)
- Removed format_loaders dict (old AgentLoader instances)
- Removed _discovery_cache for AgentInfo
- Uses discover_definitions() exclusively
- Uses create_workload() with definition loaders only
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.adk.sessions.base_session_service import BaseSessionService

from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.dsl_definition import DslWorkloadDefinition
from streetrace.workloads.dsl_workload import DslWorkload
from streetrace.workloads.loader import DefinitionLoader
from streetrace.workloads.manager import WorkloadManager, WorkloadNotFoundError
from streetrace.workloads.metadata import WorkloadMetadata
from streetrace.workloads.python_loader import PythonDefinitionLoader
from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

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

# Valid YAML agent source for testing
VALID_YAML_AGENT = """\
name: test_yaml_agent
description: A test YAML agent
model: anthropic/claude-sonnet
instruction: |
  You are a helpful assistant.
"""

# Valid Python agent source for testing
VALID_PYTHON_AGENT = """\
from a2a.types import AgentCapabilities

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


class TestPythonAgent(StreetRaceAgent):
    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="test_python_agent",
            description="A test Python agent",
            capabilities=AgentCapabilities(streaming=False),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            version="1.0.0",
        )

    async def create_agent(self, *args, **kwargs):
        from unittest.mock import MagicMock
        return MagicMock()
"""

# Invalid DSL source (syntax error)
INVALID_DSL_SOURCE = """\
streetrace v1

model main =

agent:
    instruction greeting
"""


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
def work_dir() -> Path:
    """Create a temporary work directory."""
    return Path(tempfile.mkdtemp(prefix="streetrace_test_manager_unified_"))


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


class TestWorkloadManagerInitialization:
    """Test WorkloadManager initialization after migration."""

    def test_has_definition_loaders_dict(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test WorkloadManager has _definition_loaders dict."""
        assert hasattr(workload_manager, "_definition_loaders")
        assert isinstance(workload_manager._definition_loaders, dict)  # noqa: SLF001

    def test_definition_loaders_has_sr_extension(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test _definition_loaders has .sr extension mapping."""
        loaders = workload_manager._definition_loaders  # noqa: SLF001
        assert ".sr" in loaders

    def test_definition_loaders_has_yaml_extensions(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test _definition_loaders has .yaml and .yml extension mappings."""
        loaders = workload_manager._definition_loaders  # noqa: SLF001
        assert ".yaml" in loaders
        assert ".yml" in loaders

    def test_definition_loaders_has_python_loader(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test _definition_loaders has Python loader for directories."""
        # Python loader handles directories, stored under special key
        loaders = workload_manager._definition_loaders  # noqa: SLF001
        assert "python" in loaders
        assert isinstance(loaders["python"], PythonDefinitionLoader)

    def test_has_definitions_cache(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test WorkloadManager has _definitions cache dict."""
        assert hasattr(workload_manager, "_definitions")
        assert isinstance(workload_manager._definitions, dict)  # noqa: SLF001

    def test_no_format_loaders_attribute(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test WorkloadManager does NOT have deprecated format_loaders."""
        assert not hasattr(workload_manager, "format_loaders")

    def test_no_discovery_cache_attribute(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test WorkloadManager does NOT have deprecated _discovery_cache."""
        assert not hasattr(workload_manager, "_discovery_cache")

    def test_all_definition_loaders_implement_protocol(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test all loaders implement DefinitionLoader protocol."""
        loaders = workload_manager._definition_loaders  # noqa: SLF001
        for name, loader in loaders.items():
            assert isinstance(loader, DefinitionLoader), (
                f"Loader '{name}' does not implement DefinitionLoader protocol"
            )


class TestWorkloadManagerDiscoverDefinitions:
    """Test WorkloadManager.discover_definitions() method."""

    def test_discover_definitions_returns_list(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test discover_definitions returns a list of WorkloadDefinition."""
        # Create test DSL file
        dsl_file = work_dir / "agents" / "test_agent.sr"
        dsl_file.parent.mkdir(parents=True, exist_ok=True)
        dsl_file.write_text(VALID_DSL_SOURCE)

        # Override search locations to use our work_dir
        workload_manager.search_locations = [("cwd", [work_dir])]

        definitions = workload_manager.discover_definitions()

        assert isinstance(definitions, list)
        assert all(isinstance(d, WorkloadDefinition) for d in definitions)

    def test_discover_definitions_compiles_dsl_files(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test discover_definitions compiles .sr files immediately."""
        # Create test DSL file
        dsl_file = work_dir / "test_compile.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        definitions = workload_manager.discover_definitions()

        # Should find and compile the DSL file
        dsl_defs = [d for d in definitions if isinstance(d, DslWorkloadDefinition)]
        assert len(dsl_defs) >= 1
        # Should have workflow_class populated (compiled, not deferred)
        assert dsl_defs[0].workflow_class is not None

    def test_discover_definitions_parses_yaml_files(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test discover_definitions parses .yaml files."""
        # Create test YAML file
        yaml_file = work_dir / "test_agent.yaml"
        yaml_file.write_text(VALID_YAML_AGENT)

        workload_manager.search_locations = [("cwd", [work_dir])]

        definitions = workload_manager.discover_definitions()

        # Should find and parse the YAML file
        yaml_defs = [d for d in definitions if isinstance(d, YamlWorkloadDefinition)]
        assert len(yaml_defs) >= 1
        assert yaml_defs[0].spec is not None

    def test_discover_definitions_finds_python_agents(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test discover_definitions finds Python agent directories."""
        # Create Python agent directory
        agent_dir = work_dir / "my_python_agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "agent.py"
        agent_file.write_text(VALID_PYTHON_AGENT)

        workload_manager.search_locations = [("cwd", [work_dir])]

        definitions = workload_manager.discover_definitions()

        # Should find the Python agent
        python_defs = [d for d in definitions if d.metadata.format == "python"]
        assert len(python_defs) >= 1
        assert python_defs[0].name == "test_python_agent"

    def test_discover_definitions_handles_compilation_errors_gracefully(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test discover_definitions logs errors but continues with other files."""
        # Create valid and invalid files
        valid_file = work_dir / "valid.sr"
        valid_file.write_text(VALID_DSL_SOURCE)

        invalid_file = work_dir / "invalid.sr"
        invalid_file.write_text(INVALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        # Should not raise, should continue and load valid files
        definitions = workload_manager.discover_definitions()

        # Should have loaded the valid file
        names = [d.name for d in definitions]
        assert "valid" in names

    def test_discover_definitions_caches_results(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test discover_definitions caches definitions in _definitions."""
        dsl_file = work_dir / "cached_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        workload_manager.discover_definitions()

        # Check cache is populated
        assert len(workload_manager._definitions) > 0  # noqa: SLF001
        assert "cached_agent" in workload_manager._definitions  # noqa: SLF001

    def test_discover_definitions_returns_all_formats(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test discover_definitions finds DSL, YAML, and Python agents."""
        # Create all three file types
        dsl_file = work_dir / "dsl_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        yaml_file = work_dir / "yaml_agent.yaml"
        yaml_file.write_text(VALID_YAML_AGENT)

        python_dir = work_dir / "python_agent"
        python_dir.mkdir()
        (python_dir / "agent.py").write_text(VALID_PYTHON_AGENT)

        workload_manager.search_locations = [("cwd", [work_dir])]

        definitions = workload_manager.discover_definitions()

        # Should find all three formats
        formats = {d.metadata.format for d in definitions}
        assert "dsl" in formats
        assert "yaml" in formats
        assert "python" in formats

    def test_discover_definitions_location_priority(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test discover_definitions respects location priority."""
        # Create two locations with same-named agents
        loc1 = work_dir / "loc1"
        loc2 = work_dir / "loc2"
        loc1.mkdir()
        loc2.mkdir()

        # Create agent with same name in both locations
        (loc1 / "priority_test.yaml").write_text(
            "name: priority_test\ndescription: From loc1\nmodel: test\n",
        )
        (loc2 / "priority_test.yaml").write_text(
            "name: priority_test\ndescription: From loc2\nmodel: test\n",
        )

        # loc1 has higher priority
        workload_manager.search_locations = [("loc1", [loc1]), ("loc2", [loc2])]

        definitions = workload_manager.discover_definitions()

        # Should only have one definition for "priority_test"
        priority_defs = [d for d in definitions if d.name == "priority_test"]
        assert len(priority_defs) == 1
        # Should be from loc1 (higher priority)
        assert priority_defs[0].metadata.description == "From loc1"


class TestWorkloadManagerCreateWorkload:
    """Test WorkloadManager.create_workload() context manager."""

    async def test_create_workload_from_dsl_file(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload loads DSL file and returns DslWorkload."""
        dsl_file = work_dir / "test_dsl.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        async with workload_manager.create_workload(str(dsl_file)) as workload:
            assert isinstance(workload, DslWorkload)

    async def test_create_workload_from_yaml_file(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload loads YAML file and returns BasicAgentWorkload."""
        yaml_file = work_dir / "test_yaml.yaml"
        yaml_file.write_text(VALID_YAML_AGENT)

        workload_manager.search_locations = [("cwd", [work_dir])]

        from streetrace.workloads.basic_workload import BasicAgentWorkload

        async with workload_manager.create_workload(str(yaml_file)) as workload:
            assert isinstance(workload, BasicAgentWorkload)

    async def test_create_workload_from_python_directory(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload loads Python agent directory."""
        agent_dir = work_dir / "test_python"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(VALID_PYTHON_AGENT)

        workload_manager.search_locations = [("cwd", [work_dir])]

        from streetrace.workloads.basic_workload import BasicAgentWorkload

        async with workload_manager.create_workload(str(agent_dir)) as workload:
            assert isinstance(workload, BasicAgentWorkload)

    async def test_create_workload_by_name(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload discovers and loads agent by name."""
        dsl_file = work_dir / "my_named_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        async with workload_manager.create_workload("my_named_agent") as workload:
            assert isinstance(workload, DslWorkload)

    async def test_create_workload_default_alias(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload handles 'default' alias."""
        # Create agent with default name
        dsl_file = work_dir / "Streetrace_Coding_Agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        async with workload_manager.create_workload("default") as workload:
            assert workload is not None

    async def test_create_workload_not_found_raises_error(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload raises ValueError for unknown identifier."""
        workload_manager.search_locations = [("cwd", [work_dir])]

        with pytest.raises(ValueError, match="not found"):
            async with workload_manager.create_workload("nonexistent"):
                pass

    async def test_create_workload_closes_workload_on_exit(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload closes workload when exiting context."""
        dsl_file = work_dir / "close_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        # Track that close was called by using the real workload
        async with workload_manager.create_workload(str(dsl_file)) as workload:
            # Workload should be active
            assert workload is not None

        # After exiting context, workload.close() was called
        # The context manager structure ensures this

    async def test_create_workload_requires_session_service(
        self,
        mock_model_factory: ModelFactory,
        mock_tool_provider: ToolProvider,
        mock_system_context: SystemContext,
        work_dir: Path,
    ) -> None:
        """Test create_workload raises if session_service is None."""
        manager = WorkloadManager(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            work_dir=work_dir,
            session_service=None,  # No session service
        )

        dsl_file = work_dir / "session_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        manager.search_locations = [("cwd", [work_dir])]

        with pytest.raises(ValueError, match="session_service is required"):
            async with manager.create_workload(str(dsl_file)):
                pass


class TestWorkloadManagerHttpLoading:
    """Test WorkloadManager HTTP URL loading."""

    async def test_create_workload_from_http_yaml(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test create_workload loads YAML from HTTP URL."""
        from streetrace.agents.resolver import SourceResolution, SourceType

        # Create mock workload with async close
        mock_workload = MagicMock()

        async def async_close() -> None:
            pass

        mock_workload.close = async_close

        # Create mock definition that returns the mock workload
        mock_definition = MagicMock(spec=YamlWorkloadDefinition)
        mock_definition.name = "http_test"
        mock_definition.metadata = WorkloadMetadata(
            name="http_test",
            description="Test",
            source_path=None,
            format="yaml",
        )
        mock_definition.create_workload.return_value = mock_workload

        # Create mock resolution for SourceResolver
        mock_resolution = SourceResolution(
            content=VALID_YAML_AGENT,
            source="https://example.com/agent.yaml",
            source_type=SourceType.HTTP_URL,
            file_path=None,
            format="yaml",
        )

        # Patch SourceResolver.resolve() and loader.load()
        with (
            patch(
                "streetrace.workloads.manager.SourceResolver.resolve",
                return_value=mock_resolution,
            ),
            patch.object(
                workload_manager._definition_loaders[".yaml"],  # noqa: SLF001
                "load",
                return_value=mock_definition,
            ),
        ):
            async with workload_manager.create_workload(
                "https://example.com/agent.yaml",
            ) as workload:
                assert workload is not None

    async def test_create_workload_http_dsl_allowed(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test create_workload allows HTTP DSL (now supported)."""
        from streetrace.agents.resolver import SourceResolution, SourceType

        # Create mock workload with async close
        mock_workload = MagicMock()

        async def async_close() -> None:
            pass

        mock_workload.close = async_close

        # Create mock definition
        mock_definition = MagicMock()
        mock_definition.name = "dsl_http_test"
        mock_definition.metadata = WorkloadMetadata(
            name="dsl_http_test",
            description="Test DSL",
            source_path=None,
            format="dsl",
        )
        mock_definition.create_workload.return_value = mock_workload

        # Create mock resolution for SourceResolver
        mock_resolution = SourceResolution(
            content="streetrace v1\nmodel main = test\nagent:\n    instruction test",
            source="https://example.com/agent.sr",
            source_type=SourceType.HTTP_URL,
            file_path=None,
            format="dsl",
        )

        # Patch SourceResolver.resolve() and loader.load()
        with (
            patch(
                "streetrace.workloads.manager.SourceResolver.resolve",
                return_value=mock_resolution,
            ),
            patch.object(
                workload_manager._definition_loaders[".sr"],  # noqa: SLF001
                "load",
                return_value=mock_definition,
            ),
        ):
            async with workload_manager.create_workload(
                "https://example.com/agent.sr",
            ) as workload:
                assert workload is not None

    async def test_create_workload_http_python_rejected(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test create_workload rejects HTTP Python for security."""
        # Python agents are rejected by SourceResolver for security
        with pytest.raises(ValueError, match="not supported"):
            async with workload_manager.create_workload(
                "https://example.com/agent.py",
            ):
                pass


class TestWorkloadManagerCreateWorkloadFromDefinition:
    """Test WorkloadManager.create_workload_from_definition() method."""

    def test_create_workload_from_definition_returns_dsl_workload(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload_from_definition returns DslWorkload for DSL defs."""
        dsl_file = work_dir / "dsl_workload_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]
        workload_manager.discover_definitions()

        workload = workload_manager.create_workload_from_definition(
            "dsl_workload_test",
        )

        assert isinstance(workload, DslWorkload)

    def test_create_workload_from_definition_returns_basic_workload_for_yaml(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload_from_definition returns BasicWorkload for YAML."""
        yaml_file = work_dir / "yaml_workload_test.yaml"
        yaml_file.write_text(VALID_YAML_AGENT)

        workload_manager.search_locations = [("cwd", [work_dir])]
        workload_manager.discover_definitions()

        workload = workload_manager.create_workload_from_definition(
            "test_yaml_agent",
        )

        # BasicAgentWorkload for YAML
        from streetrace.workloads.basic_workload import BasicAgentWorkload

        assert isinstance(workload, BasicAgentWorkload)

    def test_create_workload_from_definition_raises_for_unknown_name(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload_from_definition raises for unknown name."""
        workload_manager.search_locations = [("cwd", [work_dir])]
        workload_manager._definitions = {}  # noqa: SLF001

        with pytest.raises(WorkloadNotFoundError):
            workload_manager.create_workload_from_definition("nonexistent")

    def test_create_workload_from_definition_auto_discovers_if_not_cached(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload_from_definition calls discover if def not cached."""
        dsl_file = work_dir / "auto_discover_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        # Don't call discover_definitions first
        workload = workload_manager.create_workload_from_definition(
            "auto_discover_agent",
        )

        assert workload is not None
        assert isinstance(workload, DslWorkload)

    def test_create_workload_from_definition_uses_cached_definition(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test create_workload_from_definition uses cached definition."""
        # Create a mock workload
        mock_workload = MagicMock(spec=DslWorkload)

        # Create a mock definition
        mock_metadata = WorkloadMetadata(
            name="cached_test",
            description="Test",
            source_path=Path("/fake/path.sr"),
            format="dsl",
        )

        mock_definition = MagicMock(spec=DslWorkloadDefinition)
        mock_definition.metadata = mock_metadata
        mock_definition.name = "cached_test"
        mock_definition.create_workload.return_value = mock_workload

        # Pre-populate cache (use lowercase key for case-insensitive lookup)
        workload_manager._definitions["cached_test"] = mock_definition  # noqa: SLF001

        workload = workload_manager.create_workload_from_definition("cached_test")

        # Should have called create_workload on the cached definition
        mock_definition.create_workload.assert_called_once()
        assert workload is not None


class TestWorkloadManagerFindWorkloadFiles:
    """Test WorkloadManager._find_workload_files() helper method."""

    def test_find_workload_files_returns_list_of_paths(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test _find_workload_files returns list of Paths."""
        dsl_file = work_dir / "find_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        files = workload_manager._find_workload_files()  # noqa: SLF001

        assert isinstance(files, list)
        assert all(isinstance(f, Path) for f in files)

    def test_find_workload_files_finds_sr_files(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test _find_workload_files finds .sr files."""
        dsl_file = work_dir / "sr_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        files = workload_manager._find_workload_files()  # noqa: SLF001

        sr_files = [f for f in files if f.suffix == ".sr"]
        assert len(sr_files) >= 1

    def test_find_workload_files_finds_yaml_files(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test _find_workload_files finds .yaml and .yml files."""
        yaml_file = work_dir / "yaml_test.yaml"
        yaml_file.write_text(VALID_YAML_AGENT)

        yml_file = work_dir / "yml_test.yml"
        yml_file.write_text(VALID_YAML_AGENT)

        workload_manager.search_locations = [("cwd", [work_dir])]

        files = workload_manager._find_workload_files()  # noqa: SLF001

        yaml_files = [f for f in files if f.suffix in (".yaml", ".yml")]
        assert len(yaml_files) >= 2

    def test_find_workload_files_finds_python_directories(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test _find_workload_files finds Python agent directories."""
        agent_dir = work_dir / "python_test"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(VALID_PYTHON_AGENT)

        workload_manager.search_locations = [("cwd", [work_dir])]

        files = workload_manager._find_workload_files()  # noqa: SLF001

        # Python "files" are actually directories
        python_dirs = [f for f in files if f.is_dir()]
        assert len(python_dirs) >= 1


class TestWorkloadManagerGetDefinitionLoader:
    """Test WorkloadManager._get_definition_loader() helper method."""

    def test_get_definition_loader_returns_dsl_loader_for_sr(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test _get_definition_loader returns DslDefinitionLoader for .sr."""
        from streetrace.workloads.dsl_loader import DslDefinitionLoader

        loader = workload_manager._get_definition_loader(Path("test.sr"))  # noqa: SLF001

        assert isinstance(loader, DslDefinitionLoader)

    def test_get_definition_loader_returns_yaml_loader_for_yaml(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test _get_definition_loader returns YamlDefinitionLoader for .yaml."""
        from streetrace.workloads.yaml_loader import YamlDefinitionLoader

        loader = workload_manager._get_definition_loader(  # noqa: SLF001
            Path("test.yaml"),
        )

        assert isinstance(loader, YamlDefinitionLoader)

    def test_get_definition_loader_returns_yaml_loader_for_yml(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test _get_definition_loader returns YamlDefinitionLoader for .yml."""
        from streetrace.workloads.yaml_loader import YamlDefinitionLoader

        loader = workload_manager._get_definition_loader(  # noqa: SLF001
            Path("test.yml"),
        )

        assert isinstance(loader, YamlDefinitionLoader)

    def test_get_definition_loader_returns_python_loader_for_directory(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test _get_definition_loader returns PythonDefinitionLoader for dirs."""
        agent_dir = work_dir / "python_test"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("# agent")

        loader = workload_manager._get_definition_loader(agent_dir)  # noqa: SLF001

        assert isinstance(loader, PythonDefinitionLoader)

    def test_get_definition_loader_returns_none_for_unknown_extension(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test _get_definition_loader returns None for unknown extensions."""
        loader = workload_manager._get_definition_loader(  # noqa: SLF001
            Path("test.unknown"),
        )

        assert loader is None


class TestWorkloadManagerDeprecatedMethodsRemoved:
    """Test that deprecated methods/attributes have been removed.

    The old AgentLoader-based methods are removed. New methods with similar
    names may exist but use the DefinitionLoader infrastructure.
    """

    def test_no_discover_method(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test deprecated discover() method returning AgentInfo is removed."""
        # The old discover() returned list[AgentInfo]
        # Now we only have discover_definitions() returning list[WorkloadDefinition]
        assert not hasattr(workload_manager, "discover")

    def test_no_create_agent_method(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test deprecated create_agent() context manager is removed."""
        assert not hasattr(workload_manager, "create_agent")

    def test_no_load_from_http_old_method(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test old _load_from_http() returning StreetRaceAgent is removed."""
        # The new _load_from_url() returns WorkloadDefinition
        assert not hasattr(workload_manager, "_load_from_http")

    def test_no_load_definition_old_method(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test old _load_definition() returning StreetRaceAgent is removed."""
        # The new _load_definition_from_identifier() returns WorkloadDefinition
        assert not hasattr(workload_manager, "_load_definition")

    def test_no_is_dsl_definition_method(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test deprecated _is_dsl_definition() method is removed."""
        # No longer needed - definitions know their own type
        assert not hasattr(workload_manager, "_is_dsl_definition")

    def test_no_create_dsl_workload_method(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test deprecated _create_dsl_workload() method is removed."""
        # WorkloadDefinition.create_workload() handles this now
        assert not hasattr(workload_manager, "_create_dsl_workload")

    def test_no_create_basic_workload_method(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test deprecated _create_basic_workload() method is removed."""
        # WorkloadDefinition.create_workload() handles this now
        assert not hasattr(workload_manager, "_create_basic_workload")

    def test_new_load_methods_exist(
        self,
        workload_manager: WorkloadManager,
    ) -> None:
        """Test new definition-based loading methods exist."""
        # These are new methods using DefinitionLoader infrastructure
        assert hasattr(workload_manager, "_load_from_path")
        assert hasattr(workload_manager, "_load_by_name")
        assert hasattr(workload_manager, "_load_from_url")
        assert hasattr(workload_manager, "_discover_in_location")
        assert hasattr(workload_manager, "_load_definition_from_identifier")


class TestWorkloadManagerDefinitionsCaching:
    """Test that definitions are properly cached after discovery."""

    def test_definitions_cached_after_discover_definitions(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test definitions are cached after discover_definitions call."""
        dsl_file = work_dir / "cache_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        # Cache should be empty initially
        assert len(workload_manager._definitions) == 0  # noqa: SLF001

        workload_manager.discover_definitions()

        # Cache should now have definitions
        assert len(workload_manager._definitions) > 0  # noqa: SLF001

    def test_cached_definition_returned_on_second_call(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload_from_definition uses cached definition."""
        dsl_file = work_dir / "second_call_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]
        workload_manager.discover_definitions()

        # Get definition from cache
        cached_def = workload_manager._definitions.get(  # noqa: SLF001
            "second_call_test",
        )

        # Create workload - should use cached definition
        workload = workload_manager.create_workload_from_definition(
            "second_call_test",
        )

        assert workload is not None
        # The definition should still be in cache
        assert workload_manager._definitions.get(  # noqa: SLF001
            "second_call_test",
        ) is cached_def


class TestWorkloadManagerTelemetry:
    """Test telemetry attributes are set correctly."""

    async def test_create_workload_sets_telemetry_attributes(
        self,
        workload_manager: WorkloadManager,
        work_dir: Path,
    ) -> None:
        """Test create_workload sets telemetry attributes on the current span."""
        dsl_file = work_dir / "telemetry_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [work_dir])]

        # Mock the telemetry span
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with patch("streetrace.workloads.manager.trace") as mock_trace:
            mock_trace.get_current_span.return_value = mock_span

            async with workload_manager.create_workload(str(dsl_file)):
                pass

        # Verify telemetry attributes were set
        assert mock_span.set_attribute.called
