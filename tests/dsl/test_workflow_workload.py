"""Tests for DslAgentWorkflow as Workload.

Test that DslAgentWorkflow implements the Workload protocol and properly
delegates agent creation to DslStreetRaceAgent via composition.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.agents.dsl_agent_loader import DslStreetRaceAgent
    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider


@pytest.fixture
def mock_model_factory() -> "ModelFactory":
    """Create a mock ModelFactory."""
    factory = MagicMock()
    factory.get_current_model.return_value = MagicMock()
    factory.get_llm_interface.return_value = MagicMock()
    return factory


@pytest.fixture
def mock_tool_provider() -> "ToolProvider":
    """Create a mock ToolProvider."""
    return MagicMock()


@pytest.fixture
def mock_system_context() -> "SystemContext":
    """Create a mock SystemContext."""
    return MagicMock()


@pytest.fixture
def mock_session_service() -> "BaseSessionService":
    """Create a mock BaseSessionService."""
    return MagicMock()


@pytest.fixture
def mock_dsl_agent() -> "DslStreetRaceAgent":
    """Create a mock DslStreetRaceAgent."""
    agent = MagicMock()
    agent._create_agent_from_def = AsyncMock()  # noqa: SLF001
    agent.close = AsyncMock()
    return agent


@pytest.fixture
def mock_session() -> "Session":
    """Create a mock Session for testing."""
    session = MagicMock()
    session.app_name = "test-app"
    session.user_id = "test-user"
    session.id = "test-session-id"
    return session


@pytest.fixture
def mock_content() -> "Content":
    """Create a mock Content for testing."""
    return MagicMock()


class TestDslAgentWorkflowInstantiation:
    """Test cases for DslAgentWorkflow instantiation."""

    def test_init_without_dependencies_for_backward_compat(self) -> None:
        """DslAgentWorkflow can be instantiated without dependencies."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow()

        assert workflow._agent_def is None  # noqa: SLF001
        assert workflow._model_factory is None  # noqa: SLF001
        assert workflow._tool_provider is None  # noqa: SLF001
        assert workflow._system_context is None  # noqa: SLF001
        assert workflow._session_service is None  # noqa: SLF001
        assert workflow._context is None  # noqa: SLF001
        assert workflow._created_agents == []  # noqa: SLF001

    def test_init_stores_all_dependencies(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """DslAgentWorkflow stores all provided dependencies."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert workflow._agent_def is mock_dsl_agent  # noqa: SLF001
        assert workflow._model_factory is mock_model_factory  # noqa: SLF001
        assert workflow._tool_provider is mock_tool_provider  # noqa: SLF001
        assert workflow._system_context is mock_system_context  # noqa: SLF001
        assert workflow._session_service is mock_session_service  # noqa: SLF001

    def test_init_created_agents_list_is_empty(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """DslAgentWorkflow initializes with empty created_agents list."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert workflow._created_agents == []  # noqa: SLF001


class TestDslAgentWorkflowEntryPoint:
    """Test cases for _determine_entry_point method."""

    def test_entry_point_dataclass_exists(self) -> None:
        """EntryPoint dataclass is defined in workflow module."""
        from streetrace.dsl.runtime.workflow import EntryPoint

        entry = EntryPoint(type="flow", name="main")
        assert entry.type == "flow"
        assert entry.name == "main"

    def test_determine_entry_point_returns_main_flow_when_exists(self) -> None:
        """_determine_entry_point returns flow entry point for 'main' flow."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"default": {}}  # noqa: RUF012

            async def flow_main(self, ctx: object) -> None:
                pass

        workflow = TestWorkflow()
        entry = workflow._determine_entry_point()  # noqa: SLF001

        assert entry.type == "flow"
        assert entry.name == "main"

    def test_determine_entry_point_returns_default_agent_when_no_main_flow(
        self,
    ) -> None:
        """_determine_entry_point returns default agent when no main flow."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"default": {}, "other": {}}  # noqa: RUF012

        workflow = TestWorkflow()
        entry = workflow._determine_entry_point()  # noqa: SLF001

        assert entry.type == "agent"
        assert entry.name == "default"

    def test_determine_entry_point_returns_first_agent_when_no_default(self) -> None:
        """_determine_entry_point returns first agent when no default."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"analyzer": {}, "writer": {}}  # noqa: RUF012

        workflow = TestWorkflow()

        with pytest.raises(ValueError, match="No entry point found"):
            workflow._determine_entry_point()  # noqa: SLF001

    def test_determine_entry_point_raises_when_no_entry_point(self) -> None:
        """_determine_entry_point raises ValueError when no entry point."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012

        workflow = TestWorkflow()

        with pytest.raises(ValueError, match="No entry point found"):
            workflow._determine_entry_point()  # noqa: SLF001


class TestDslAgentWorkflowCreateAgent:
    """Test cases for _create_agent method."""

    @pytest.mark.asyncio
    async def test_create_agent_delegates_to_dsl_streetrace_agent(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """_create_agent delegates to DslStreetRaceAgent._create_agent_from_def."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        # Create mock agent to be returned
        mock_base_agent = MagicMock()
        mock_dsl_agent._create_agent_from_def.return_value = mock_base_agent  # noqa: SLF001

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test_prompt"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        result = await workflow._create_agent("test_agent")  # noqa: SLF001

        mock_dsl_agent._create_agent_from_def.assert_called_once_with(  # noqa: SLF001
            "test_agent",
            {"instruction": "test_prompt"},
            mock_model_factory,
            mock_tool_provider,
            mock_system_context,
        )
        assert result is mock_base_agent

    @pytest.mark.asyncio
    async def test_create_agent_tracks_created_agent(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """_create_agent adds agent to _created_agents list."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_dsl_agent._create_agent_from_def.return_value = mock_base_agent  # noqa: SLF001

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        await workflow._create_agent("test_agent")  # noqa: SLF001

        assert mock_base_agent in workflow._created_agents  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_create_agent_raises_when_not_initialized(self) -> None:
        """_create_agent raises ValueError when not properly initialized."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {}}  # noqa: RUF012

        workflow = TestWorkflow()

        with pytest.raises(ValueError, match="not properly initialized"):
            await workflow._create_agent("test_agent")  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_create_agent_raises_for_unknown_agent(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """_create_agent raises ValueError for unknown agent name."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"known_agent": {}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        with pytest.raises(ValueError, match="not found in workflow"):
            await workflow._create_agent("unknown_agent")  # noqa: SLF001


class TestDslAgentWorkflowClose:
    """Test cases for close method."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_created_agents(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """close() calls close on all created agents via agent_def."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_agent1 = MagicMock()
        mock_agent2 = MagicMock()
        mock_dsl_agent._create_agent_from_def.side_effect = [  # noqa: SLF001
            mock_agent1,
            mock_agent2,
        ]

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"agent1": {}, "agent2": {}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Create agents
        await workflow._create_agent("agent1")  # noqa: SLF001
        await workflow._create_agent("agent2")  # noqa: SLF001

        # Close workflow
        await workflow.close()

        # Verify close was called for both agents
        assert mock_dsl_agent.close.call_count == 2
        mock_dsl_agent.close.assert_any_call(mock_agent1)
        mock_dsl_agent.close.assert_any_call(mock_agent2)

    @pytest.mark.asyncio
    async def test_close_clears_created_agents_list(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """close() clears the _created_agents list."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_dsl_agent._create_agent_from_def.return_value = mock_base_agent  # noqa: SLF001

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        await workflow._create_agent("test_agent")  # noqa: SLF001
        assert len(workflow._created_agents) == 1  # noqa: SLF001

        await workflow.close()

        assert workflow._created_agents == []  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_close_works_without_agent_def(self) -> None:
        """close() works when no agent_def is set."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow()

        # Should not raise
        await workflow.close()

        assert workflow._created_agents == []  # noqa: SLF001


async def _mock_run_async_gen(
    events: list["Event"],
) -> AsyncGenerator["Event", None]:
    """Yield events for mocking."""
    for event in events:
        yield event


class TestDslAgentWorkflowRunAsync:
    """Test cases for run_async method."""

    @pytest.mark.asyncio
    async def test_run_async_yields_events_from_agent(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """run_async yields events from agent execution."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_dsl_agent._create_agent_from_def.return_value = mock_base_agent  # noqa: SLF001

        mock_event1 = MagicMock()
        mock_event2 = MagicMock()

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"default": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock the internal _execute_agent method
        async def mock_execute_agent(
            name: str,  # noqa: ARG001
            session: "Session",  # noqa: ARG001
            message: "Content | None",  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            yield mock_event1
            yield mock_event2

        workflow._execute_agent = mock_execute_agent  # noqa: SLF001

        events = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert len(events) == 2
        assert events[0] is mock_event1
        assert events[1] is mock_event2


class TestDslAgentWorkflowRunAgent:
    """Test cases for run_agent method."""

    @pytest.mark.asyncio
    async def test_run_agent_creates_agent_via_delegation(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_agent creates agent via _create_agent delegation."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_dsl_agent._create_agent_from_def.return_value = mock_base_agent  # noqa: SLF001

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"analyzer": {"instruction": "analyze"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock Runner to avoid actual execution
        mock_runner_instance = MagicMock()
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content = MagicMock()
        mock_event.content.parts = [MagicMock(text="result")]
        mock_runner_instance.run_async = MagicMock(
            return_value=_mock_run_async_gen([mock_event]),
        )

        # Mock InMemorySessionService with async create_session
        mock_session_service_instance = MagicMock()
        mock_session_service_instance.create_session = AsyncMock()

        with (
            patch(
                "streetrace.dsl.runtime.workflow.Runner",
                return_value=mock_runner_instance,
            ),
            patch(
                "streetrace.dsl.runtime.workflow.InMemorySessionService",
                return_value=mock_session_service_instance,
            ),
        ):
            result = await workflow.run_agent("analyzer", "analyze this")

        assert mock_dsl_agent._create_agent_from_def.called  # noqa: SLF001
        assert result == "result"

    @pytest.mark.asyncio
    async def test_run_agent_raises_without_session_service(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
    ) -> None:
        """run_agent raises ValueError without session_service."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"analyzer": {}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=None,  # No session service
        )

        with pytest.raises(ValueError, match="Session service not available"):
            await workflow.run_agent("analyzer")


class TestDslAgentWorkflowRunFlow:
    """Test cases for run_flow method."""

    @pytest.mark.asyncio
    async def test_run_flow_calls_flow_method(self) -> None:
        """run_flow calls the corresponding flow method."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012
            flow_called = False

            async def flow_test(self, ctx: object) -> str:  # noqa: ARG002
                self.flow_called = True
                return "flow_result"

        workflow = TestWorkflow()
        result = await workflow.run_flow("test")

        assert workflow.flow_called
        assert result == "flow_result"

    @pytest.mark.asyncio
    async def test_run_flow_raises_for_unknown_flow(self) -> None:
        """run_flow raises ValueError for unknown flow."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow()

        with pytest.raises(ValueError, match="not found"):
            await workflow.run_flow("nonexistent")


class TestWorkflowContextDelegation:
    """Test cases for WorkflowContext delegation to workflow."""

    def test_context_accepts_workflow_parameter(self) -> None:
        """WorkflowContext accepts workflow parameter in constructor."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow()
        ctx = WorkflowContext(workflow=workflow)

        assert ctx._workflow is workflow  # noqa: SLF001

    def test_context_without_workflow_for_backward_compat(self) -> None:
        """WorkflowContext works without workflow for backward compatibility."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext()

        assert ctx._workflow is None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_context_run_agent_delegates_to_workflow(
        self,
        mock_dsl_agent: "DslStreetRaceAgent",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """WorkflowContext.run_agent delegates to workflow.run_agent."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_dsl_agent._create_agent_from_def.return_value = mock_base_agent  # noqa: SLF001

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_definition=mock_dsl_agent,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock run_agent on workflow
        workflow.run_agent = AsyncMock(return_value="workflow_result")

        ctx = WorkflowContext(workflow=workflow)
        result = await ctx.run_agent("test_agent", "arg1", "arg2")

        workflow.run_agent.assert_called_once_with("test_agent", "arg1", "arg2")
        assert result == "workflow_result"

    @pytest.mark.asyncio
    async def test_context_run_agent_uses_fallback_without_workflow(self) -> None:
        """WorkflowContext.run_agent uses original implementation without workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext()
        ctx.set_agents(
            {
                "test_agent": {"instruction": "test"},
            },
        )
        ctx.set_models({"main": "test-model"})
        ctx.set_prompts({"test": lambda _: "test prompt"})

        # Without workflow, should use fallback implementation
        # which returns None for unknown agents
        result = await ctx.run_agent("nonexistent_agent")

        assert result is None


class TestCreateContextConnectsWorkflow:
    """Test cases for create_context connecting workflow reference."""

    def test_create_context_passes_workflow_reference(self) -> None:
        """create_context passes workflow reference to context."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _models = {"main": "test-model"}  # noqa: RUF012
            _prompts = {}  # noqa: RUF012
            _agents = {}  # noqa: RUF012

        workflow = TestWorkflow()
        ctx = workflow.create_context()

        assert ctx._workflow is workflow  # noqa: SLF001
