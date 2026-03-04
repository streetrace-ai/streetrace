"""End-to-end integration tests for escalation operator feature.

Test the complete pipeline: DSL -> Parse -> Transform -> Codegen -> Execute
for escalation conditions and handlers.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.dsl.runtime.errors import AbortError
from streetrace.dsl.runtime.workflow import DslAgentWorkflow, EscalationSpec, PromptSpec

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.dsl.runtime.events import FlowEvent
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


class TestNormalizedEscalationE2E:
    """Test normalized escalation (~) end-to-end."""

    @pytest.mark.asyncio
    async def test_escalation_triggers_on_normalized_match(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Test that ~ escalation triggers when agent returns matching output.

        When agent returns "done" (or variations like "**Done.**"), the
        escalation condition ~ "DONE" should match and trigger handler.
        """
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text="**Done.**")

        class EscalationWorkflow(DslAgentWorkflow):
            _agents = {"peer1": {"instruction": "analyzer"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "analyzer": PromptSpec(
                    body=lambda _: "You analyze text.",
                    escalation=EscalationSpec(op="~", value="DONE"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                # $result = run agent peer1 $input, on escalate return "escalated"
                async for event in ctx.run_agent_with_escalation(
                    "peer1",
                    ctx.vars["input_prompt"],
                ):
                    yield event
                ctx.vars["result"] = ctx.get_last_result()
                _, escalated = ctx.get_last_result_with_escalation()
                if escalated:
                    ctx.vars["_return_value"] = "escalated"
                    return
                ctx.vars["_return_value"] = ctx.vars["result"]

        workflow = EscalationWorkflow(
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
                ctx._last_call_result = "**Done.**"  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [event async for event in workflow.run_async(mock_session, mock_content)]

        assert workflow._context is not None  # noqa: SLF001
        assert workflow._context.vars.get("_return_value") == "escalated"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_no_escalation_when_normalized_does_not_match(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Test that normal flow continues when escalation condition not met."""
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text="SUCCESS")

        class NoEscalationWorkflow(DslAgentWorkflow):
            _agents = {"peer1": {"instruction": "analyzer"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "analyzer": PromptSpec(
                    body=lambda _: "You analyze text.",
                    escalation=EscalationSpec(op="~", value="DONE"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.run_agent_with_escalation(
                    "peer1",
                    ctx.vars["input_prompt"],
                ):
                    yield event
                ctx.vars["result"] = ctx.get_last_result()
                _, escalated = ctx.get_last_result_with_escalation()
                if escalated:
                    ctx.vars["_return_value"] = "should not happen"
                    return
                ctx.vars["_return_value"] = ctx.vars["result"]

        workflow = NoEscalationWorkflow(
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
                ctx._last_call_result = "SUCCESS"  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [event async for event in workflow.run_async(mock_session, mock_content)]

        assert workflow._context is not None  # noqa: SLF001
        assert workflow._context.vars.get("_return_value") == "SUCCESS"  # noqa: SLF001


class TestEscalationWithReturnValue:
    """Test on escalate return $value pattern."""

    @pytest.mark.asyncio
    async def test_return_previous_value_on_escalation(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Test that on escalate return $current returns the previous value."""
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text="STOP")

        class ReturnValueWorkflow(DslAgentWorkflow):
            _agents = {"checker": {"instruction": "checker_prompt"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "checker_prompt": PromptSpec(
                    body=lambda _: "You check things.",
                    escalation=EscalationSpec(op="~", value="STOP"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                ctx.vars["current"] = "initial"
                async for event in ctx.run_agent_with_escalation(
                    "checker",
                    ctx.vars["input_prompt"],
                ):
                    yield event
                # On escalate return $current
                _, escalated = ctx.get_last_result_with_escalation()
                if escalated:
                    ctx.vars["_return_value"] = ctx.vars["current"]
                    return
                ctx.vars["current"] = ctx.get_last_result()
                ctx.vars["_return_value"] = ctx.vars["current"]

        workflow = ReturnValueWorkflow(
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
                ctx._last_call_result = "STOP"  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [event async for event in workflow.run_async(mock_session, mock_content)]

        assert workflow._context is not None  # noqa: SLF001
        # Should return "initial" not "STOP"
        assert workflow._context.vars.get("_return_value") == "initial"  # noqa: SLF001


class TestEscalationWithContinue:
    """Test on escalate continue pattern in loops."""

    @pytest.mark.asyncio
    async def test_continue_skips_to_next_iteration(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Test that on escalate continue skips the current iteration."""
        from streetrace.dsl.runtime.context import WorkflowContext

        class ContinueWorkflow(DslAgentWorkflow):
            _agents = {"iter_agent": {"instruction": "iter_prompt"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "iter_prompt": PromptSpec(
                    body=lambda _: "You iterate.",
                    escalation=EscalationSpec(op="contains", value="SKIP"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                ctx.vars["results"] = []
                items = ["item1", "SKIP THIS", "item3"]

                for item in items:
                    async for event in ctx.run_agent_with_escalation(
                        "iter_agent",
                        item,
                    ):
                        yield event
                    _, escalated = ctx.get_last_result_with_escalation()
                    if escalated:
                        continue  # Skip this iteration
                    result = ctx.get_last_result()
                    results_list = ctx.vars["results"]
                    if isinstance(results_list, list):
                        results_list.append(result)

                ctx.vars["_return_value"] = ctx.vars["results"]

        workflow = ContinueWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        call_count = 0

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,
        ) -> AsyncGenerator["Event", None]:
            nonlocal call_count
            ctx = workflow._context  # noqa: SLF001
            item = args[0] if args else ""
            # Return the item as the result
            if ctx is not None:
                ctx._last_call_result = str(item)  # noqa: SLF001
            call_count += 1
            yield create_mock_adk_event(is_final=True, text=str(item))

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [event async for event in workflow.run_async(mock_session, mock_content)]

        assert workflow._context is not None  # noqa: SLF001
        results = workflow._context.vars.get("_return_value")  # noqa: SLF001
        # "SKIP THIS" should not be in results
        assert results == ["item1", "item3"]
        assert call_count == 3  # All items were processed


class TestEscalationWithAbort:
    """Test on escalate abort pattern."""

    @pytest.mark.asyncio
    async def test_abort_raises_abort_error(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Test that on escalate abort raises AbortError."""
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text="FATAL")

        class AbortWorkflow(DslAgentWorkflow):
            _agents = {"critical": {"instruction": "critical_prompt"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "critical_prompt": PromptSpec(
                    body=lambda _: "You do critical work.",
                    escalation=EscalationSpec(op="==", value="FATAL"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.run_agent_with_escalation(
                    "critical",
                    ctx.vars["input_prompt"],
                ):
                    yield event
                _, escalated = ctx.get_last_result_with_escalation()
                if escalated:
                    msg = "Escalation triggered abort"
                    raise AbortError(msg)
                ctx.vars["_return_value"] = ctx.get_last_result()

        workflow = AbortWorkflow(
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
                ctx._last_call_result = "FATAL"  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        with pytest.raises(AbortError, match="Escalation triggered abort"):
            _ = [
                event async for event in workflow.run_async(mock_session, mock_content)
            ]


class TestBackwardCompatibility:
    """Test backward compatibility - prompts without escalation work."""

    @pytest.mark.asyncio
    async def test_prompts_without_escalation_work(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Test that prompts without escalation still work normally."""
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text="normal result")

        class BasicWorkflow(DslAgentWorkflow):
            _agents = {"basic": {"instruction": "basic_prompt"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                # PromptSpec without escalation
                "basic_prompt": PromptSpec(
                    body=lambda _: "You do basic work.",
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.run_agent("basic", ctx.vars["input_prompt"]):
                    yield event
                ctx.vars["_return_value"] = ctx.get_last_result()

        workflow = BasicWorkflow(
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
                ctx._last_call_result = "normal result"  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [event async for event in workflow.run_async(mock_session, mock_content)]

        assert workflow._context is not None  # noqa: SLF001
        assert workflow._context.vars.get("_return_value") == "normal result"  # noqa: SLF001


class TestMultipleEscalationOperators:
    """Test all escalation operators work correctly."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("output", "expected_escalation"),
        [
            ("DONE", True),
            ("done", True),
            ("**Done.**", True),
            ("  Drifting!  ", False),  # Does not match "DONE"
            ("I am done", False),  # Not equal, just contains
        ],
    )
    async def test_normalized_operator_matches_with_formatting(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
        output: str,
        expected_escalation: bool,
    ) -> None:
        """Test ~ operator handles markdown formatting."""
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text=output)

        class NormalizedWorkflow(DslAgentWorkflow):
            _agents = {"test": {"instruction": "test_prompt"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "test_prompt": PromptSpec(
                    body=lambda _: "Test.",
                    escalation=EscalationSpec(op="~", value="DONE"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.run_agent_with_escalation("test"):
                    yield event
                _, escalated = ctx.get_last_result_with_escalation()
                ctx.vars["escalated"] = escalated

        workflow = NormalizedWorkflow(
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
                ctx._last_call_result = output  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert workflow._context is not None  # noqa: SLF001
        assert workflow._context.vars.get("escalated") == expected_escalation  # noqa: SLF001

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("output", "expected_escalation"),
        [
            ("EXACT", True),
            ("exact", False),  # Case sensitive
            ("EXACT!", False),  # Extra punctuation
        ],
    )
    async def test_exact_match_operator(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
        output: str,
        expected_escalation: bool,
    ) -> None:
        """Test == operator requires exact string match."""
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text=output)

        class ExactWorkflow(DslAgentWorkflow):
            _agents = {"test": {"instruction": "test_prompt"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "test_prompt": PromptSpec(
                    body=lambda _: "Test.",
                    escalation=EscalationSpec(op="==", value="EXACT"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.run_agent_with_escalation("test"):
                    yield event
                _, escalated = ctx.get_last_result_with_escalation()
                ctx.vars["escalated"] = escalated

        workflow = ExactWorkflow(
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
                ctx._last_call_result = output  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert workflow._context is not None  # noqa: SLF001
        assert workflow._context.vars.get("escalated") == expected_escalation  # noqa: SLF001

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("output", "expected_escalation"),
        [
            ("KEEP", False),  # Matches, so no escalation
            ("DISCARD", True),  # Doesn't match, escalate
            ("keep", True),  # Case sensitive, doesn't match
        ],
    )
    async def test_not_equal_operator(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
        output: str,
        expected_escalation: bool,
    ) -> None:
        """Test != operator escalates when value does not match."""
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text=output)

        class NotEqualWorkflow(DslAgentWorkflow):
            _agents = {"test": {"instruction": "test_prompt"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "test_prompt": PromptSpec(
                    body=lambda _: "Test.",
                    escalation=EscalationSpec(op="!=", value="KEEP"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.run_agent_with_escalation("test"):
                    yield event
                _, escalated = ctx.get_last_result_with_escalation()
                ctx.vars["escalated"] = escalated

        workflow = NotEqualWorkflow(
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
                ctx._last_call_result = output  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert workflow._context is not None  # noqa: SLF001
        assert workflow._context.vars.get("escalated") == expected_escalation  # noqa: SLF001

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("output", "expected_escalation"),
        [
            ("Found ERROR in data", True),
            ("ERROR", True),
            ("An ERROR occurred", True),
            ("error", False),  # Case sensitive
            ("No issues found", False),
        ],
    )
    async def test_contains_operator(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
        output: str,
        expected_escalation: bool,
    ) -> None:
        """Test contains operator escalates when substring found."""
        from streetrace.dsl.runtime.context import WorkflowContext

        final_event = create_mock_adk_event(is_final=True, text=output)

        class ContainsWorkflow(DslAgentWorkflow):
            _agents = {"test": {"instruction": "test_prompt"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "test_prompt": PromptSpec(
                    body=lambda _: "Test.",
                    escalation=EscalationSpec(op="contains", value="ERROR"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                async for event in ctx.run_agent_with_escalation("test"):
                    yield event
                _, escalated = ctx.get_last_result_with_escalation()
                ctx.vars["escalated"] = escalated

        workflow = ContainsWorkflow(
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
                ctx._last_call_result = output  # noqa: SLF001
            yield final_event

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [
            event async for event in workflow.run_async(mock_session, mock_content)
        ]

        assert workflow._context is not None  # noqa: SLF001
        assert workflow._context.vars.get("escalated") == expected_escalation  # noqa: SLF001


class TestDslCompilationAndEscalation:
    """Test DSL compilation produces correct escalation code."""

    def test_compiled_dsl_with_escalation_is_valid_python(self) -> None:
        """Test that compiled DSL with escalation generates valid Python."""
        from streetrace.dsl.ast.transformer import AstTransformer
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''
model main = anthropic/claude-sonnet

prompt analyzer: """You analyze text."""
    escalate if ~ "DONE"

agent peer1:
    instruction analyzer

flow resolver:
    $result = run agent peer1 with $input_prompt, on escalate return "escalated"
    return $result
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)

        transformer = AstTransformer()
        ast = transformer.transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify the code compiles
        compile(code, "<generated>", "exec")

        # Verify escalation-related code is present
        assert "EscalationSpec" in code
        assert "run_agent_with_escalation" in code
        assert "_escalated" in code

    def test_compiled_dsl_has_escalation_spec_in_prompts(self) -> None:
        """Test that compiled DSL includes EscalationSpec in prompt definitions."""
        from streetrace.dsl.ast.transformer import AstTransformer
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''
prompt test_normalized: """Test."""
    escalate if ~ "DONE"

prompt test_exact: """Test."""
    escalate if == "EXACT"

prompt test_not_equal: """Test."""
    escalate if != "KEEP"

prompt test_contains: """Test."""
    escalate if contains "ERROR"
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)

        transformer = AstTransformer()
        ast = transformer.transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify all escalation operators are generated
        assert "op='~'" in code
        assert "op='=='" in code
        assert "op='!='" in code
        assert "op='contains'" in code

        # Verify all values are present
        assert "value='DONE'" in code
        assert "value='EXACT'" in code
        assert "value='KEEP'" in code
        assert "value='ERROR'" in code

    def test_compiled_dsl_abort_handler_generates_abort_error(self) -> None:
        """Test that compiled DSL with abort handler raises AbortError."""
        from streetrace.dsl.ast.transformer import AstTransformer
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''
prompt critical: """You do critical work."""
    escalate if == "FATAL"

agent critical_agent:
    instruction critical

flow critical_flow:
    $result = run agent critical_agent with $input_prompt, on escalate abort
    return $result
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)

        transformer = AstTransformer()
        ast = transformer.transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify the code compiles
        compile(code, "<generated>", "exec")

        # Verify AbortError is imported and used
        assert "AbortError" in code
        assert "raise AbortError" in code


class TestLoopWithEscalationPatterns:
    """Test escalation patterns in loop contexts."""

    @pytest.mark.asyncio
    async def test_loop_with_escalation_return_exits_loop(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Test that on escalate return exits the loop and returns value."""
        from streetrace.dsl.runtime.context import WorkflowContext

        class LoopReturnWorkflow(DslAgentWorkflow):
            _agents = {"peer1": {"instruction": "pi_enhancer"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "pi_enhancer": PromptSpec(
                    body=lambda _: "You are a prompt improvement assistant.",
                    escalation=EscalationSpec(op="~", value="DRIFTING"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                ctx.vars["current"] = "initial"
                ctx.vars["iteration_count"] = 0

                for _ in range(3):
                    count = ctx.vars["iteration_count"]
                    ctx.vars["iteration_count"] = (
                        (int(count) if isinstance(count, int | str) else 0) + 1
                    )
                    async for event in ctx.run_agent_with_escalation(
                        "peer1",
                        ctx.vars["current"],
                    ):
                        yield event
                    _, escalated = ctx.get_last_result_with_escalation()
                    if escalated:
                        ctx.vars["_return_value"] = ctx.vars["current"]
                        return
                    ctx.vars["current"] = ctx.get_last_result()

                ctx.vars["_return_value"] = ctx.vars["current"]

        workflow = LoopReturnWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        iteration = 0

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,  # noqa: ARG001
        ) -> AsyncGenerator["Event", None]:
            nonlocal iteration
            iteration += 1
            ctx = workflow._context  # noqa: SLF001
            if ctx is not None:
                # On second iteration, return DRIFTING
                if iteration == 2:
                    ctx._last_call_result = "**Drifting!**"  # noqa: SLF001
                else:
                    ctx._last_call_result = f"result_{iteration}"  # noqa: SLF001
            yield create_mock_adk_event(
                is_final=True,
                text="**Drifting!**" if iteration == 2 else f"result_{iteration}",
            )

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [event async for event in workflow.run_async(mock_session, mock_content)]

        assert workflow._context is not None  # noqa: SLF001
        # Loop exited on iteration 2
        assert workflow._context.vars.get("iteration_count") == 2  # noqa: SLF001
        # Should return "result_1" (the value before escalation)
        assert workflow._context.vars.get("_return_value") == "result_1"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_for_loop_with_continue_processes_all_items(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Test that on escalate continue skips but processes remaining items."""
        from streetrace.dsl.runtime.context import WorkflowContext

        class ForLoopContinueWorkflow(DslAgentWorkflow):
            _agents = {"processor": {"instruction": "process_prompt"}}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "process_prompt": PromptSpec(
                    body=lambda _: "Process item.",
                    escalation=EscalationSpec(op="contains", value="SKIP"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                ctx.vars["results"] = []
                ctx.vars["skipped"] = []
                items = ["good1", "SKIP_ME", "good2", "SKIP_THIS_TOO", "good3"]

                for item in items:
                    async for event in ctx.run_agent_with_escalation("processor", item):
                        yield event
                    _, escalated = ctx.get_last_result_with_escalation()
                    skipped_list = ctx.vars["skipped"]
                    results_list = ctx.vars["results"]
                    if escalated:
                        if isinstance(skipped_list, list):
                            skipped_list.append(item)
                        continue
                    result = ctx.get_last_result()
                    if isinstance(results_list, list):
                        results_list.append(result)

                ctx.vars["_return_value"] = {
                    "results": ctx.vars["results"],
                    "skipped": ctx.vars["skipped"],
                }

        workflow = ForLoopContinueWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        async def mock_run_agent(
            agent_name: str,  # noqa: ARG001
            *args: object,
        ) -> AsyncGenerator["Event", None]:
            ctx = workflow._context  # noqa: SLF001
            item = args[0] if args else ""
            if ctx is not None:
                ctx._last_call_result = f"processed_{item}"  # noqa: SLF001
            yield create_mock_adk_event(is_final=True, text=f"processed_{item}")

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [event async for event in workflow.run_async(mock_session, mock_content)]

        assert workflow._context is not None  # noqa: SLF001
        return_value = workflow._context.vars.get("_return_value")  # noqa: SLF001
        assert isinstance(return_value, dict)
        # Only non-SKIP items should be in results
        assert return_value["results"] == [
            "processed_good1",
            "processed_good2",
            "processed_good3",
        ]
        # SKIP items should be tracked
        assert return_value["skipped"] == ["SKIP_ME", "SKIP_THIS_TOO"]


class TestCompleteResolverExample:
    """Test the complete resolver example from the design document."""

    @pytest.mark.asyncio
    async def test_complete_resolver_pattern(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        mock_session: "Session",
        mock_content: "Content",
    ) -> None:
        """Test the full resolver pattern from the design doc.

        The pattern:
        - Two peer agents that can improve prompts
        - Each can output "DRIFTING" if conversation goes off track
        - Loop max 3 times, escalating (returning current) if DRIFTING
        """
        from streetrace.dsl.runtime.context import WorkflowContext

        class ResolverWorkflow(DslAgentWorkflow):
            _models = {"main": "anthropic/claude-sonnet"}  # noqa: RUF012
            _agents = {  # noqa: RUF012
                "peer1": {"instruction": "pi_enhancer"},
                "peer2": {"instruction": "pi_enhancer"},
            }
            _prompts = {  # noqa: RUF012
                "pi_enhancer": PromptSpec(
                    body=lambda _: (
                        "You are a prompt improvement assistant. "
                        "Reply with DRIFTING if conversation is going off track."
                    ),
                    model="main",
                    escalation=EscalationSpec(op="~", value="DRIFTING"),
                ),
            }

            async def flow_main(
                self,
                ctx: WorkflowContext,
            ) -> AsyncGenerator["Event | FlowEvent", None]:
                ctx.vars["current"] = ctx.vars["input_prompt"]

                for _ in range(3):  # loop max 3
                    # peer1
                    async for event in ctx.run_agent_with_escalation(
                        "peer1",
                        ctx.vars["current"],
                    ):
                        yield event
                    _, escalated1 = ctx.get_last_result_with_escalation()
                    if escalated1:
                        ctx.vars["_return_value"] = ctx.vars["current"]
                        return
                    ctx.vars["current"] = ctx.get_last_result()

                    # peer2
                    async for event in ctx.run_agent_with_escalation(
                        "peer2",
                        ctx.vars["current"],
                    ):
                        yield event
                    _, escalated2 = ctx.get_last_result_with_escalation()
                    if escalated2:
                        ctx.vars["_return_value"] = ctx.vars["current"]
                        return
                    ctx.vars["current"] = ctx.get_last_result()

                ctx.vars["_return_value"] = ctx.vars["current"]

        workflow = ResolverWorkflow(
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
            call_count += 1
            ctx = workflow._context  # noqa: SLF001
            result_text: str
            if ctx is not None:
                # Simulate: peer1 works fine, peer2 drifts on iteration 2
                if agent_name == "peer2" and call_count == 4:  # 2nd peer2 call
                    ctx._last_call_result = "**Drifting.**"  # noqa: SLF001
                    result_text = "**Drifting.**"
                else:
                    ctx._last_call_result = f"improved_v{call_count}"  # noqa: SLF001
                    result_text = f"improved_v{call_count}"
            else:
                result_text = ""
            yield create_mock_adk_event(is_final=True, text=result_text)

        workflow.run_agent = mock_run_agent  # type: ignore[method-assign]

        _ = [event async for event in workflow.run_async(mock_session, mock_content)]

        assert workflow._context is not None  # noqa: SLF001
        # Should have stopped when peer2 drifted on iteration 2
        # Sequence: peer1 -> peer2 -> peer1 -> peer2 (drifts)
        assert call_count == 4
        # Return value should be result from peer1 (call 3), not the drifting result
        assert workflow._context.vars.get("_return_value") == "improved_v3"  # noqa: SLF001
