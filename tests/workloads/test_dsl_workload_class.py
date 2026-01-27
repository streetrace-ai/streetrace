"""Tests for DslWorkload class.

These tests verify the DslWorkload runtime class that implements the
Workload protocol for executing DSL-based workflows.
"""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.workloads.dsl_agent_factory import DslAgentFactory
from streetrace.workloads.dsl_definition import DslWorkloadDefinition
from streetrace.workloads.dsl_workload import DslWorkload
from streetrace.workloads.metadata import WorkloadMetadata
from streetrace.workloads.protocol import Workload

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider


class SampleWorkflow(DslAgentWorkflow):
    """Sample workflow class for testing."""

    _models: ClassVar[dict[str, str]] = {"main": "test-model"}
    _prompts: ClassVar[dict[str, object]] = {
        "test": lambda _ctx: "Test instruction",
    }
    _tools: ClassVar[dict[str, object]] = {}
    _agents: ClassVar[dict[str, dict[str, object]]] = {
        "default": {"instruction": "test"},
    }


class TestDslWorkloadRequiredParameters:
    """Test that DslWorkload requires all constructor parameters."""

    @pytest.fixture
    def sample_definition(self) -> DslWorkloadDefinition:
        """Create sample DslWorkloadDefinition for testing."""
        metadata = WorkloadMetadata(
            name="test-workload",
            description="Test workload",
            source_path=Path("/test/workload.sr"),
            format="dsl",
        )
        return DslWorkloadDefinition(
            metadata=metadata,
            workflow_class=SampleWorkflow,
            source_map=[],
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

    def test_requires_definition_parameter(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that definition parameter is required."""
        with pytest.raises(TypeError):
            DslWorkload(  # type: ignore[call-arg]
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
                session_service=mock_session_service,
            )

    def test_requires_model_factory_parameter(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that model_factory parameter is required."""
        with pytest.raises(TypeError):
            DslWorkload(  # type: ignore[call-arg]
                definition=sample_definition,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
                session_service=mock_session_service,
            )

    def test_requires_tool_provider_parameter(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that tool_provider parameter is required."""
        with pytest.raises(TypeError):
            DslWorkload(  # type: ignore[call-arg]
                definition=sample_definition,
                model_factory=mock_model_factory,
                system_context=mock_system_context,
                session_service=mock_session_service,
            )

    def test_requires_system_context_parameter(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test that system_context parameter is required."""
        with pytest.raises(TypeError):
            DslWorkload(  # type: ignore[call-arg]
                definition=sample_definition,
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                session_service=mock_session_service,
            )

    def test_requires_session_service_parameter(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
    ) -> None:
        """Test that session_service parameter is required."""
        with pytest.raises(TypeError):
            DslWorkload(  # type: ignore[call-arg]
                definition=sample_definition,
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

    def test_can_create_with_all_parameters(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test workload can be created with all required parameters."""
        workload = DslWorkload(
            definition=sample_definition,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert workload is not None
        assert workload._definition is sample_definition  # noqa: SLF001
        assert workload._model_factory is mock_model_factory  # noqa: SLF001
        assert workload._tool_provider is mock_tool_provider  # noqa: SLF001
        assert workload._system_context is mock_system_context  # noqa: SLF001
        assert workload._session_service is mock_session_service  # noqa: SLF001


class TestDslWorkloadInit:
    """Test DslWorkload initialization behavior."""

    @pytest.fixture
    def sample_definition(self) -> DslWorkloadDefinition:
        """Create sample DslWorkloadDefinition for testing."""
        metadata = WorkloadMetadata(
            name="init-test-workload",
            description="Init test workload",
            source_path=Path("/test/init.sr"),
            format="dsl",
        )
        return DslWorkloadDefinition(
            metadata=metadata,
            workflow_class=SampleWorkflow,
            source_map=[],
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

    def test_workflow_instance_created_during_init(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test workflow instance is created during init."""
        workload = DslWorkload(
            definition=sample_definition,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert workload._workflow is not None  # noqa: SLF001
        assert isinstance(workload._workflow, DslAgentWorkflow)  # noqa: SLF001
        assert isinstance(workload._workflow, SampleWorkflow)  # noqa: SLF001

    def test_workflow_property_returns_workflow_instance(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test workflow property returns the workflow instance."""
        workload = DslWorkload(
            definition=sample_definition,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert workload.workflow is not None
        assert isinstance(workload.workflow, SampleWorkflow)

    def test_definition_property_returns_definition(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test definition property returns the definition."""
        workload = DslWorkload(
            definition=sample_definition,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert workload.definition is sample_definition


class TestDslWorkloadRunAsync:
    """Test DslWorkload.run_async() method."""

    @pytest.fixture
    def sample_definition(self) -> DslWorkloadDefinition:
        """Create sample DslWorkloadDefinition for testing."""
        metadata = WorkloadMetadata(
            name="run-test-workload",
            description="Run test workload",
            source_path=Path("/test/run.sr"),
            format="dsl",
        )
        return DslWorkloadDefinition(
            metadata=metadata,
            workflow_class=SampleWorkflow,
            source_map=[],
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

    @pytest.fixture
    def workload(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> DslWorkload:
        """Create a DslWorkload instance for testing."""
        return DslWorkload(
            definition=sample_definition,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

    @pytest.mark.asyncio
    async def test_run_async_delegates_to_workflow(
        self, workload: DslWorkload,
    ) -> None:
        """Test run_async delegates to workflow.run_async."""
        mock_session = MagicMock()
        mock_message = MagicMock()
        mock_event = MagicMock()

        # Create async generator that yields the mock event
        async def mock_run_async(
            session: object,  # noqa: ARG001
            message: object,  # noqa: ARG001
        ) -> None:
            yield mock_event

        # Patch the workflow's run_async method
        with patch.object(
            workload._workflow,  # noqa: SLF001
            "run_async",
            side_effect=mock_run_async,
        ):
            events = [
                event
                async for event in workload.run_async(mock_session, mock_message)
            ]

            assert len(events) == 1
            assert events[0] is mock_event


class TestDslWorkloadClose:
    """Test DslWorkload.close() method."""

    @pytest.fixture
    def sample_definition(self) -> DslWorkloadDefinition:
        """Create sample DslWorkloadDefinition for testing."""
        metadata = WorkloadMetadata(
            name="close-test-workload",
            description="Close test workload",
            source_path=Path("/test/close.sr"),
            format="dsl",
        )
        return DslWorkloadDefinition(
            metadata=metadata,
            workflow_class=SampleWorkflow,
            source_map=[],
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

    @pytest.fixture
    def workload(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> DslWorkload:
        """Create a DslWorkload instance for testing."""
        return DslWorkload(
            definition=sample_definition,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

    @pytest.mark.asyncio
    async def test_close_delegates_to_workflow(
        self, workload: DslWorkload,
    ) -> None:
        """Test close delegates to workflow.close."""
        mock_close = AsyncMock()
        with patch.object(
            workload._workflow,  # noqa: SLF001
            "close",
            mock_close,
        ):
            await workload.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_cleans_up_resources(
        self, workload: DslWorkload,
    ) -> None:
        """Test close cleans up resources properly."""
        # Just verify close doesn't raise
        await workload.close()


class TestDslWorkloadProtocolCompliance:
    """Test that DslWorkload satisfies the Workload protocol."""

    @pytest.fixture
    def sample_definition(self) -> DslWorkloadDefinition:
        """Create sample DslWorkloadDefinition for testing."""
        metadata = WorkloadMetadata(
            name="protocol-test",
            description="Protocol test",
            source_path=Path("/test/protocol.sr"),
            format="dsl",
        )
        return DslWorkloadDefinition(
            metadata=metadata,
            workflow_class=SampleWorkflow,
            source_map=[],
        )

    def test_satisfies_workload_protocol(
        self,
        sample_definition: DslWorkloadDefinition,
    ) -> None:
        """Test DslWorkload satisfies the Workload protocol."""
        workload = DslWorkload(
            definition=sample_definition,
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            session_service=MagicMock(),
        )

        assert isinstance(workload, Workload)

    def test_has_run_async_method(
        self,
        sample_definition: DslWorkloadDefinition,
    ) -> None:
        """Test DslWorkload has run_async method."""
        workload = DslWorkload(
            definition=sample_definition,
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            session_service=MagicMock(),
        )

        assert hasattr(workload, "run_async")
        assert callable(workload.run_async)

    def test_has_close_method(
        self,
        sample_definition: DslWorkloadDefinition,
    ) -> None:
        """Test DslWorkload has close method."""
        workload = DslWorkload(
            definition=sample_definition,
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            session_service=MagicMock(),
        )

        assert hasattr(workload, "close")
        assert callable(workload.close)


class TestDslWorkloadAgentFactory:
    """Test DslWorkload integration with DslAgentFactory."""

    @pytest.fixture
    def sample_definition(self) -> DslWorkloadDefinition:
        """Create sample DslWorkloadDefinition for testing."""
        metadata = WorkloadMetadata(
            name="factory-test",
            description="Factory test",
            source_path=Path("/test/factory.sr"),
            format="dsl",
        )
        return DslWorkloadDefinition(
            metadata=metadata,
            workflow_class=SampleWorkflow,
            source_map=[],
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

    def test_workflow_receives_agent_factory(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test workflow instance receives agent_factory."""
        workload = DslWorkload(
            definition=sample_definition,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # The workflow should have _agent_factory set
        assert workload._workflow._agent_factory is not None  # noqa: SLF001
        assert isinstance(
            workload._workflow._agent_factory,  # noqa: SLF001
            DslAgentFactory,
        )

    def test_agent_factory_matches_definition(
        self,
        sample_definition: DslWorkloadDefinition,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Test agent_factory is the same as definition.agent_factory."""
        workload = DslWorkload(
            definition=sample_definition,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # The factory should be from the definition
        assert workload._workflow._agent_factory is sample_definition.agent_factory  # noqa: SLF001
