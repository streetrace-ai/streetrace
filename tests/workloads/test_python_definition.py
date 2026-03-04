"""Tests for PythonWorkloadDefinition class."""

from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, override
from unittest.mock import MagicMock

import pytest

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.python_definition import PythonWorkloadDefinition


class MockAgent(StreetRaceAgent):
    """Mock agent for testing."""

    @override
    def get_agent_card(self) -> MagicMock:
        """Provide a mock agent card."""
        return MagicMock(name="MockAgent", description="A mock agent")

    @override
    async def create_agent(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
    ) -> "BaseAgent":
        """Create a mock agent."""
        return MagicMock()


class TestPythonWorkloadDefinitionRequiredParameters:
    """Test that PythonWorkloadDefinition requires all parameters."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="test-python-workload",
            description="A test Python workload",
            source_path=Path("/test/agent"),
            format="python",
        )

    @pytest.fixture
    def sample_agent_class(self) -> type[StreetRaceAgent]:
        """Create a sample agent class for testing."""
        return MockAgent

    @pytest.fixture
    def sample_module(self) -> ModuleType:
        """Create a sample module for testing."""
        module = ModuleType("test_agent_module")
        module.__file__ = "/test/agent/agent.py"
        return module

    def test_requires_metadata_parameter(
        self,
        sample_agent_class: type[StreetRaceAgent],
        sample_module: ModuleType,
    ) -> None:
        """Test that metadata parameter is required."""
        from streetrace.workloads.python_definition import PythonWorkloadDefinition

        with pytest.raises(TypeError):
            PythonWorkloadDefinition(  # type: ignore[call-arg]
                agent_class=sample_agent_class,
                module=sample_module,
            )

    def test_requires_agent_class_parameter(
        self,
        sample_metadata: WorkloadMetadata,
        sample_module: ModuleType,
    ) -> None:
        """Test that agent_class parameter is required."""
        from streetrace.workloads.python_definition import PythonWorkloadDefinition

        with pytest.raises(TypeError):
            PythonWorkloadDefinition(  # type: ignore[call-arg]
                metadata=sample_metadata,
                module=sample_module,
            )

    def test_requires_module_parameter(
        self,
        sample_metadata: WorkloadMetadata,
        sample_agent_class: type[StreetRaceAgent],
    ) -> None:
        """Test that module parameter is required."""
        from streetrace.workloads.python_definition import PythonWorkloadDefinition

        with pytest.raises(TypeError):
            PythonWorkloadDefinition(  # type: ignore[call-arg]
                metadata=sample_metadata,
                agent_class=sample_agent_class,
            )

    def test_can_create_with_all_required_parameters(
        self,
        sample_metadata: WorkloadMetadata,
        sample_agent_class: type[StreetRaceAgent],
        sample_module: ModuleType,
    ) -> None:
        """Test that definition can be created with all required parameters."""
        from streetrace.workloads.python_definition import PythonWorkloadDefinition

        definition = PythonWorkloadDefinition(
            metadata=sample_metadata,
            agent_class=sample_agent_class,
            module=sample_module,
        )

        assert definition is not None
        assert definition.metadata is sample_metadata
        assert definition.agent_class is sample_agent_class
        assert definition.module is sample_module


class TestPythonWorkloadDefinitionProperties:
    """Test PythonWorkloadDefinition properties."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="python-workflow",
            description="Test Python workflow description",
            source_path=Path("/path/to/agent"),
            format="python",
        )

    @pytest.fixture
    def sample_agent_class(self) -> type[StreetRaceAgent]:
        """Create a sample agent class for testing."""
        return MockAgent

    @pytest.fixture
    def sample_module(self) -> ModuleType:
        """Create a sample module for testing."""
        module = ModuleType("my_agent_module")
        module.__file__ = "/path/to/agent/agent.py"
        return module

    @pytest.fixture
    def definition(
        self,
        sample_metadata: WorkloadMetadata,
        sample_agent_class: type[StreetRaceAgent],
        sample_module: ModuleType,
    ) -> "PythonWorkloadDefinition":
        """Create a PythonWorkloadDefinition instance for testing."""
        from streetrace.workloads.python_definition import PythonWorkloadDefinition

        return PythonWorkloadDefinition(
            metadata=sample_metadata,
            agent_class=sample_agent_class,
            module=sample_module,
        )

    def test_agent_class_property_returns_correct_type(
        self,
        definition: "PythonWorkloadDefinition",
        sample_agent_class: type[StreetRaceAgent],
    ) -> None:
        """Test that agent_class property returns the correct type."""
        assert definition.agent_class is sample_agent_class
        assert issubclass(definition.agent_class, StreetRaceAgent)

    def test_module_property_returns_correct_type(
        self,
        definition: "PythonWorkloadDefinition",
        sample_module: ModuleType,
    ) -> None:
        """Test that module property returns the correct type."""
        assert definition.module is sample_module
        assert isinstance(definition.module, ModuleType)

    def test_agent_class_property_is_read_only(
        self,
        definition: "PythonWorkloadDefinition",
    ) -> None:
        """Test that agent_class property cannot be set."""
        with pytest.raises(AttributeError):
            definition.agent_class = MagicMock()  # type: ignore[misc]

    def test_module_property_is_read_only(
        self,
        definition: "PythonWorkloadDefinition",
    ) -> None:
        """Test that module property cannot be set."""
        with pytest.raises(AttributeError):
            definition.module = MagicMock()  # type: ignore[misc]

    def test_metadata_property_returns_metadata(
        self,
        definition: "PythonWorkloadDefinition",
        sample_metadata: WorkloadMetadata,
    ) -> None:
        """Test that metadata property returns the metadata."""
        assert definition.metadata is sample_metadata

    def test_name_property_delegates_to_metadata(
        self, definition: "PythonWorkloadDefinition",
    ) -> None:
        """Test that name property returns metadata.name."""
        assert definition.name == "python-workflow"
        assert definition.name == definition.metadata.name


