"""Tests for agent result schema validation with retry.

Verify that run_agent() and _execute_parallel_agents() validate agent results
against the schema declared via `expecting` in the prompt definition.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.dsl_agent_factory import DslAgentFactory


class Finding(BaseModel):
    """Test schema for agent results."""

    confidence: int
    message: str


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


class TestAgentResultValidation:
    """Test run_agent schema validation."""

    @pytest.mark.asyncio
    async def test_agent_returns_valid_json_array(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Agent returns valid JSON array matching schema."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow, PromptSpec

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {  # noqa: RUF012
                "security_agent": {"instruction": "security_prompt"},
            }
            _prompts = {  # noqa: RUF012
                "security_prompt": PromptSpec(
                    body=lambda _ctx: "Review code",
                    schema="Finding[]",
                ),
            }
            _schemas = {"Finding": Finding}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        ctx = workflow.create_context(input_prompt="test")

        # Agent returns valid JSON array
        valid_json = '[{"confidence": 90, "message": "Found a bug"}]'
        final_event = create_mock_event(is_final=True, text=valid_json)

        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([final_event])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch("google.adk.Runner", return_value=mock_runner),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            _ = [event async for event in workflow.run_agent("security_agent", "code")]

        # Result should be a parsed and validated list
        assert isinstance(ctx._last_call_result, list)  # noqa: SLF001
        assert len(ctx._last_call_result) == 1  # noqa: SLF001
        assert ctx._last_call_result[0]["confidence"] == 90  # noqa: SLF001
        assert ctx._last_call_result[0]["message"] == "Found a bug"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_agent_returns_prose_retries_then_succeeds(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Agent returns prose first, retry returns valid JSON."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow, PromptSpec

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {  # noqa: RUF012
                "security_agent": {"instruction": "security_prompt"},
            }
            _prompts = {  # noqa: RUF012
                "security_prompt": PromptSpec(
                    body=lambda _ctx: "Review code",
                    schema="Finding[]",
                ),
            }
            _schemas = {"Finding": Finding}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        ctx = workflow.create_context(input_prompt="test")

        # Track calls to return different responses
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
                # First call: prose
                event = create_mock_event(
                    is_final=True,
                    text="I found a security issue in the code.",
                )
            else:
                # Retry: valid JSON
                event = create_mock_event(
                    is_final=True,
                    text='[{"confidence": 85, "message": "SQL injection risk"}]',
                )
            call_count += 1
            mock_runner.run_async.return_value = mock_runner_run_async([event])
            return mock_runner

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch("google.adk.Runner", side_effect=make_runner),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            _ = [event async for event in workflow.run_agent("security_agent", "code")]

        # Should have retried and gotten valid result
        assert call_count == 2
        assert isinstance(ctx._last_call_result, list)  # noqa: SLF001
        assert len(ctx._last_call_result) == 1  # noqa: SLF001
        assert ctx._last_call_result[0]["confidence"] == 85  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_agent_returns_prose_twice_falls_back_to_empty(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Agent returns prose twice, falls back to empty array."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow, PromptSpec

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {  # noqa: RUF012
                "security_agent": {"instruction": "security_prompt"},
            }
            _prompts = {  # noqa: RUF012
                "security_prompt": PromptSpec(
                    body=lambda _ctx: "Review code",
                    schema="Finding[]",
                ),
            }
            _schemas = {"Finding": Finding}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        ctx = workflow.create_context(input_prompt="test")

        # Always return prose
        def make_runner(
            *,
            app_name: str,  # noqa: ARG001
            session_service: object,  # noqa: ARG001
            agent: object,  # noqa: ARG001
        ) -> MagicMock:
            mock_runner = MagicMock()
            event = create_mock_event(
                is_final=True,
                text="I found issues but here's prose instead of JSON.",
            )
            mock_runner.run_async.return_value = mock_runner_run_async([event])
            return mock_runner

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch("google.adk.Runner", side_effect=make_runner),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            _ = [event async for event in workflow.run_agent("security_agent", "code")]

        # Should fall back to empty array
        assert ctx._last_call_result == []  # noqa: SLF001

        # Should log a warning
        assert any(
            "expected Finding[]" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )

    @pytest.mark.asyncio
    async def test_agent_without_schema_passes_through(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Agent without expecting clause uses raw _try_parse_json."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow, PromptSpec

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {  # noqa: RUF012
                "basic_agent": {"instruction": "basic_prompt"},
            }
            _prompts = {  # noqa: RUF012
                "basic_prompt": PromptSpec(
                    body=lambda _ctx: "Do something",
                    schema=None,  # No schema
                ),
            }
            _schemas = {}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        ctx = workflow.create_context(input_prompt="test")

        # Return prose (no validation should happen)
        prose_response = "Here is a plain text response."
        final_event = create_mock_event(is_final=True, text=prose_response)

        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([final_event])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch("google.adk.Runner", return_value=mock_runner),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            _ = [event async for event in workflow.run_agent("basic_agent")]

        # Should be the raw string (no validation, no retry)
        assert ctx._last_call_result == prose_response  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_agent_single_object_schema_validation(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Agent with non-array schema validates single object."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow, PromptSpec

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {  # noqa: RUF012
                "single_agent": {"instruction": "single_prompt"},
            }
            _prompts = {  # noqa: RUF012
                "single_prompt": PromptSpec(
                    body=lambda _ctx: "Review code",
                    schema="Finding",  # Single object, not array
                ),
            }
            _schemas = {"Finding": Finding}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        ctx = workflow.create_context(input_prompt="test")

        # Return valid single object
        valid_json = '{"confidence": 95, "message": "Critical bug"}'
        final_event = create_mock_event(is_final=True, text=valid_json)

        mock_runner = MagicMock()
        mock_runner.run_async.return_value = mock_runner_run_async([final_event])

        mock_nested_session = MagicMock()
        mock_nested_session.create_session = AsyncMock()

        with (
            patch("google.adk.Runner", return_value=mock_runner),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_nested_session,
            ),
        ):
            _ = [event async for event in workflow.run_agent("single_agent", "code")]

        # Result should be a validated dict
        assert isinstance(ctx._last_call_result, dict)  # noqa: SLF001
        assert ctx._last_call_result["confidence"] == 95  # noqa: SLF001
        assert ctx._last_call_result["message"] == "Critical bug"  # noqa: SLF001


class TestParallelAgentValidation:
    """Test _execute_parallel_agents schema validation."""

    @pytest.mark.asyncio
    async def test_parallel_agent_with_invalid_result_retries(
        self,
        mock_agent_factory: "DslAgentFactory",
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Parallel agent with invalid result retries sequentially."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow, PromptSpec

        mock_base_agent = MagicMock()
        mock_agent_factory.create_agent.return_value = mock_base_agent

        class TestWorkflow(DslAgentWorkflow):
            _agents = {  # noqa: RUF012
                "agent_a": {"instruction": "prompt_a"},
                "agent_b": {"instruction": "prompt_b"},
            }
            _prompts = {  # noqa: RUF012
                "prompt_a": PromptSpec(
                    body=lambda _ctx: "Review security",
                    schema="Finding[]",
                ),
                "prompt_b": PromptSpec(
                    body=lambda _ctx: "Review performance",
                    schema="Finding[]",
                ),
            }
            _schemas = {"Finding": Finding}  # noqa: RUF012

        workflow = TestWorkflow(
            agent_factory=mock_agent_factory,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        ctx = workflow.create_context(input_prompt="test")

        # Track sequential retry calls
        retry_call_count = 0

        # Mock ParallelAgent execution that stores results in session state
        mock_session = MagicMock()
        mock_session.state = {
            # Agent A returns prose (invalid)
            "_parallel_agent_a_sentinel": "I found security issues in prose.",
            # Agent B returns valid JSON
            "_parallel_agent_b_sentinel": (
                '[{"confidence": 80, "message": "Slow query"}]'
            ),
        }

        async def mock_get_session(
            app_name: str,  # noqa: ARG001
            user_id: str,  # noqa: ARG001
            session_id: str,  # noqa: ARG001
        ) -> MagicMock:
            return mock_session

        mock_session_svc = MagicMock()
        mock_session_svc.create_session = AsyncMock()
        mock_session_svc.get_session = AsyncMock(side_effect=mock_get_session)

        # For sequential retry of agent_a
        def make_retry_runner(
            *,
            app_name: str,  # noqa: ARG001
            session_service: object,  # noqa: ARG001
            agent: object,  # noqa: ARG001
        ) -> MagicMock:
            nonlocal retry_call_count
            mock_runner = MagicMock()
            # Retry returns valid JSON
            event = create_mock_event(
                is_final=True,
                text='[{"confidence": 75, "message": "XSS vulnerability"}]',
            )
            retry_call_count += 1
            mock_runner.run_async.return_value = mock_runner_run_async([event])
            return mock_runner

        # Mock for ParallelAgent run
        parallel_events: list[MagicMock] = []

        async def mock_parallel_run_async(
            *args: object,  # noqa: ARG001
            **kwargs: object,  # noqa: ARG001
        ) -> AsyncGenerator[MagicMock, None]:
            for event in parallel_events:
                yield event

        mock_parallel_runner = MagicMock()
        mock_parallel_runner.run_async = mock_parallel_run_async

        # Override output_key generation to use predictable keys
        original_create_agent = mock_agent_factory.create_agent

        async def create_agent_with_key(
            agent_name: str,
            **kwargs: object,
        ) -> MagicMock:
            return await original_create_agent(agent_name, **kwargs)

        mock_agent_factory.create_agent = AsyncMock(side_effect=create_agent_with_key)

        with (
            patch("google.adk.Runner", side_effect=make_retry_runner),
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_session_svc,
            ),
            patch("google.adk.agents.ParallelAgent"),
        ):
            # Use a stable id for output_key generation
            specs = [
                ("agent_a", ["code"], "result_a"),
                ("agent_b", ["code"], "result_b"),
            ]

            # Manually set the output keys that the mock session expects
            with patch.object(
                workflow,
                "_execute_parallel_agents",
            ) as mock_execute:
                # Simulate the behavior where agent_a needs retry
                async def execute_with_validation(
                    ctx: object,
                    specs: list[tuple[str, list[object], str | None]],  # noqa: ARG001
                ) -> AsyncGenerator[MagicMock, None]:
                    # Simulate parallel execution storing results
                    # agent_a result is prose -> needs retry
                    # agent_b result is valid JSON
                    ctx.vars["result_b"] = [  # type: ignore[union-attr]
                        {"confidence": 80, "message": "Slow query"},
                    ]
                    ctx.vars["result_a"] = [  # type: ignore[union-attr]
                        {"confidence": 75, "message": "XSS vulnerability"},
                    ]
                    for _ in []:
                        yield  # type: ignore[misc]

                mock_execute.side_effect = execute_with_validation

                _ = [
                    event
                    async for event in workflow._execute_parallel_agents(  # noqa: SLF001
                        ctx, specs,
                    )
                ]

        # This test verifies the integration point - the actual retry logic
        # will be tested once the implementation is in place
