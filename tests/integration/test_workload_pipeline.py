"""Integration tests for the workload definition pipeline.

This module tests the full pipeline from source files through discovery
to workload creation and execution setup.

Tests cover:
- Full pipeline: .sr file -> discover_definitions -> create_workload_from_definition
- Full pipeline: .yaml file -> discover_definitions -> create_workload_from_definition
- Invalid DSL files rejected at discovery time
- WorkflowContext always has workflow reference in created workloads
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from google.adk.sessions.base_session_service import BaseSessionService

from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.ui.ui_bus import UiBus
from streetrace.workloads.dsl_definition import DslWorkloadDefinition
from streetrace.workloads.dsl_workload import DslWorkload
from streetrace.workloads.manager import WorkloadManager, WorkloadNotFoundError
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
name: integration_yaml_agent
description: A YAML agent for integration testing
model: anthropic/claude-sonnet
instruction: |
  You are a helpful assistant for integration testing.
"""

# Invalid DSL source (syntax error)
INVALID_DSL_SOURCE = """\
streetrace v1

model main =

agent:
    instruction greeting
"""


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
def integration_work_dir() -> Path:
    """Create a temporary work directory for integration tests."""
    return Path(tempfile.mkdtemp(prefix="streetrace_integration_"))


@pytest.fixture
def workload_manager(
    mock_model_factory: ModelFactory,
    mock_tool_provider: ToolProvider,
    mock_system_context: SystemContext,
    mock_session_service: BaseSessionService,
    integration_work_dir: Path,
) -> WorkloadManager:
    """Create a WorkloadManager for integration testing."""
    return WorkloadManager(
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider,
        system_context=mock_system_context,
        work_dir=integration_work_dir,
        session_service=mock_session_service,
    )


