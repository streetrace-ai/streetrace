"""Integration tests for flow event yielding.

Test that DSL flows yield events correctly during execution, including:
- Single and multiple agent flows
- Direct LLM calls (call llm statements)
- Mixed flows with agents and LLM calls
- Nested flow calls
- End-to-end DSL compilation and execution
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streetrace.dsl.runtime.events import FlowEvent, LlmCallEvent, LlmResponseEvent
from streetrace.dsl.runtime.workflow import DslAgentWorkflow

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.dsl.runtime.context import WorkflowContext
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
    """Create a mock BaseSessionService."""
    return MagicMock()


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
    source: str | None = None,
) -> MagicMock:
    """Create a mock ADK Event.

    Args:
        is_final: Whether this is the final response event.
        text: Optional text content for the event.
        source: Optional source identifier for the event.

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

    if source:
        event.source = source

    return event


class TestSingleAgentFlowYieldsAllAdkEvents:
    """Test that a single agent flow yields all ADK events."""

    @pytest.mark.asyncio
    async def test_single_agent_yields_all_events(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Single agent flow yields all ADK events from execution."""
        # Create mock events that would be yielded by agent execution
        event1 = create_mock_adk_event(is_final=False)
        event2 = create_mock_adk_event(is_final=False)
        event3 = create_mock_adk_event(is_final=True, text="final result")

        class SingleAgentWorkflow(DslAgentWorkflow):
            _agents = {"analyzer": {"instruction": "test"}}  # noqa: RUF012

            async def flow_main(
                self,
                ctx: "WorkflowContext",
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.run_agent("analyzer", ctx.vars["input_prompt"]):
                    yield event

        workflow = SingleAgentWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock run_agent to yield our events
        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            yield event1
            yield event2
            yield event3

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        events = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert len(events) == 3
        assert events[0] is event1
        assert events[1] is event2
        assert events[2] is event3

    @pytest.mark.asyncio
    async def test_final_response_captured_correctly(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Verify final response is captured via get_last_result()."""
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text="analysis complete")

        class CaptureResultWorkflow(DslAgentWorkflow):
            _agents = {"analyzer": {"instruction": "test"}}  # noqa: RUF012

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.run_agent("analyzer"):
                    yield event
                ctx.vars["result"] = ctx.get_last_result()

        workflow = CaptureResultWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            ctx = workflow._context  # noqa: SLF001
            if ctx is not None:
                ctx._last_call_result = "analysis complete"  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        # Consume generator to execute flow
        _ = [event async for event in workflow.run_async(mock_session, mock_content)]

        # The context should have captured the result
        assert workflow._context is not None  # noqa: SLF001
        assert workflow._context.vars.get("result") == "analysis complete"  # noqa: SLF001


