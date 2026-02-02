"""Unit tests for run_agent async generator functionality.

Test that DslAgentWorkflow.run_agent and WorkflowContext.run_agent
yield ADK events as async generators.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions.base_session_service import BaseSessionService

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


def create_mock_event(
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


async def mock_runner_run_async(
    events: list["Event"],
) -> AsyncGenerator["Event", None]:
    """Create async generator that yields mock events.

    Args:
        events: List of events to yield.

    Yields:
        Each event in sequence.

    """
    for event in events:
        yield event


class TestDslAgentWorkflowRunAgentGenerator:
    """Test DslAgentWorkflow.run_agent as an async generator."""

    @pytest.mark.asyncio
    async def test_run_agent_is_async_generator(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_agent returns an async generator."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock Runner and InMemorySessionService
        mock_event = create_mock_event(is_final=True, text="result")
        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([mock_event])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch(
                "google.adk.Runner",
                return_value=mock_runner,
            ),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            result = workflow.run_agent("test_agent", "input")
            # Check it's an async generator
            assert hasattr(result, "__anext__")

    @pytest.mark.asyncio
    async def test_run_agent_yields_all_adk_events(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_agent yields all ADK events from runner."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Create multiple events
        event1 = create_mock_event(is_final=False)
        event2 = create_mock_event(is_final=False)
        event3 = create_mock_event(is_final=True, text="final result")

        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async(
            [event1, event2, event3],
        )

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch(
                "google.adk.Runner",
                return_value=mock_runner,
            ),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            collected_events = [
                event async for event in workflow.run_agent("test_agent", "input")
            ]

        assert len(collected_events) == 3
        assert collected_events[0] is event1
        assert collected_events[1] is event2
        assert collected_events[2] is event3

    @pytest.mark.asyncio
    async def test_run_agent_captures_final_response_in_context(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_agent stores final response in context._last_call_result."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Create context first
        ctx = workflow.create_context(input_prompt="test input")

        final_event = create_mock_event(is_final=True, text="captured result")

        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([final_event])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch(
                "google.adk.Runner",
                return_value=mock_runner,
            ),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            # Consume the generator to trigger result capture
            _ = [event async for event in workflow.run_agent("test_agent", "input")]

        assert ctx._last_call_result == "captured result"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_run_agent_handles_missing_content_parts(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_agent handles final event with no content parts."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        ctx = workflow.create_context(input_prompt="test input")

        # Final event with empty parts
        final_event = create_mock_event(is_final=True)

        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([final_event])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch(
                "google.adk.Runner",
                return_value=mock_runner,
            ),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            _ = [event async for event in workflow.run_agent("test_agent")]

        # Should be None when no content parts
        assert ctx._last_call_result is None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_run_agent_builds_prompt_from_args(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_agent builds prompt text from arguments."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        final_event = create_mock_event(is_final=True, text="result")

        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([final_event])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        captured_message = None

        def capture_runner(
            *,
            app_name: str,  # noqa: ARG001
            session_service: object,  # noqa: ARG001
            agent: object,  # noqa: ARG001
        ) -> MagicMock:
            nonlocal mock_runner
            return mock_runner

        def capture_run_async(
            *,
            user_id: str,  # noqa: ARG001
            session_id: str,  # noqa: ARG001
            new_message: object,
        ) -> AsyncGenerator:
            nonlocal captured_message
            captured_message = new_message
            return mock_runner_run_async([final_event])

        mock_runner.run_async = capture_run_async

        with (
            patch(
                "google.adk.Runner",
                side_effect=capture_runner,
            ),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            _ = [
                event
                async for event in workflow.run_agent("test_agent", "arg1", "arg2")
            ]

        # Verify message was created with joined args
        assert captured_message is not None
        assert captured_message.parts[0].text == "arg1\n---\narg2"


class TestWorkflowContextRunAgentGenerator:
    """Test WorkflowContext.run_agent as an async generator."""

    @pytest.mark.asyncio
    async def test_context_run_agent_is_async_generator(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """WorkflowContext.run_agent returns an async generator."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = WorkflowContext(workflow=workflow)

        mock_event = create_mock_event(is_final=True, text="result")
        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([mock_event])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch(
                "google.adk.Runner",
                return_value=mock_runner,
            ),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            result = ctx.run_agent("test_agent")
            assert hasattr(result, "__anext__")

    @pytest.mark.asyncio
    async def test_context_run_agent_yields_events_from_workflow(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """WorkflowContext.run_agent re-yields events from workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = WorkflowContext(workflow=workflow)

        event1 = create_mock_event(is_final=False)
        event2 = create_mock_event(is_final=True, text="final")

        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([event1, event2])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch(
                "google.adk.Runner",
                return_value=mock_runner,
            ),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            collected = [event async for event in ctx.run_agent("test_agent")]

        assert len(collected) == 2
        assert collected[0] is event1
        assert collected[1] is event2

    @pytest.mark.asyncio
    async def test_context_run_agent_passes_args_to_workflow(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """WorkflowContext.run_agent passes arguments to workflow."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Mock run_agent to capture args
        captured_args: list[object] = []

        async def mock_run_agent(
            agent_name: str,
            *args: object,
        ) -> AsyncGenerator[MagicMock, None]:
            captured_args.extend([agent_name, *args])
            yield create_mock_event(is_final=True, text="result")

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        ctx = WorkflowContext(workflow=workflow)
        _ = [event async for event in ctx.run_agent("agent", "arg1", "arg2", "arg3")]

        assert captured_args == ["agent", "arg1", "arg2", "arg3"]


class TestMultipleAgentInterleaving:
    """Test event yielding with multiple agents."""

    @pytest.mark.asyncio
    async def test_sequential_agents_yield_interleaved_events(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Sequential agent runs yield their events in order."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {  # noqa: RUF012
                "agent1": {"instruction": "first"},
                "agent2": {"instruction": "second"},
            }

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        workflow.create_context(input_prompt="test")

        # Events for agent1
        agent1_event1 = create_mock_event(is_final=False)
        agent1_event1.agent_name = "agent1"
        agent1_event2 = create_mock_event(is_final=True, text="result1")
        agent1_event2.agent_name = "agent1"

        # Events for agent2
        agent2_event1 = create_mock_event(is_final=False)
        agent2_event1.agent_name = "agent2"
        agent2_event2 = create_mock_event(is_final=True, text="result2")
        agent2_event2.agent_name = "agent2"

        call_count = 0

        def make_runner(
            *,
            app_name: str,  # noqa: ARG001
            session_service: object,  # noqa: ARG001
            agent: object,  # noqa: ARG001
        ) -> MagicMock:
            nonlocal call_count
            mock_runner = MagicMock()
            if call_count == 0:
                mock_runner.run_async.return_value = mock_runner_run_async(
                    [agent1_event1, agent1_event2],
                )
            else:
                mock_runner.run_async.return_value = mock_runner_run_async(
                    [agent2_event1, agent2_event2],
                )
            call_count += 1
            return mock_runner

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch(
                "google.adk.Runner",
                side_effect=make_runner,
            ),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            # Run agent1 first
            events1 = [event async for event in workflow.run_agent("agent1", "input1")]

            # Run agent2 second
            events2 = [event async for event in workflow.run_agent("agent2", "input2")]

        # Each agent should yield its own events
        assert len(events1) == 2
        assert events1[0].agent_name == "agent1"
        assert events1[1].agent_name == "agent1"

        assert len(events2) == 2
        assert events2[0].agent_name == "agent2"
        assert events2[1].agent_name == "agent2"


class TestRunAgentWithoutContext:
    """Test run_agent behavior when no context is set."""

    @pytest.mark.asyncio
    async def test_run_agent_without_context_does_not_fail(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """run_agent works even without a context."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {"test_agent": {"instruction": "test"}}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        # Do NOT create context
        assert workflow._context is None  # noqa: SLF001

        final_event = create_mock_event(is_final=True, text="result")

        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([final_event])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch(
                "google.adk.Runner",
                return_value=mock_runner,
            ),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            # Should not raise
            events = [event async for event in workflow.run_agent("test_agent")]

        assert len(events) == 1