class TestPythonWorkloadDefinitionCreateWorkload:
    """Test PythonWorkloadDefinition.create_workload() method."""

    @pytest.fixture
    def sample_metadata(self) -> WorkloadMetadata:
        """Create sample metadata for testing."""
        return WorkloadMetadata(
            name="test-workload",
            description="Test workload",
            source_path=Path("/test/workload"),
            format="python",
        )

    @pytest.fixture
    def sample_agent_class(self) -> type[StreetRaceAgent]:
        """Create a sample agent class for testing."""
        return MockAgent

    @pytest.fixture
    def sample_module(self) -> ModuleType:
        """Create a sample module for testing."""
        module = ModuleType("workload_module")
        module.__file__ = "/test/workload/agent.py"
        return module

    @pytest.fixture
    def definition(
        self,
        sample_metadata: WorkloadMetadata,
        sample_agent_class: type[StreetRaceAgent],
        sample_module: ModuleType,
    ) -> "PythonWorkloadDefinition":
        """Create a PythonWorkloadDefinition instance for testing."""
        from streetrace.workloads.python_definition import PythonWorkloadDefinition

        return PythonWorkloadDefinition(
            metadata=sample_metadata,
            agent_class=sample_agent_class,
            module=sample_module,
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
        definition: "PythonWorkloadDefinition",
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
        definition: "PythonWorkloadDefinition",
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

    def test_create_workload_creates_agent_instance(
        self,
        definition: "PythonWorkloadDefinition",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that create_workload creates an agent from agent_class."""
        workload = definition.create_workload(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # The agent definition should be an instance of the agent class
        assert isinstance(workload._agent_def, MockAgent)  # noqa: SLF001


class TestPythonWorkloadDefinitionInheritance:
    """Test PythonWorkloadDefinition inheritance from WorkloadDefinition."""

    def test_inherits_from_workload_definition(self) -> None:
        """Test that PythonWorkloadDefinition inherits from WorkloadDefinition."""
        from streetrace.workloads.definition import WorkloadDefinition
        from streetrace.workloads.python_definition import PythonWorkloadDefinition

        assert issubclass(PythonWorkloadDefinition, WorkloadDefinition)

    def test_is_not_abstract(self) -> None:
        """Test that PythonWorkloadDefinition is concrete (not abstract)."""
        from streetrace.workloads.python_definition import PythonWorkloadDefinition

        metadata = WorkloadMetadata(
            name="test",
            description="test",
            source_path=Path("/test"),
            format="python",
        )

        module = ModuleType("test_module")

        # Should not raise - it's concrete
        definition = PythonWorkloadDefinition(
            metadata=metadata,
            agent_class=MockAgent,
            module=module,
        )

        assert definition is not None
