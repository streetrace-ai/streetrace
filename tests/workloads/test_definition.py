"""Tests for WorkloadDefinition abstract base class."""

from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

import pytest

from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.protocol import Workload


class TestWorkloadDefinitionAbstractClass:
    """Test that WorkloadDefinition is a proper abstract base class."""

    def test_is_abstract_base_class(self) -> None:
        """Test that WorkloadDefinition inherits from ABC."""
        assert issubclass(WorkloadDefinition, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """Test that WorkloadDefinition cannot be instantiated directly."""
        metadata = WorkloadMetadata(
            name="test",
            description="test workload",
            source_path=Path("/test.sr"),
            format="dsl",
        )

        with pytest.raises(TypeError, match="abstract"):
            WorkloadDefinition(metadata)  # type: ignore[abstract]

    def test_create_workload_is_abstract(self) -> None:
        """Test that create_workload method is abstract."""
        # Check that create_workload is in the abstract methods
        assert "create_workload" in WorkloadDefinition.__abstractmethods__


class TestWorkloadDefinitionConcreteSubclass:
    """Test that concrete subclasses of WorkloadDefinition work correctly."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="test-workload",
            description="A test workload for testing",
            source_path=Path("/test/workload.sr"),
            format="dsl",
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

    def test_concrete_subclass_can_be_created(
        self, sample_metadata: WorkloadMetadata,
    ) -> None:
        """Test that a concrete subclass implementing create_workload can be created."""

        class ConcreteDefinition(WorkloadDefinition):
            """Concrete implementation for testing."""

            def create_workload(
                self,
                model_factory: "ModelFactory",  # noqa: ARG002
                tool_provider: "ToolProvider",  # noqa: ARG002
                system_context: "SystemContext",  # noqa: ARG002
                session_service: "BaseSessionService",  # noqa: ARG002
            ) -> "Workload":
                """Create a workload instance."""
                return Mock()

        # Should not raise
        definition = ConcreteDefinition(sample_metadata)
        assert definition is not None

    def test_metadata_property_returns_metadata(
        self, sample_metadata: WorkloadMetadata,
    ) -> None:
        """Test that metadata property returns the metadata passed to constructor."""

        class ConcreteDefinition(WorkloadDefinition):
            """Concrete implementation for testing."""

            def create_workload(
                self,
                model_factory: "ModelFactory",  # noqa: ARG002
                tool_provider: "ToolProvider",  # noqa: ARG002
                system_context: "SystemContext",  # noqa: ARG002
                session_service: "BaseSessionService",  # noqa: ARG002
            ) -> "Workload":
                """Create a workload instance."""
                return Mock()

        definition = ConcreteDefinition(sample_metadata)

        assert definition.metadata is sample_metadata
        assert definition.metadata.name == "test-workload"
        assert definition.metadata.description == "A test workload for testing"
        assert definition.metadata.source_path == Path("/test/workload.sr")
        assert definition.metadata.format == "dsl"

    def test_name_property_delegates_to_metadata(
        self, sample_metadata: WorkloadMetadata,
    ) -> None:
        """Test that name property returns metadata.name."""

        class ConcreteDefinition(WorkloadDefinition):
            """Concrete implementation for testing."""

            def create_workload(
                self,
                model_factory: "ModelFactory",  # noqa: ARG002
                tool_provider: "ToolProvider",  # noqa: ARG002
                system_context: "SystemContext",  # noqa: ARG002
                session_service: "BaseSessionService",  # noqa: ARG002
            ) -> "Workload":
                """Create a workload instance."""
                return Mock()

        definition = ConcreteDefinition(sample_metadata)

        assert definition.name == "test-workload"
        assert definition.name == definition.metadata.name

    def test_create_workload_receives_all_dependencies(
        self,
        sample_metadata: WorkloadMetadata,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that create_workload receives all required dependencies."""
        received_args: dict[str, object] = {}

        class ConcreteDefinition(WorkloadDefinition):
            """Concrete implementation that records received arguments."""

            def create_workload(
                self,
                model_factory: "ModelFactory",
                tool_provider: "ToolProvider",
                system_context: "SystemContext",
                session_service: "BaseSessionService",
            ) -> "Workload":
                """Create a workload instance and record arguments."""
                received_args["model_factory"] = model_factory
                received_args["tool_provider"] = tool_provider
                received_args["system_context"] = system_context
                received_args["session_service"] = session_service
                return Mock()

        definition = ConcreteDefinition(sample_metadata)
        definition.create_workload(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert received_args["model_factory"] is mock_model_factory
        assert received_args["tool_provider"] is mock_tool_provider
        assert received_args["system_context"] is mock_system_context
        assert received_args["session_service"] is mock_session_service

    def test_create_workload_returns_workload(
        self,
        sample_metadata: WorkloadMetadata,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that create_workload returns a Workload instance."""
        mock_workload = Mock()

        class ConcreteDefinition(WorkloadDefinition):
            """Concrete implementation returning a mock workload."""

            def create_workload(
                self,
                model_factory: "ModelFactory",  # noqa: ARG002
                tool_provider: "ToolProvider",  # noqa: ARG002
                system_context: "SystemContext",  # noqa: ARG002
                session_service: "BaseSessionService",  # noqa: ARG002
            ) -> "Workload":
                """Create a workload instance."""
                return mock_workload

        definition = ConcreteDefinition(sample_metadata)
        result = definition.create_workload(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert result is mock_workload


class TestWorkloadDefinitionWithDifferentFormats:
    """Test WorkloadDefinition with different workload formats."""

    def test_dsl_format_definition(self) -> None:
        """Test definition with DSL format metadata."""
        metadata = WorkloadMetadata(
            name="dsl-workflow",
            description="A DSL-based workflow",
            source_path=Path("/agents/workflow.sr"),
            format="dsl",
        )

        class DslDefinition(WorkloadDefinition):
            """DSL-specific definition."""

            def create_workload(
                self,
                model_factory: "ModelFactory",  # noqa: ARG002
                tool_provider: "ToolProvider",  # noqa: ARG002
                system_context: "SystemContext",  # noqa: ARG002
                session_service: "BaseSessionService",  # noqa: ARG002
            ) -> "Workload":
                """Create DSL workload."""
                return Mock()

        definition = DslDefinition(metadata)
        assert definition.metadata.format == "dsl"

    def test_yaml_format_definition(self) -> None:
        """Test definition with YAML format metadata."""
        metadata = WorkloadMetadata(
            name="yaml-agent",
            description="A YAML-based agent",
            source_path=Path("/agents/agent.yaml"),
            format="yaml",
        )

        class YamlDefinition(WorkloadDefinition):
            """YAML-specific definition."""

            def create_workload(
                self,
                model_factory: "ModelFactory",  # noqa: ARG002
                tool_provider: "ToolProvider",  # noqa: ARG002
                system_context: "SystemContext",  # noqa: ARG002
                session_service: "BaseSessionService",  # noqa: ARG002
            ) -> "Workload":
                """Create YAML workload."""
                return Mock()

        definition = YamlDefinition(metadata)
        assert definition.metadata.format == "yaml"

    def test_python_format_definition(self) -> None:
        """Test definition with Python format metadata."""
        metadata = WorkloadMetadata(
            name="python-agent",
            description="A Python-based agent",
            source_path=Path("/agents/python_agent/__init__.py"),
            format="python",
        )

        class PythonDefinition(WorkloadDefinition):
            """Python-specific definition."""

            def create_workload(
                self,
                model_factory: "ModelFactory",  # noqa: ARG002
                tool_provider: "ToolProvider",  # noqa: ARG002
                system_context: "SystemContext",  # noqa: ARG002
                session_service: "BaseSessionService",  # noqa: ARG002
            ) -> "Workload":
                """Create Python workload."""
                return Mock()

        definition = PythonDefinition(metadata)
        assert definition.metadata.format == "python"
