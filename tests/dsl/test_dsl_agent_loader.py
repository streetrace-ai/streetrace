"""Tests for DSL agent loader integration with WorkloadManager.

Test loading .sr files as agents through the WorkloadManager's workload loading
mechanism using the new DefinitionLoader system.
"""

from pathlib import Path
from unittest.mock import MagicMock

from google.adk.sessions.base_session_service import BaseSessionService

from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.workloads import WorkloadManager
from streetrace.workloads.dsl_loader import DslDefinitionLoader

# Sample DSL sources for testing
VALID_DSL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello! How can I help you today?\"\"\"

tool fs = builtin streetrace.filesystem

agent:
    tools fs
    instruction greeting
"""

INVALID_DSL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting using model "undefined_model": \"\"\"Hello!\"\"\"
"""


class TestDslAgentLoaderIntegration:
    """Test DSL agent loading via WorkloadManager."""

    def test_workload_manager_has_dsl_definition_loader(self) -> None:
        """WorkloadManager includes DSL format in definition loaders."""
        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=Path.cwd(),
        )

        # Check the definition loaders (new API)
        assert ".sr" in manager._definition_loaders  # noqa: SLF001
        assert isinstance(
            manager._definition_loaders[".sr"],  # noqa: SLF001
            DslDefinitionLoader,
        )

    def test_load_sr_file_directly(self, tmp_path: Path) -> None:
        """Load a .sr file directly via path."""
        # Create test DSL file
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )

        # Load definition using new API
        definition = manager._load_from_path(dsl_file)  # noqa: SLF001

        assert definition is not None
        assert definition.metadata.format == "dsl"

    def test_format_hints_include_sr_extension(self) -> None:
        """Ensure .sr extension is in definition loaders."""
        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=Path.cwd(),
        )

        # Check that .sr files are recognized by definition loaders
        loader = manager._get_definition_loader(Path("test.sr"))  # noqa: SLF001
        assert loader is not None
        assert isinstance(loader, DslDefinitionLoader)

    def test_discover_sr_files_in_directory(self, tmp_path: Path) -> None:
        """Discover .sr files in agent directories."""
        # Create test directory with agent files
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "my_agent.sr").write_text(VALID_DSL_SOURCE)

        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )
        manager.search_locations = [("cwd", [tmp_path])]

        # Discover definitions using new API
        discovered = manager.discover_definitions()

        # Check that our DSL agent was discovered
        agent_names = [d.name.lower() for d in discovered]
        assert "my_agent" in agent_names

    def test_invalid_dsl_logged_on_discover(self, tmp_path: Path) -> None:
        """Invalid DSL file is logged but discovery continues."""
        # Create invalid DSL file
        dsl_file = tmp_path / "invalid_agent.sr"
        dsl_file.write_text(INVALID_DSL_SOURCE)

        # Also create a valid file
        valid_file = tmp_path / "valid_agent.sr"
        valid_file.write_text(VALID_DSL_SOURCE)

        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )
        manager.search_locations = [("cwd", [tmp_path])]

        # Discovery should succeed (valid file) but skip invalid
        discovered = manager.discover_definitions()

        # Should find valid file only
        names = [d.name.lower() for d in discovered]
        assert "valid_agent" in names
        # Invalid file should be skipped silently (logged)


class TestDslDefinitionLoaderDirect:
    """Test the DSL definition loader directly."""

    def test_load_from_resolution(self, tmp_path: Path) -> None:
        """Load definition from SourceResolution."""
        from streetrace.agents.resolver import SourceResolution, SourceType

        dsl_file = tmp_path / "my_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        resolution = SourceResolution(
            content=VALID_DSL_SOURCE,
            source=str(dsl_file),
            source_type=SourceType.FILE_PATH,
            file_path=dsl_file,
            format="dsl",
        )

        loader = DslDefinitionLoader()
        definition = loader.load(resolution)

        assert definition is not None
        assert definition.name == "my_agent"
        assert definition.metadata.format == "dsl"

    def test_load_uses_resolution_content(self, tmp_path: Path) -> None:
        """Load uses content from SourceResolution, not file."""
        from streetrace.agents.resolver import SourceResolution, SourceType

        # File has invalid content
        dsl_file = tmp_path / "my_agent.sr"
        dsl_file.write_text("invalid content")

        # But resolution has valid content
        resolution = SourceResolution(
            content=VALID_DSL_SOURCE,
            source=str(dsl_file),
            source_type=SourceType.FILE_PATH,
            file_path=dsl_file,
            format="dsl",
        )

        loader = DslDefinitionLoader()
        definition = loader.load(resolution)

        # Should succeed because resolution has valid content
        assert definition is not None
        assert definition.name == "my_agent"


class TestDslWorkloadCreation:
    """Test DSL workload creation through WorkloadManager."""

    async def test_create_workload_from_dsl_file(self, tmp_path: Path) -> None:
        """Create workload from .sr file."""
        dsl_file = tmp_path / "test_workload.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        model_factory = MagicMock(spec=ModelFactory)
        model_factory.get_current_model.return_value = MagicMock()
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)
        session_manager = MagicMock()
        session_manager.session_service = MagicMock(spec=BaseSessionService)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
            session_manager=session_manager,
        )

        async with manager.create_workload(str(dsl_file)) as workload:
            assert workload is not None
            # DSL workloads should have specific attributes
            assert hasattr(workload, "run_async")
            assert hasattr(workload, "close")

    async def test_create_workload_from_dsl_by_name(self, tmp_path: Path) -> None:
        """Create workload by name discovery."""
        dsl_file = tmp_path / "named_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        model_factory = MagicMock(spec=ModelFactory)
        model_factory.get_current_model.return_value = MagicMock()
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)
        session_manager = MagicMock()
        session_manager.session_service = MagicMock(spec=BaseSessionService)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
            session_manager=session_manager,
        )
        manager.search_locations = [("cwd", [tmp_path])]

        # Should discover and load by name
        async with manager.create_workload("named_agent") as workload:
            assert workload is not None