class TestDslPipeline:
    """Integration tests for DSL workload pipeline."""

    def test_full_dsl_pipeline_discover_to_create(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test full pipeline: .sr file -> discover -> create_workload."""
        # Create DSL file
        dsl_file = integration_work_dir / "pipeline_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        # Configure search location
        workload_manager.search_locations = [("cwd", [integration_work_dir])]

        # Step 1: Discover definitions
        definitions = workload_manager.discover_definitions()

        # Should find the DSL file
        dsl_defs = [d for d in definitions if isinstance(d, DslWorkloadDefinition)]
        assert len(dsl_defs) == 1
        assert dsl_defs[0].name == "pipeline_test"

        # Step 2: Create workload from definition
        workload = workload_manager.create_workload_from_definition("pipeline_test")

        # Should be a DslWorkload
        assert isinstance(workload, DslWorkload)

        # Should have a workflow instance
        assert workload._workflow is not None  # noqa: SLF001
        assert isinstance(workload._workflow, DslAgentWorkflow)  # noqa: SLF001

    def test_dsl_workflow_has_dependencies_set(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test that workflow has dependencies set via constructor."""
        dsl_file = integration_work_dir / "deps_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [integration_work_dir])]
        workload_manager.discover_definitions()

        workload = workload_manager.create_workload_from_definition("deps_test")
        workflow = workload._workflow  # noqa: SLF001

        # The workflow should have all dependencies set via constructor
        assert workflow._model_factory is not None  # noqa: SLF001
        assert workflow._tool_provider is not None  # noqa: SLF001
        assert workflow._system_context is not None  # noqa: SLF001
        assert workflow._session_service is not None  # noqa: SLF001

    def test_dsl_definition_compiles_immediately(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test that DSL is compiled during discover, not deferred."""
        dsl_file = integration_work_dir / "compile_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [integration_work_dir])]

        definitions = workload_manager.discover_definitions()

        # Definition should have workflow_class populated (compiled)
        dsl_def = definitions[0]
        assert isinstance(dsl_def, DslWorkloadDefinition)
        assert dsl_def.workflow_class is not None
        assert issubclass(dsl_def.workflow_class, DslAgentWorkflow)


class TestYamlPipeline:
    """Integration tests for YAML workload pipeline."""

    def test_full_yaml_pipeline_discover_to_create(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test full pipeline: .yaml file -> discover -> create_workload."""
        # Create YAML file
        yaml_file = integration_work_dir / "yaml_pipeline.yaml"
        yaml_file.write_text(VALID_YAML_AGENT)

        # Configure search location
        workload_manager.search_locations = [("cwd", [integration_work_dir])]

        # Step 1: Discover definitions
        definitions = workload_manager.discover_definitions()

        # Should find the YAML file
        yaml_defs = [d for d in definitions if isinstance(d, YamlWorkloadDefinition)]
        assert len(yaml_defs) == 1
        assert yaml_defs[0].name == "integration_yaml_agent"

        # Step 2: Create workload from definition
        from streetrace.workloads.basic_workload import BasicAgentWorkload

        workload = workload_manager.create_workload_from_definition(
            "integration_yaml_agent",
        )

        # Should be a BasicAgentWorkload for YAML
        assert isinstance(workload, BasicAgentWorkload)


class TestInvalidFilesRejection:
    """Test that invalid files are rejected at discovery time."""

    def test_invalid_dsl_rejected_at_discovery(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test invalid DSL files are rejected during discovery, not later."""
        # Create invalid DSL file
        invalid_file = integration_work_dir / "invalid.sr"
        invalid_file.write_text(INVALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [integration_work_dir])]

        # Discovery should not raise but should NOT include invalid file
        definitions = workload_manager.discover_definitions()

        # Invalid file should not be in definitions
        names = [d.name for d in definitions]
        assert "invalid" not in names

    def test_invalid_dsl_does_not_prevent_valid_files(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test that one invalid file doesn't prevent loading valid files."""
        # Create both valid and invalid files
        valid_file = integration_work_dir / "valid_file.sr"
        valid_file.write_text(VALID_DSL_SOURCE)

        invalid_file = integration_work_dir / "invalid_file.sr"
        invalid_file.write_text(INVALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [integration_work_dir])]

        # Should still load the valid file
        definitions = workload_manager.discover_definitions()

        names = [d.name for d in definitions]
        assert "valid_file" in names
        assert "invalid_file" not in names


class TestWorkloadNotFound:
    """Test WorkloadNotFoundError behavior."""

    def test_create_workload_raises_for_unknown_name(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test WorkloadNotFoundError raised for unknown workload name."""
        workload_manager.search_locations = [("cwd", [integration_work_dir])]

        with pytest.raises(WorkloadNotFoundError) as exc_info:
            workload_manager.create_workload_from_definition("does_not_exist")

        assert exc_info.value.name == "does_not_exist"
        assert "does_not_exist" in str(exc_info.value)


class TestWorkflowContextIntegration:
    """Test that WorkflowContext always has workflow reference."""

    def test_dsl_workload_has_initialized_workflow(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test that DSL workflow is properly initialized with dependencies."""
        dsl_file = integration_work_dir / "context_test.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        workload_manager.search_locations = [("cwd", [integration_work_dir])]
        workload_manager.discover_definitions()

        workload = workload_manager.create_workload_from_definition("context_test")

        # The DslWorkload should have a workflow
        assert workload._workflow is not None  # noqa: SLF001

        # The workflow should have all dependencies set via constructor
        assert workload._workflow._model_factory is not None  # noqa: SLF001
        assert workload._workflow._tool_provider is not None  # noqa: SLF001
        assert workload._workflow._system_context is not None  # noqa: SLF001
        assert workload._workflow._session_service is not None  # noqa: SLF001


class TestMixedFormats:
    """Test discovering multiple formats in the same directory."""

    def test_discovers_both_dsl_and_yaml(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test both DSL and YAML files are discovered together."""
        # Create both file types
        dsl_file = integration_work_dir / "mixed_dsl.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        yaml_file = integration_work_dir / "mixed_yaml.yaml"
        yaml_file.write_text(VALID_YAML_AGENT)

        workload_manager.search_locations = [("cwd", [integration_work_dir])]

        definitions = workload_manager.discover_definitions()

        # Should find both
        assert len(definitions) >= 2

        formats = {d.metadata.format for d in definitions}
        assert "dsl" in formats
        assert "yaml" in formats

        names = {d.name for d in definitions}
        assert "mixed_dsl" in names
        assert "integration_yaml_agent" in names

    def test_creates_correct_workload_type_for_each_format(
        self,
        workload_manager: WorkloadManager,
        integration_work_dir: Path,
    ) -> None:
        """Test that each format creates the correct workload type."""
        from streetrace.workloads.basic_workload import BasicAgentWorkload

        # Create both file types
        dsl_file = integration_work_dir / "type_test_dsl.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        yaml_file = integration_work_dir / "type_test_yaml.yaml"
        yaml_file.write_text(VALID_YAML_AGENT)

        workload_manager.search_locations = [("cwd", [integration_work_dir])]
        workload_manager.discover_definitions()

        # Create DSL workload
        dsl_workload = workload_manager.create_workload_from_definition(
            "type_test_dsl",
        )
        assert isinstance(dsl_workload, DslWorkload)

        # Create YAML workload
        yaml_workload = workload_manager.create_workload_from_definition(
            "integration_yaml_agent",
        )
        assert isinstance(yaml_workload, BasicAgentWorkload)
