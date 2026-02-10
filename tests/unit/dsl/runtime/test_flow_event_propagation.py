"""Unit tests for flow execution event propagation.

Test that _execute_flow, run_async, and run_flow yield all events
from contained operations (agent runs, LLM calls, etc.).
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.dsl.runtime.events import FlowEvent, LlmCallEvent, LlmResponseEvent

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.dsl_agent_factory import DslAgentFactory


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
    """Create a mock BaseSessionService with async methods."""
    service = MagicMock()
    service.get_session = AsyncMock(return_value=None)
    service.create_session = AsyncMock()
    return service


@pytest.fixture
def mock_agent_factory() -> "DslAgentFactory":
    """Create a mock DslAgentFactory."""
    factory = MagicMock()
    factory.create_agent = AsyncMock()
    factory.close = AsyncMock()
    return factory


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
    """Create a mock Content with text parts."""
    content = MagicMock()
    part = MagicMock()
    part.text = "test input"
    content.parts = [part]
    return content


def create_mock_adk_event(
    *,
    is_final: bool = False,
    text: str | None = None,
) -> MagicMock:
    """Create a mock ADK Event.

    Args:
        is_final: Whether this is the final response event.
        text: Optional text content for the event.

    Returns:
        Mock event with configured properties.

    """
    event = MagicMock()
    event.is_final_response.return_value = is_final

    if is_final and text is not None:
        event.content = MagicMock()
        part = MagicMock()
        part.text = text
        event.content.parts = [part]
    elif is_final:
        event.content = MagicMock()
        event.content.parts = []
    else:
        event.content = None

    return event


class TestExecuteFlowIsAsyncGenerator:
    """Test _execute_flow is an async generator."""

    @pytest.mark.asyncio
    async def test_execute_flow_is_async_generator(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """_execute_flow returns an async generator."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                _ = ctx
                # Empty generator for this test
                return
                yield  # Makes this an async generator

        workflow = TestWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        result = workflow._execute_flow("main", mock_session, mock_content)  # noqa: SLF001
        assert hasattr(result, "__anext__")

    @pytest.mark.asyncio
    async def test_execute_flow_yields_events_from_flow_method(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """_execute_flow yields events from the flow method."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_event1 = create_mock_adk_event(is_final=False)
        mock_event2 = create_mock_adk_event(is_final=True, text="done")

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                _ = ctx
                yield mock_event1
                yield mock_event2

        workflow = TestWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        events = [
            event
            async for event in workflow._execute_flow(  # noqa: SLF001
                "main",
                mock_session,
                mock_content,
            )
        ]

        assert len(events) == 2
        assert events[0] is mock_event1
        assert events[1] is mock_event2

    @pytest.mark.asyncio
    async def test_execute_flow_raises_for_unknown_flow(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """_execute_flow raises ValueError for unknown flow."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        with pytest.raises(ValueError, match="not found"):
            async for _ in workflow._execute_flow(  # noqa: SLF001
                "nonexistent",
                mock_session,
                mock_content,
            ):
                pass


class TestRunAsyncYieldsFlowEvents:
    """Test run_async yields events for both flow and agent entry points."""

    @pytest.mark.asyncio
    async def test_run_async_yields_events_for_flow_entry_point(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """run_async yields events when entry point is a flow."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_event = create_mock_adk_event(is_final=True, text="result")

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                _ = ctx
                yield mock_event

        workflow = TestWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        events = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert len(events) == 1
        assert events[0] is mock_event

    @pytest.mark.asyncio
    async def test_run_async_yields_events_for_agent_entry_point(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """run_async yields events when entry point is an agent."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_event = create_mock_adk_event(is_final=True, text="agent result")

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"default": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock _execute_agent to yield events
        async def mock_execute_agent(
            name: str,  # noqa: ARG001
            session: "Session",  # noqa: ARG001
            message: "Content | None",  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            yield mock_event

        workflow._execute_agent = mock_execute_agent  # noqa: SLF001

        events = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert len(events) == 1
        assert events[0] is mock_event


class TestRunFlowYieldsEvents:
    """Test run_flow method yields events from nested flows."""

    @pytest.mark.asyncio
    async def test_run_flow_is_async_generator(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_flow returns an async generator."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012

            async def flow_nested(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                _ = ctx
                return
                yield

        workflow = TestWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        result = workflow.run_flow("nested")
        assert hasattr(result, "__anext__")

    @pytest.mark.asyncio
    async def test_run_flow_yields_events_from_nested_flow(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_flow yields events from the nested flow method."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        llm_call_event = LlmCallEvent(
            prompt_name="test_prompt",
            model="gpt-4",
            prompt_text="Hello",
        )
        llm_response_event = LlmResponseEvent(
            prompt_name="test_prompt",
            content="World",
        )

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012

            async def flow_nested(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                _ = ctx
                yield llm_call_event
                yield llm_response_event

        workflow = TestWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        events = [event async for event in workflow.run_flow("nested")]

        assert len(events) == 2
        assert events[0] is llm_call_event
        assert events[1] is llm_response_event

    @pytest.mark.asyncio
    async def test_run_flow_raises_for_unknown_flow(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_flow raises ValueError for unknown flow."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        with pytest.raises(ValueError, match="not found"):
            async for _ in workflow.run_flow("nonexistent"):
                pass


class TestContextRunFlowYieldsEvents:
    """Test WorkflowContext.run_flow yields events."""

    @pytest.mark.asyncio
    async def test_context_run_flow_is_async_generator(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """WorkflowContext.run_flow returns an async generator."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012

            async def flow_test(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                _ = ctx
                return
                yield

        workflow = TestWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = WorkflowContext(workflow=workflow)

        result = ctx.run_flow("test")
        assert hasattr(result, "__anext__")

    @pytest.mark.asyncio
    async def test_context_run_flow_yields_events_from_workflow(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """WorkflowContext.run_flow re-yields events from workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        llm_event = LlmResponseEvent(
            prompt_name="test",
            content="result",
        )

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012

            async def flow_test(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                _ = ctx
                yield llm_event

        workflow = TestWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = WorkflowContext(workflow=workflow)

        events = [event async for event in ctx.run_flow("test")]

        assert len(events) == 1
        assert events[0] is llm_event


class TestSequentialAgentsYieldInterleavedEvents:
    """Test that sequential agent runs yield their events in order."""

    @pytest.mark.asyncio
    async def test_flow_with_sequential_agents_yields_interleaved_events(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Flow method calling multiple agents yields all events in order."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        agent1_event1 = create_mock_adk_event(is_final=False)
        agent1_event1.source = "agent1"
        agent1_event2 = create_mock_adk_event(is_final=True, text="result1")
        agent1_event2.source = "agent1"

        agent2_event1 = create_mock_adk_event(is_final=False)
        agent2_event1.source = "agent2"
        agent2_event2 = create_mock_adk_event(is_final=True, text="result2")
        agent2_event2.source = "agent2"

        class TestWorkflow(DslAgentWorkflow):
            _agents = {  # noqa: RUF012
                "agent1": {"instruction": "first"},
                "agent2": {"instruction": "second"},
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                # Simulate running agent1 then agent2
                async for event in ctx.run_agent("agent1", "input1"):
                    yield event
                async for event in ctx.run_agent("agent2", "input2"):
                    yield event

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock run_agent to return different events based on agent name
        call_count = 0

        async def mock_run_agent(
            agent_name: str,
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            nonlocal call_count
            if agent_name == "agent1":
                yield agent1_event1
                yield agent1_event2
            else:
                yield agent2_event1
                yield agent2_event2
            call_count += 1

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        events = [
            event
            async for event in workflow._execute_flow(  # noqa: SLF001
                "main",
                mock_session,
                mock_content,
            )
        ]

        assert len(events) == 4
        # Events should be in order: agent1's events then agent2's events
        assert events[0].source == "agent1"
        assert events[1].source == "agent1"
        assert events[2].source == "agent2"
        assert events[3].source == "agent2"


class TestMixedFlowYieldsCorrectEventSequence:
    """Test that flows with agents and LLM calls yield correct event sequence."""

    @pytest.mark.asyncio
    async def test_flow_with_agent_and_llm_call_yields_all_events(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Flow with agent run and LLM call yields all events in order."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        # Agent events
        agent_event = create_mock_adk_event(is_final=True, text="agent_result")

        # LLM events
        llm_call_event = LlmCallEvent(
            prompt_name="summarize",
            model="gpt-4",
            prompt_text="Summarize: agent_result",
        )
        llm_response_event = LlmResponseEvent(
            prompt_name="summarize",
            content="Summary",
        )

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"analyzer": {"instruction": "analyze"}}  # noqa: RUF012

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                # Run agent first
                async for event in ctx.run_agent("analyzer", "input"):
                    yield event
                # Then call LLM
                async for event in ctx.call_llm("summarize"):
                    yield event

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock run_agent
        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            yield agent_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        # We also need to mock the context's call_llm method
        async def patched_execute_flow(
            flow_name: str,
            session: "Session",  # noqa: ARG001
            message: "Content | None",
        ) -> AsyncGenerator["Event | FlowEvent", None]:
            flow_method = getattr(workflow, f"flow_{flow_name}", None)
            if flow_method is None:
                msg = f"Flow '{flow_name}' not found"
                raise ValueError(msg)

            input_text = workflow._extract_message_text(message)  # noqa: SLF001
            ctx = workflow.create_context(input_prompt=input_text)

            # Mock call_llm on context
            async def mock_call_llm(
                prompt_name: str,  # noqa: ARG001
                *args: object,  # noqa: ARG001
                model: str | None = None,  # noqa: ARG001
            ) -> AsyncGenerator[FlowEvent, None]:
                yield llm_call_event
                yield llm_response_event

            ctx.call_llm = mock_call_llm  # type: ignore[method-assign]

            async for event in flow_method(ctx):
                yield event

        workflow._execute_flow = patched_execute_flow  # noqa: SLF001

        events = [
            event
            async for event in workflow._execute_flow(  # noqa: SLF001
                "main",
                mock_session,
                mock_content,
            )
        ]

        assert len(events) == 3
        # First should be agent event
        assert events[0] is agent_event
        # Then LLM events
        assert events[1] is llm_call_event
        assert events[2] is llm_response_event


class TestExecuteFlowCreatesContext:
    """Test that _execute_flow creates proper context."""

    @pytest.mark.asyncio
    async def test_execute_flow_creates_context_with_input_prompt(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """_execute_flow creates context with input_prompt from message."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        captured_ctx: WorkflowContext | None = None

        class TestWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                nonlocal captured_ctx
                captured_ctx = ctx
                return
                yield

        workflow = TestWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Consume the generator
        _ = [
            event
            async for event in workflow._execute_flow(  # noqa: SLF001
                "main",
                mock_session,
                mock_content,
            )
        ]

        assert captured_ctx is not None
        assert captured_ctx.vars["input_prompt"] == "test input"