class TestMultipleAgentFlowYieldsInterleavedEvents:
    """Test that multiple agent flow yields interleaved events."""

    @pytest.mark.asyncio
    async def test_sequential_agents_yield_in_order(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Multiple sequential agents yield events in execution order."""
        from streetrace.dsl.runtime.context import WorkflowContext

        # Events for first agent
        agent1_event1 = create_mock_adk_event(is_final=False, source="agent1")
        agent1_event2 = create_mock_adk_event(
            is_final=True,
            text="result1",
            source="agent1",
        )

        # Events for second agent
        agent2_event1 = create_mock_adk_event(is_final=False, source="agent2")
        agent2_event2 = create_mock_adk_event(
            is_final=True,
            text="result2",
            source="agent2",
        )

        class MultiAgentWorkflow(DslAgentWorkflow):
            _agents = {  # noqa: RUF012
                "analyzer": {"instruction": "analyze"},
                "summarizer": {"instruction": "summarize"},
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                # First agent run
                async for event in ctx.run_agent("analyzer", ctx.vars["input_prompt"]):
                    yield event
                ctx.vars["analysis"] = ctx.get_last_result()

                # Second agent run
                async for event in ctx.run_agent("summarizer", ctx.vars["analysis"]):
                    yield event
                ctx.vars["summary"] = ctx.get_last_result()

        workflow = MultiAgentWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        call_count = 0

        async def mock_run_agent(
            agent_name: str,
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            nonlocal call_count
            ctx = workflow._context  # noqa: SLF001
            if agent_name == "analyzer":
                yield agent1_event1
                yield agent1_event2
                if ctx is not None:
                    ctx._last_call_result = "result1"  # noqa: SLF001
            else:
                yield agent2_event1
                yield agent2_event2
                if ctx is not None:
                    ctx._last_call_result = "result2"  # noqa: SLF001
            call_count += 1

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        events = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert len(events) == 4
        # Events from first agent (using getattr for source which is added to mock)
        assert getattr(events[0], "source", None) == "agent1"
        assert getattr(events[1], "source", None) == "agent1"
        # Events from second agent
        assert getattr(events[2], "source", None) == "agent2"
        assert getattr(events[3], "source", None) == "agent2"
        # Both agents were called
        assert call_count == 2


class TestFlowWithCallLlmYieldsFlowEvents:
    """Test that flow with call_llm yields LlmCallEvent and LlmResponseEvent."""

    @pytest.mark.asyncio
    async def test_call_llm_yields_call_and_response_events(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """call_llm statement yields LlmCallEvent and LlmResponseEvent."""
        from streetrace.dsl.runtime.context import WorkflowContext

        class CallLlmWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012
            _models = {"main": "test-model"}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "analyze_prompt": lambda ctx: (
                    f"Analyze: {ctx.vars.get('input_prompt', '')}"
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.call_llm("analyze_prompt"):
                    yield event
                ctx.vars["result"] = ctx.get_last_result()

        workflow = CallLlmWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock litellm.acompletion
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "LLM response content"

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            mock_acompletion.return_value = mock_response

            events = [
                event async for event in workflow.run_async(mock_session, mock_content)
            ]

        assert len(events) == 2

        # First event should be LlmCallEvent
        assert isinstance(events[0], LlmCallEvent)
        assert events[0].prompt_name == "analyze_prompt"
        assert events[0].model == "test-model"
        assert "Analyze:" in events[0].prompt_text

        # Second event should be LlmResponseEvent
        assert isinstance(events[1], LlmResponseEvent)
        assert events[1].prompt_name == "analyze_prompt"
        assert events[1].content == "LLM response content"
        assert events[1].is_final is True

    @pytest.mark.asyncio
    async def test_call_llm_with_model_override(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """call_llm with model override uses specified model."""
        from streetrace.dsl.runtime.context import WorkflowContext

        class ModelOverrideWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012
            _models = {"main": "default-model", "fast": "fast-model"}  # noqa: RUF012
            _prompts = {"quick_prompt": lambda _: "Quick task"}  # noqa: RUF012

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.call_llm("quick_prompt", model="fast-model"):
                    yield event

        workflow = ModelOverrideWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Fast response"

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            mock_acompletion.return_value = mock_response

            events = [
                event async for event in workflow.run_async(mock_session, mock_content)
            ]

        assert len(events) == 2
        assert isinstance(events[0], LlmCallEvent)
        assert events[0].model == "fast-model"


class TestMixedFlowYieldsCorrectEventSequence:
    """Test that mixed flow (agents + LLM calls) yields correct event sequence."""

    @pytest.mark.asyncio
    async def test_agent_then_llm_call_yields_all_events(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Flow with agent run followed by LLM call yields all events."""
        from streetrace.dsl.runtime.context import WorkflowContext

        agent_event = create_mock_adk_event(is_final=True, text="agent result")

        class MixedWorkflow(DslAgentWorkflow):
            _agents = {"analyzer": {"instruction": "analyze"}}  # noqa: RUF012
            _models = {"main": "test-model"}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "summarize": lambda ctx: f"Summarize: {ctx.vars.get('analysis', '')}",
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                # Run agent
                async for event in ctx.run_agent("analyzer"):
                    yield event
                ctx.vars["analysis"] = ctx.get_last_result()

                # Call LLM directly
                async for flow_event in ctx.call_llm("summarize"):
                    yield flow_event

        workflow = MixedWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            ctx = workflow._context  # noqa: SLF001
            if ctx is not None:
                ctx._last_call_result = "agent result"  # noqa: SLF001
            yield agent_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Summary result"

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            mock_acompletion.return_value = mock_response

            events = [
                event async for event in workflow.run_async(mock_session, mock_content)
            ]

        # Should have: agent_event, LlmCallEvent, LlmResponseEvent
        assert len(events) == 3

        # First is ADK event from agent
        assert events[0] is agent_event

        # Second is LlmCallEvent
        assert isinstance(events[1], LlmCallEvent)
        assert events[1].prompt_name == "summarize"

        # Third is LlmResponseEvent
        assert isinstance(events[2], LlmResponseEvent)
        assert events[2].content == "Summary result"


class TestNestedFlowsPropagateEvents:
    """Test that nested flows propagate events correctly."""

    @pytest.mark.asyncio
    async def test_nested_flow_yields_inner_flow_events(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Events from inner flow are yielded through outer flow."""
        from streetrace.dsl.runtime.context import WorkflowContext

        class NestedFlowWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012
            _models = {"main": "test-model"}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "inner_prompt": lambda _: "Inner task",
                "outer_prompt": lambda _: "Outer task",
            }

            async def flow_inner(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for flow_event in ctx.call_llm("inner_prompt"):
                    yield flow_event

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                # Call outer LLM first
                async for flow_event in ctx.call_llm("outer_prompt"):
                    yield flow_event

                # Call nested flow
                async for inner_event in ctx.run_flow("inner"):
                    yield inner_event

        workflow = NestedFlowWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Response"

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            mock_acompletion.return_value = mock_response

            events = [
                event async for event in workflow.run_async(mock_session, mock_content)
            ]

        # Should have: outer LlmCallEvent, outer LlmResponseEvent,
        # inner LlmCallEvent, inner LlmResponseEvent
        assert len(events) == 4

        # All events should be FlowEvents (LlmCallEvent or LlmResponseEvent)
        assert isinstance(events[0], LlmCallEvent)
        assert events[0].prompt_name == "outer_prompt"

        assert isinstance(events[1], LlmResponseEvent)

        assert isinstance(events[2], LlmCallEvent)
        assert events[2].prompt_name == "inner_prompt"

        assert isinstance(events[3], LlmResponseEvent)


class TestEndToEndDslCompilationAndExecution:
    """Test end-to-end DSL file compilation and execution."""

    def test_compiled_dsl_produces_async_generator_flow(self) -> None:
        """Verify compiled DSL file produces async generator flow methods."""
        from pathlib import Path

        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        # Use the actual flow.sr example file
        flow_file = Path("agents/examples/dsl/flow.sr")
        if not flow_file.exists():
            pytest.skip("flow.sr example file not found")

        source = flow_file.read_text()

        # Parse, transform, and generate code
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        python_code, _ = generator.generate(ast, str(flow_file))

        # Verify the generated code contains async generator patterns
        assert "AsyncGenerator" in python_code
        assert "async for _event in" in python_code
        assert "yield _event" in python_code
        assert "ctx.get_last_result()" in python_code

    def test_compiled_dsl_flow_method_is_async_generator(self) -> None:
        """Verify compiled DSL flow method is actually an async generator."""
        from pathlib import Path

        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        # Use the actual flow.sr example file
        flow_file = Path("agents/examples/dsl/flow.sr")
        if not flow_file.exists():
            pytest.skip("flow.sr example file not found")

        source = flow_file.read_text()

        # Parse, transform, and generate code
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        python_code, _ = generator.generate(ast, str(flow_file))

        # Compile (safe DSL-generated code)
        bytecode = compile(python_code, str(flow_file), "exec")
        namespace: dict[str, object] = {}
        # Execute the bytecode to define the workflow class
        # This is safe because it's DSL-generated code, not arbitrary user input
        exec(bytecode, namespace)  # noqa: S102

        # Find the workflow class
        workflow_class = None
        for obj in namespace.values():
            if (
                isinstance(obj, type)
                and issubclass(obj, DslAgentWorkflow)
                and obj.__name__ != "DslAgentWorkflow"
            ):
                workflow_class = obj
                break

        assert workflow_class is not None

        # Check that flow_main is an async generator function
        import inspect

        flow_main = getattr(workflow_class, "flow_main", None)
        assert flow_main is not None
        assert inspect.isasyncgenfunction(flow_main)


class TestEventTypesAreCorrect:
    """Test that FlowEvent subclasses have correct type field values."""

    def test_llm_call_event_has_correct_type(self) -> None:
        """LlmCallEvent type field is 'llm_call'."""
        event = LlmCallEvent(
            prompt_name="test",
            model="test-model",
            prompt_text="Test prompt",
        )
        assert event.type == "llm_call"

    def test_llm_response_event_has_correct_type(self) -> None:
        """LlmResponseEvent type field is 'llm_response'."""
        event = LlmResponseEvent(
            prompt_name="test",
            content="Test response",
        )
        assert event.type == "llm_response"

    def test_base_flow_event_requires_type(self) -> None:
        """Base FlowEvent requires type field."""
        event = FlowEvent(type="custom")
        assert event.type == "custom"

    def test_flow_event_subclasses_inherit_base(self) -> None:
        """Verify FlowEvent subclasses are instance of FlowEvent."""
        call_event = LlmCallEvent(
            prompt_name="test",
            model="model",
            prompt_text="text",
        )
        response_event = LlmResponseEvent(
            prompt_name="test",
            content="response",
        )

        assert isinstance(call_event, FlowEvent)
        assert isinstance(response_event, FlowEvent)


class TestResultCaptureWorksCorrectly:
    """Test that ctx.get_last_result() returns correct values."""

    @pytest.mark.asyncio
    async def test_get_last_result_after_call_llm(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """get_last_result returns LLM response after call_llm."""
        from streetrace.dsl.runtime.context import WorkflowContext

        captured_result: object = None

        class ResultCaptureWorkflow(DslAgentWorkflow):
            _agents = {}  # noqa: RUF012
            _models = {"main": "test-model"}  # noqa: RUF012
            _prompts = {"test_prompt": lambda _: "Test"}  # noqa: RUF012

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                nonlocal captured_result
                async for event in ctx.call_llm("test_prompt"):
                    yield event
                captured_result = ctx.get_last_result()

        workflow = ResultCaptureWorkflow(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Captured response"

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            mock_acompletion.return_value = mock_response

            _ = [
                event async for event in workflow.run_async(mock_session, mock_content)
            ]

        assert captured_result == "Captured response"

    @pytest.mark.asyncio
    async def test_variable_assignment_from_result(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Variable assignment works with get_last_result pattern."""
        from streetrace.dsl.runtime.context import WorkflowContext

        agent_event = create_mock_adk_event(is_final=True, text="step1 result")

        class VariableAssignmentWorkflow(DslAgentWorkflow):
            _agents = {"step1": {"instruction": "do step1"}}  # noqa: RUF012
            _models = {"main": "test-model"}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "step2_prompt": lambda ctx: (
                    f"Process: {ctx.vars.get('step1_result', '')}"
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                # $step1_result = run agent step1
                async for adk_event in ctx.run_agent("step1"):
                    yield adk_event
                ctx.vars["step1_result"] = ctx.get_last_result()

                # $final = call llm step2_prompt
                async for flow_event in ctx.call_llm("step2_prompt"):
                    yield flow_event
                ctx.vars["final"] = ctx.get_last_result()

        workflow = VariableAssignmentWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            ctx = workflow._context  # noqa: SLF001
            if ctx is not None:
                ctx._last_call_result = "step1 result"  # noqa: SLF001
            yield agent_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "final result"

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            mock_acompletion.return_value = mock_response

            _ = [
                event async for event in workflow.run_async(mock_session, mock_content)
            ]

        # Verify both variables were captured
        assert workflow._context is not None  # noqa: SLF001
        assert workflow._context.vars["step1_result"] == "step1 result"  # noqa: SLF001
        assert workflow._context.vars["final"] == "final result"  # noqa: SLF001


class TestAgentEntryPointYieldsEvents:
    """Test that agent entry point (no flow) also yields events."""

    @pytest.mark.asyncio
    async def test_agent_entry_yields_events(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Workflow with agent entry point (no flow) yields ADK events."""
        event1 = create_mock_adk_event(is_final=False)
        event2 = create_mock_adk_event(is_final=True, text="done")

        class AgentOnlyWorkflow(DslAgentWorkflow):
            _agents = {"default": {"instruction": "test"}}  # noqa: RUF012

        workflow = AgentOnlyWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock _execute_agent to yield events
        async def mock_execute_agent(
            agent_name: str,  # noqa: ARG001
            session: "Session",  # noqa: ARG001
            message: "Content | None",  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            yield event1
            yield event2

        workflow._execute_agent = mock_execute_agent  # type: ignore[method-assign]  # noqa: SLF001

        events = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert len(events) == 2
        assert events[0] is event1
        assert events[1] is event2
