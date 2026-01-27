"""Tests for YamlWorkloadDefinition class."""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from streetrace.agents.yaml_models import YamlAgentSpec
from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.yaml_definition import YamlWorkloadDefinition


class TestYamlWorkloadDefinitionRequiredParameters:
    """Test that YamlWorkloadDefinition requires all parameters."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="test-yaml-workload",
            description="A test YAML workload",
            source_path=Path("/test/agent.yaml"),
            format="yaml",
        )

    @pytest.fixture
    def sample_spec(self) -> YamlAgentSpec:
        """Create a sample YamlAgentSpec for testing."""
        return YamlAgentSpec(
            name="test_agent",
            description="A test agent specification",
            model="anthropic/claude-sonnet",
            instruction="You are a helpful assistant.",
        )

    def test_requires_metadata_parameter(
        self,
        sample_spec: YamlAgentSpec,
    ) -> None:
        """Test that metadata parameter is required."""
        from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

        with pytest.raises(TypeError):
            YamlWorkloadDefinition(  # type: ignore[call-arg]
                spec=sample_spec,
            )

    def test_requires_spec_parameter(
        self,
        sample_metadata: WorkloadMetadata,
    ) -> None:
        """Test that spec parameter is required."""
        from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

        with pytest.raises(TypeError):
            YamlWorkloadDefinition(  # type: ignore[call-arg]
                metadata=sample_metadata,
            )

    def test_can_create_with_all_required_parameters(
        self,
        sample_metadata: WorkloadMetadata,
        sample_spec: YamlAgentSpec,
    ) -> None:
        """Test that definition can be created with all required parameters."""
        from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

        definition = YamlWorkloadDefinition(
            metadata=sample_metadata,
            spec=sample_spec,
        )

        assert definition is not None
        assert definition.metadata is sample_metadata
        assert definition.spec is sample_spec


class TestYamlWorkloadDefinitionProperties:
    """Test YamlWorkloadDefinition properties."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="yaml-workflow",
            description="Test YAML workflow description",
            source_path=Path("/path/to/workflow.yaml"),
            format="yaml",
        )

    @pytest.fixture
    def sample_spec(self) -> YamlAgentSpec:
        """Create a sample YamlAgentSpec for testing."""
        return YamlAgentSpec(
            name="my_yaml_agent",
            description="Custom YAML agent description",
            model="openai/gpt-4",
            instruction="Be helpful and concise.",
            global_instruction="Global system instruction.",
        )

    @pytest.fixture
    def definition(
        self,
        sample_metadata: WorkloadMetadata,
        sample_spec: YamlAgentSpec,
    ) -> "YamlWorkloadDefinition":
        """Create a YamlWorkloadDefinition instance for testing."""
        from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

        return YamlWorkloadDefinition(
            metadata=sample_metadata,
            spec=sample_spec,
        )

    def test_spec_property_returns_correct_type(
        self,
        definition: "YamlWorkloadDefinition",
        sample_spec: YamlAgentSpec,
    ) -> None:
        """Test that spec property returns the correct type."""
        assert definition.spec is sample_spec
        assert isinstance(definition.spec, YamlAgentSpec)

    def test_spec_property_is_read_only(
        self,
        definition: "YamlWorkloadDefinition",
    ) -> None:
        """Test that spec property cannot be set."""
        with pytest.raises(AttributeError):
            definition.spec = MagicMock()  # type: ignore[misc]

    def test_metadata_property_returns_metadata(
        self,
        definition: "YamlWorkloadDefinition",
        sample_metadata: WorkloadMetadata,
    ) -> None:
        """Test that metadata property returns the metadata."""
        assert definition.metadata is sample_metadata

    def test_name_property_delegates_to_metadata(
        self, definition: "YamlWorkloadDefinition",
    ) -> None:
        """Test that name property returns metadata.name."""
        assert definition.name == "yaml-workflow"
        assert definition.name == definition.metadata.name


class TestYamlWorkloadDefinitionCreateWorkload:
    """Test YamlWorkloadDefinition.create_workload() method."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="test-workload",
            description="Test workload",
            source_path=Path("/test/workload.yaml"),
            format="yaml",
        )

    @pytest.fixture
    def sample_spec(self) -> YamlAgentSpec:
        """Create a sample YamlAgentSpec for testing."""
        return YamlAgentSpec(
            name="workload_agent",
            description="Agent for workload testing",
            model="anthropic/claude-sonnet",
        )

    @pytest.fixture
    def definition(
        self,
        sample_metadata: WorkloadMetadata,
        sample_spec: YamlAgentSpec,
    ) -> "YamlWorkloadDefinition":
        """Create a YamlWorkloadDefinition instance for testing."""
        from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

        return YamlWorkloadDefinition(
            metadata=sample_metadata,
            spec=sample_spec,
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

    def test_create_workload_returns_basic_workload(
        self,
        definition: "YamlWorkloadDefinition",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that create_workload returns a BasicAgentWorkload instance."""
        from streetrace.workloads.basic_workload import BasicAgentWorkload

        workload = definition.create_workload(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert isinstance(workload, BasicAgentWorkload)

    def test_create_workload_passes_dependencies(
        self,
        definition: "YamlWorkloadDefinition",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that create_workload passes all dependencies to BasicAgentWorkload."""
        workload = definition.create_workload(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert workload._model_factory is mock_model_factory  # noqa: SLF001
        assert workload._tool_provider is mock_tool_provider  # noqa: SLF001
        assert workload._system_context is mock_system_context  # noqa: SLF001
        assert workload._session_service is mock_session_service  # noqa: SLF001


class TestYamlWorkloadDefinitionInheritance:
    """Test YamlWorkloadDefinition inheritance from WorkloadDefinition."""

    def test_inherits_from_workload_definition(self) -> None:
        """Test that YamlWorkloadDefinition inherits from WorkloadDefinition."""
        from streetrace.workloads.definition import WorkloadDefinition
        from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

        assert issubclass(YamlWorkloadDefinition, WorkloadDefinition)

    def test_is_not_abstract(self) -> None:
        """Test that YamlWorkloadDefinition is concrete (not abstract)."""
        from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

        metadata = WorkloadMetadata(
            name="test",
            description="test",
            source_path=Path("/test.yaml"),
            format="yaml",
        )

        spec = YamlAgentSpec(
            name="test_agent",
            description="Test agent",
        )

        # Should not raise - it's concrete
        definition = YamlWorkloadDefinition(
            metadata=metadata,
            spec=spec,
        )

        assert definition is not None
