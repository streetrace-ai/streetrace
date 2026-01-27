"""Tests for DslWorkloadDefinition class."""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.dsl.sourcemap import SourceMapping
from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.dsl_definition import DslWorkloadDefinition


class TestDslWorkloadDefinitionRequiredParameters:
    """Test that DslWorkloadDefinition requires all parameters."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="test-dsl-workload",
            description="A test DSL workload",
            source_path=Path("/test/agent.sr"),
            format="dsl",
        )

    @pytest.fixture
    def sample_workflow_class(self) -> type[DslAgentWorkflow]:
        """Create a sample workflow class for testing."""

        class TestWorkflow(DslAgentWorkflow):
            """Test workflow subclass."""


        return TestWorkflow

    @pytest.fixture
    def sample_source_map(self) -> list[SourceMapping]:
        """Create sample source mappings for testing."""
        return [
            SourceMapping(
                generated_line=10,
                generated_column=0,
                source_file="/test/agent.sr",
                source_line=5,
                source_column=0,
            ),
        ]

    def test_requires_metadata_parameter(
        self,
        sample_workflow_class: type[DslAgentWorkflow],
        sample_source_map: list[SourceMapping],
    ) -> None:
        """Test that metadata parameter is required."""
        from streetrace.workloads.dsl_definition import DslWorkloadDefinition

        with pytest.raises(TypeError):
            DslWorkloadDefinition(  # type: ignore[call-arg]
                workflow_class=sample_workflow_class,
                source_map=sample_source_map,
            )

    def test_requires_workflow_class_parameter(
        self,
        sample_metadata: WorkloadMetadata,
        sample_source_map: list[SourceMapping],
    ) -> None:
        """Test that workflow_class parameter is required."""
        from streetrace.workloads.dsl_definition import DslWorkloadDefinition

        with pytest.raises(TypeError):
            DslWorkloadDefinition(  # type: ignore[call-arg]
                metadata=sample_metadata,
                source_map=sample_source_map,
            )

    def test_requires_source_map_parameter(
        self,
        sample_metadata: WorkloadMetadata,
        sample_workflow_class: type[DslAgentWorkflow],
    ) -> None:
        """Test that source_map parameter is required."""
        from streetrace.workloads.dsl_definition import DslWorkloadDefinition

        with pytest.raises(TypeError):
            DslWorkloadDefinition(  # type: ignore[call-arg]
                metadata=sample_metadata,
                workflow_class=sample_workflow_class,
            )

    def test_can_create_with_all_required_parameters(
        self,
        sample_metadata: WorkloadMetadata,
        sample_workflow_class: type[DslAgentWorkflow],
        sample_source_map: list[SourceMapping],
    ) -> None:
        """Test that definition can be created with all required parameters."""
        from streetrace.workloads.dsl_definition import DslWorkloadDefinition

        definition = DslWorkloadDefinition(
            metadata=sample_metadata,
            workflow_class=sample_workflow_class,
            source_map=sample_source_map,
        )

        assert definition is not None
        assert definition.metadata is sample_metadata
        assert definition.workflow_class is sample_workflow_class
        assert definition.source_map is sample_source_map


class TestDslWorkloadDefinitionProperties:
    """Test DslWorkloadDefinition properties."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="test-workflow",
            description="Test workflow description",
            source_path=Path("/path/to/workflow.sr"),
            format="dsl",
        )

    @pytest.fixture
    def sample_workflow_class(self) -> type[DslAgentWorkflow]:
        """Create a sample workflow class for testing."""

        class MyTestWorkflow(DslAgentWorkflow):
            """Custom workflow for testing."""

        return MyTestWorkflow

    @pytest.fixture
    def sample_source_map(self) -> list[SourceMapping]:
        """Create sample source mappings for testing."""
        return [
            SourceMapping(
                generated_line=1,
                generated_column=0,
                source_file="/path/to/workflow.sr",
                source_line=1,
                source_column=0,
            ),
            SourceMapping(
                generated_line=5,
                generated_column=4,
                source_file="/path/to/workflow.sr",
                source_line=3,
                source_column=2,
            ),
        ]

    @pytest.fixture
    def definition(
        self,
        sample_metadata: WorkloadMetadata,
        sample_workflow_class: type[DslAgentWorkflow],
        sample_source_map: list[SourceMapping],
    ) -> "DslWorkloadDefinition":
        """Create a DslWorkloadDefinition instance for testing."""
        from streetrace.workloads.dsl_definition import DslWorkloadDefinition

        return DslWorkloadDefinition(
            metadata=sample_metadata,
            workflow_class=sample_workflow_class,
            source_map=sample_source_map,
        )

    def test_workflow_class_property_returns_correct_type(
        self,
        definition: "DslWorkloadDefinition",
        sample_workflow_class: type[DslAgentWorkflow],
    ) -> None:
        """Test that workflow_class property returns the correct type."""
        assert definition.workflow_class is sample_workflow_class
        assert issubclass(definition.workflow_class, DslAgentWorkflow)

    def test_source_map_property_returns_correct_list(
        self,
        definition: "DslWorkloadDefinition",
        sample_source_map: list[SourceMapping],
    ) -> None:
        """Test that source_map property returns the correct list."""
        assert definition.source_map is sample_source_map
        assert len(definition.source_map) == 2
        assert all(isinstance(m, SourceMapping) for m in definition.source_map)

    def test_metadata_property_returns_metadata(
        self,
        definition: "DslWorkloadDefinition",
        sample_metadata: WorkloadMetadata,
    ) -> None:
        """Test that metadata property returns the metadata."""
        assert definition.metadata is sample_metadata

    def test_name_property_delegates_to_metadata(
        self, definition: "DslWorkloadDefinition",
    ) -> None:
        """Test that name property returns metadata.name."""
        assert definition.name == "test-workflow"
        assert definition.name == definition.metadata.name

    def test_workflow_class_property_is_read_only(
        self,
        definition: "DslWorkloadDefinition",
    ) -> None:
        """Test that workflow_class property cannot be set."""
        with pytest.raises(AttributeError):
            definition.workflow_class = MagicMock()  # type: ignore[misc]

    def test_source_map_property_is_read_only(
        self, definition: "DslWorkloadDefinition",
    ) -> None:
        """Test that source_map property cannot be set."""
        with pytest.raises(AttributeError):
            definition.source_map = []  # type: ignore[misc]


