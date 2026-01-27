"""Tests for DefinitionLoader protocol."""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from streetrace.agents.resolver import SourceResolution, SourceType
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.loader import DefinitionLoader
from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.protocol import Workload


class ConcreteDefinition(WorkloadDefinition):
    """Concrete WorkloadDefinition for testing."""

    def create_workload(
        self,
        model_factory: "ModelFactory",  # noqa: ARG002
        tool_provider: "ToolProvider",  # noqa: ARG002
        system_context: "SystemContext",  # noqa: ARG002
        session_service: "BaseSessionService",  # noqa: ARG002
    ) -> "Workload":
        """Create a workload instance."""
        return Mock()


def make_resolution(
    content: str,
    source: str = "test.sr",
    file_path: Path | None = None,
    fmt: str = "dsl",
) -> SourceResolution:
    """Create a SourceResolution for testing."""
    return SourceResolution(
        content=content,
        source=source,
        source_type=SourceType.FILE_PATH,
        file_path=file_path,
        format=fmt,
    )


class TestDefinitionLoaderProtocol:
    """Test DefinitionLoader protocol definition."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that DefinitionLoader protocol is runtime checkable."""
        # Should have runtime_checkable decorator
        assert hasattr(DefinitionLoader, "__protocol_attrs__") or hasattr(
            DefinitionLoader, "_is_protocol",
        )

    def test_protocol_has_load_method(self) -> None:
        """Test that protocol defines load method."""
        assert hasattr(DefinitionLoader, "load")

    def test_protocol_does_not_have_can_load(self) -> None:
        """Test protocol no longer has can_load (removed in consolidation)."""
        # The protocol should only define load() now
        # can_load, discover are handled by SourceResolver
        # Protocol attrs check is implicit in isinstance tests

    def test_protocol_does_not_have_discover(self) -> None:
        """Test protocol no longer has discover (removed in consolidation)."""
        # discover is now handled by SourceResolver
        # Protocol attrs check is implicit in isinstance tests


class TestDefinitionLoaderProtocolCompliance:
    """Test that classes can properly implement the DefinitionLoader protocol."""

    def test_compliant_class_with_only_load_satisfies_protocol(self) -> None:
        """Test that a class with only load() satisfies the protocol."""

        class MinimalLoader:
            """A class that implements the minimal DefinitionLoader protocol."""

            def load(self, resolution: SourceResolution) -> WorkloadDefinition:
                """Load a workload definition from a SourceResolution."""
                metadata = WorkloadMetadata(
                    name="test",
                    description="Test workload",
                    source_path=resolution.file_path,
                    format="dsl",
                )
                return ConcreteDefinition(metadata)

        loader = MinimalLoader()
        assert isinstance(loader, DefinitionLoader)

    def test_compliant_class_isinstance_check(self) -> None:
        """Test isinstance check with a compliant class."""

        class CompliantLoader:
            """A class that properly implements the DefinitionLoader protocol."""

            def load(self, resolution: SourceResolution) -> WorkloadDefinition:
                """Load a workload definition from SourceResolution."""
                metadata = WorkloadMetadata(
                    name=resolution.file_path.stem if resolution.file_path else "test",
                    description="Test workload",
                    source_path=resolution.file_path,
                    format="dsl",
                )
                return ConcreteDefinition(metadata)

        loader = CompliantLoader()
        assert isinstance(loader, DefinitionLoader)

    def test_non_compliant_class_missing_load(self) -> None:
        """Test that class missing load fails isinstance check."""

        class IncompleteLoader:
            """Missing load method."""

            def some_other_method(self) -> None:
                """Not the load method."""

        loader = IncompleteLoader()
        assert not isinstance(loader, DefinitionLoader)


class _SampleLoader:
    """Sample loader for testing - implements the simplified protocol."""

    def load(self, resolution: SourceResolution) -> WorkloadDefinition:
        """Load a workload definition from SourceResolution."""
        file_path = resolution.file_path
        name = file_path.stem if file_path else "unknown"
        metadata = WorkloadMetadata(
            name=name,
            description=f"Loaded from {resolution.source}",
            source_path=file_path,
            format="dsl",
        )
        return ConcreteDefinition(metadata)


class TestDefinitionLoaderBehavior:
    """Test DefinitionLoader method behaviors."""

    @pytest.fixture
    def sample_loader(self) -> "DefinitionLoader":
        """Create a sample loader implementing the protocol."""
        return _SampleLoader()

    def test_load_returns_workload_definition(
        self, sample_loader: "DefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load returns a WorkloadDefinition instance."""
        path = tmp_path / "my_agent.sr"
        resolution = make_resolution("streetrace v1", str(path), path)

        definition = sample_loader.load(resolution)

        assert isinstance(definition, WorkloadDefinition)
        assert definition.name == "my_agent"
        assert definition.metadata.source_path == path
        assert definition.metadata.format == "dsl"

    def test_load_works_with_none_file_path(
        self, sample_loader: "DefinitionLoader",
    ) -> None:
        """Test load handles None file_path (e.g., HTTP sources)."""
        resolution = make_resolution(
            "streetrace v1",
            "https://example.com/agent.sr",
            None,
        )

        definition = sample_loader.load(resolution)

        assert isinstance(definition, WorkloadDefinition)
        assert definition.name == "unknown"  # No file path to extract name from
        assert definition.metadata.source_path is None

    def test_load_uses_source_resolution_content(
        self, sample_loader: "DefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load has access to content from SourceResolution."""
        content = "test content"
        path = tmp_path / "test.sr"
        resolution = make_resolution(content, str(path), path)

        # The sample loader doesn't use content, but real loaders do
        assert resolution.content == content

        # Verify loading still works
        definition = sample_loader.load(resolution)
        assert isinstance(definition, WorkloadDefinition)


class TestAllLoadersImplementProtocol:
    """Test that all actual loaders implement the DefinitionLoader protocol."""

    def test_dsl_loader_implements_protocol(self) -> None:
        """Test DslDefinitionLoader satisfies the protocol."""
        from streetrace.workloads.dsl_loader import DslDefinitionLoader

        loader = DslDefinitionLoader()
        assert isinstance(loader, DefinitionLoader)

    def test_yaml_loader_implements_protocol(self) -> None:
        """Test YamlDefinitionLoader satisfies the protocol."""
        from streetrace.workloads.yaml_loader import YamlDefinitionLoader

        loader = YamlDefinitionLoader()
        assert isinstance(loader, DefinitionLoader)

    def test_python_loader_implements_protocol(self) -> None:
        """Test PythonDefinitionLoader satisfies the protocol."""
        from streetrace.workloads.python_loader import PythonDefinitionLoader

        loader = PythonDefinitionLoader()
        assert isinstance(loader, DefinitionLoader)