class TestDslWorkloadDefinitionCreateWorkload:
    """Test DslWorkloadDefinition.create_workload() method."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="test-workload",
            description="Test workload",
            source_path=Path("/test/workload.sr"),
            format="dsl",
        )

    @pytest.fixture
    def sample_workflow_class(self) -> type[DslAgentWorkflow]:
        """Create a sample workflow class for testing."""

        class CreateTestWorkflow(DslAgentWorkflow):
            """Workflow for create_workload testing."""


        return CreateTestWorkflow

    @pytest.fixture
    def sample_source_map(self) -> list[SourceMapping]:
        """Create sample source mappings for testing."""
        return []

    @pytest.fixture
    def definition(
        self,
        sample_metadata: WorkloadMetadata,
        sample_workflow_class: type[DslAgentWorkflow],
        sample_source_map: list[SourceMapping],
    ) -> "DslWorkloadDefinition":
        """Create a DslWorkloadDefinition instance for testing."""
        from streetrace.workloads.dsl_definition import DslWorkloadDefinition

        return DslWorkloadDefinition(
            metadata=sample_metadata,
            workflow_class=sample_workflow_class,
            source_map=sample_source_map,
        )

    @pytest.fixture
    def mock_model_factory(self) -> "ModelFactory":
        """Create mock ModelFactory."""
        return MagicMock()

    @pytest.fixture
    def mock_tool_provider(self) -> "ToolProvider":
        """Create mock ToolProvider."""
        return MagicMock()

    @pytest.fixture
    def mock_system_context(self) -> "SystemContext":
        """Create mock SystemContext."""
        return MagicMock()

    @pytest.fixture
    def mock_session_service(self) -> "BaseSessionService":
        """Create mock BaseSessionService."""
        return MagicMock()

    def test_create_workload_returns_dsl_workload(
        self,
        definition: "DslWorkloadDefinition",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that create_workload returns a DslWorkload instance."""
        from streetrace.workloads.dsl_workload import DslWorkload

        workload = definition.create_workload(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert isinstance(workload, DslWorkload)

    def test_create_workload_passes_dependencies(
        self,
        definition: "DslWorkloadDefinition",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that create_workload passes all dependencies to DslWorkload."""
        workload = definition.create_workload(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert workload._definition is definition  # noqa: SLF001
        assert workload._model_factory is mock_model_factory  # noqa: SLF001
        assert workload._tool_provider is mock_tool_provider  # noqa: SLF001
        assert workload._system_context is mock_system_context  # noqa: SLF001
        assert workload._session_service is mock_session_service  # noqa: SLF001


class TestDslWorkloadDefinitionAgentFactory:
    """Test DslWorkloadDefinition.agent_factory property."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="factory-test",
            description="Agent factory test",
            source_path=Path("/test/factory.sr"),
            format="dsl",
        )

    @pytest.fixture
    def sample_workflow_class(self) -> type[DslAgentWorkflow]:
        """Create a sample workflow class for testing."""

        class FactoryTestWorkflow(DslAgentWorkflow):
            """Workflow for agent factory testing."""

        return FactoryTestWorkflow

    @pytest.fixture
    def sample_source_map(self) -> list[SourceMapping]:
        """Create sample source mappings for testing."""
        return [
            SourceMapping(
                generated_line=1,
                generated_column=0,
                source_file="/test/factory.sr",
                source_line=1,
                source_column=0,
            ),
        ]

    @pytest.fixture
    def definition(
        self,
        sample_metadata: WorkloadMetadata,
        sample_workflow_class: type[DslAgentWorkflow],
        sample_source_map: list[SourceMapping],
    ) -> "DslWorkloadDefinition":
        """Create a DslWorkloadDefinition instance for testing."""
        from streetrace.workloads.dsl_definition import DslWorkloadDefinition

        return DslWorkloadDefinition(
            metadata=sample_metadata,
            workflow_class=sample_workflow_class,
            source_map=sample_source_map,
        )

    def test_agent_factory_property_returns_factory(
        self, definition: "DslWorkloadDefinition",
    ) -> None:
        """Test that agent_factory property returns a DslAgentFactory."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = definition.agent_factory

        assert isinstance(factory, DslAgentFactory)

    def test_agent_factory_has_correct_workflow_class(
        self,
        definition: "DslWorkloadDefinition",
        sample_workflow_class: type[DslAgentWorkflow],
    ) -> None:
        """Test that agent_factory has the correct workflow class."""
        factory = definition.agent_factory

        assert factory.workflow_class is sample_workflow_class

    def test_agent_factory_has_correct_source_file(
        self, definition: "DslWorkloadDefinition",
    ) -> None:
        """Test that agent_factory has the correct source file."""
        factory = definition.agent_factory

        assert factory.source_file == Path("/test/factory.sr")

    def test_agent_factory_has_correct_source_map(
        self,
        definition: "DslWorkloadDefinition",
        sample_source_map: list[SourceMapping],
    ) -> None:
        """Test that agent_factory has the correct source map."""
        factory = definition.agent_factory

        assert factory.source_map is sample_source_map

    def test_agent_factory_is_cached(
        self, definition: "DslWorkloadDefinition",
    ) -> None:
        """Test that agent_factory returns the same instance."""
        factory1 = definition.agent_factory
        factory2 = definition.agent_factory

        assert factory1 is factory2


class TestDslWorkloadDefinitionInheritance:
    """Test DslWorkloadDefinition inheritance from WorkloadDefinition."""

    def test_inherits_from_workload_definition(self) -> None:
        """Test that DslWorkloadDefinition inherits from WorkloadDefinition."""
        from streetrace.workloads.definition import WorkloadDefinition
        from streetrace.workloads.dsl_definition import DslWorkloadDefinition

        assert issubclass(DslWorkloadDefinition, WorkloadDefinition)

    def test_is_not_abstract(self) -> None:
        """Test that DslWorkloadDefinition is concrete (not abstract)."""
        from streetrace.workloads.dsl_definition import DslWorkloadDefinition

        metadata = WorkloadMetadata(
            name="test",
            description="test",
            source_path=Path("/test.sr"),
            format="dsl",
        )

        class TestWorkflow(DslAgentWorkflow):
            pass

        # Should not raise - it's concrete
        definition = DslWorkloadDefinition(
            metadata=metadata,
            workflow_class=TestWorkflow,
            source_map=[],
        )

        assert definition is not None
