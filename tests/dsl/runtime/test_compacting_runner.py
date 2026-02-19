"""Tests for mid-run compaction in workflow execution.

Test the CompactingRunner which monitors token usage during agent execution
and triggers compaction when the threshold is reached, avoiding compaction
during tool call/result pairs.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import types as genai_types

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session


def _make_event(
    author: str = "model",
    text: str | None = None,
    function_call: dict | None = None,
    function_response: dict | None = None,
    is_final: bool = False,
    usage_metadata: dict | None = None,
) -> "Event":
    """Create a mock ADK Event for testing.

    Use simple MagicMock without spec to avoid pydantic inspection issues.
    """
    parts = []
    if text:
        parts.append(genai_types.Part(text=text))
    if function_call:
        parts.append(
            genai_types.Part(
                function_call=genai_types.FunctionCall(
                    name=function_call["name"],
                    args=function_call.get("args", {}),
                ),
            ),
        )
    if function_response:
        parts.append(
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    name=function_response["name"],
                    response=function_response.get("response", {}),
                ),
            ),
        )

    content = genai_types.Content(role=author, parts=parts) if parts else None

    # Simple MagicMock without spec to avoid pydantic issues
    event = MagicMock()
    event.author = author
    event.content = content
    event.is_final_response = MagicMock(return_value=is_final)

    # Handle usage_metadata
    if usage_metadata:
        mock_usage = MagicMock()
        mock_usage.total_token_count = usage_metadata.get("total_token_count")
        mock_usage.prompt_token_count = usage_metadata.get("prompt_token_count")
        mock_usage.candidates_token_count = usage_metadata.get("candidates_token_count")
        event.usage_metadata = mock_usage
    else:
        event.usage_metadata = None

    return event


def _make_session(
    session_id: str = "test-session",
    app_name: str = "test-app",
    user_id: str = "test-user",
    events: list["Event"] | None = None,
) -> "Session":
    """Create a mock ADK Session for testing."""
    session = MagicMock()
    session.id = session_id
    session.app_name = app_name
    session.user_id = user_id
    session.events = events if events is not None else []
    session.state = {}
    return session


class TestIsToolCallEvent:
    """Tests for detecting tool call events."""

    def test_text_event_is_not_tool_call(self) -> None:
        """Regular text event is not a tool call."""
        from streetrace.dsl.runtime.compacting_runner import is_tool_call_event

        event = _make_event(text="Hello, world!")
        assert is_tool_call_event(event) is False

    def test_function_call_event_is_tool_call(self) -> None:
        """Event with function_call is a tool call."""
        from streetrace.dsl.runtime.compacting_runner import is_tool_call_event

        event = _make_event(function_call={"name": "search", "args": {"q": "test"}})
        assert is_tool_call_event(event) is True

    def test_function_response_event_is_not_tool_call(self) -> None:
        """Event with function_response is NOT a tool call (it's a result)."""
        from streetrace.dsl.runtime.compacting_runner import is_tool_call_event

        event = _make_event(
            function_response={"name": "search", "response": {"result": "found"}},
        )
        assert is_tool_call_event(event) is False

    def test_event_with_no_content_is_not_tool_call(self) -> None:
        """Event with no content is not a tool call."""
        from streetrace.dsl.runtime.compacting_runner import is_tool_call_event

        event = MagicMock()
        event.content = None
        assert is_tool_call_event(event) is False

    def test_event_with_empty_parts_is_not_tool_call(self) -> None:
        """Event with empty parts is not a tool call."""
        from streetrace.dsl.runtime.compacting_runner import is_tool_call_event

        event = MagicMock()
        event.content = MagicMock()
        event.content.parts = []
        assert is_tool_call_event(event) is False


class TestIsToolResultEvent:
    """Tests for detecting tool result events."""

    def test_text_event_is_not_tool_result(self) -> None:
        """Regular text event is not a tool result."""
        from streetrace.dsl.runtime.compacting_runner import is_tool_result_event

        event = _make_event(text="Hello, world!")
        assert is_tool_result_event(event) is False

    def test_function_response_event_is_tool_result(self) -> None:
        """Event with function_response is a tool result."""
        from streetrace.dsl.runtime.compacting_runner import is_tool_result_event

        event = _make_event(
            function_response={"name": "search", "response": {"result": "found"}},
        )
        assert is_tool_result_event(event) is True

    def test_function_call_event_is_not_tool_result(self) -> None:
        """Event with function_call is NOT a tool result."""
        from streetrace.dsl.runtime.compacting_runner import is_tool_result_event

        event = _make_event(function_call={"name": "search", "args": {"q": "test"}})
        assert is_tool_result_event(event) is False


class TestGetEventTokenCount:
    """Tests for extracting actual token counts from usage_metadata."""

    def test_returns_total_token_count(self) -> None:
        """Returns total_token_count when available."""
        from streetrace.dsl.runtime.compacting_runner import get_event_token_count

        event = _make_event(
            text="Hello",
            usage_metadata={"total_token_count": 100},
        )
        assert get_event_token_count(event) == 100

    def test_returns_sum_when_no_total(self) -> None:
        """Returns sum of prompt + candidates when total not available."""
        from streetrace.dsl.runtime.compacting_runner import get_event_token_count

        event = _make_event(
            text="Hello",
            usage_metadata={
                "prompt_token_count": 50,
                "candidates_token_count": 30,
            },
        )
        assert get_event_token_count(event) == 80

    def test_returns_none_when_no_usage(self) -> None:
        """Returns None when usage_metadata is not present."""
        from streetrace.dsl.runtime.compacting_runner import get_event_token_count

        event = _make_event(text="Hello")
        assert get_event_token_count(event) is None


class TestCompactingRunner:
    """Tests for CompactingRunner mid-run compaction behavior."""

    @pytest.mark.asyncio
    async def test_no_compaction_when_below_threshold(self) -> None:
        """Events yield normally when token count stays below threshold."""
        from streetrace.dsl.runtime.compacting_runner import (
            CompactingRunner,
            TruncateCompactionStrategy,
        )

        session = _make_session(events=[])
        mock_session_service = AsyncMock()
        # Strategy with threshold_ratio=0.8, max_tokens=1000 means threshold=800
        strategy = TruncateCompactionStrategy(threshold_ratio=0.8)

        runner = CompactingRunner(
            session_service=mock_session_service,
            compaction_strategy=strategy,
            max_tokens=1000,
            # 10 tokens per event, way below 800 threshold
            token_estimator=lambda _e, _m: 10,
        )

        events = [
            _make_event(text="Message 1"),
            _make_event(text="Message 2"),
            _make_event(text="Message 3", is_final=True),
        ]

        async def mock_run_async(*_args, **_kwargs) -> AsyncGenerator:
            for event in events:
                yield event

        mock_adk_runner = MagicMock()
        mock_adk_runner.run_async = mock_run_async
        runner._runner_factory = lambda _a, _s: mock_adk_runner  # noqa: SLF001

        collected = [event async for event in runner.run(
            agent=MagicMock(),
            session=session,
            message=None,
        )]

        assert len(collected) == 3

    @pytest.mark.asyncio
    async def test_compaction_triggers_at_threshold(self) -> None:
        """Compaction triggers when token count reaches threshold."""
        from streetrace.dsl.runtime.compacting_runner import (
            CompactingRunner,
            TruncateCompactionStrategy,
        )

        session = _make_session(events=[])
        compacted_session = _make_session(events=[_make_event(text="Summary")])

        mock_session_service = AsyncMock()
        mock_session_service.get_session.return_value = session
        strategy = TruncateCompactionStrategy(threshold_ratio=0.8)
        strategy.compact = AsyncMock(return_value=compacted_session)

        # Token sequence: 500 + 500 = 1000 > 800 threshold
        token_sequence = iter([500, 500, 100, 100])

        runner = CompactingRunner(
            session_service=mock_session_service,
            compaction_strategy=strategy,
            max_tokens=1000,
            token_estimator=lambda _e, _m: next(token_sequence, 10),
        )

        run_count = [0]

        async def mock_run_async(*_args, **_kwargs) -> AsyncGenerator:
            run_count[0] += 1
            if run_count[0] == 1:
                yield _make_event(text="Event 1")  # 500 tokens
                yield _make_event(text="Event 2")  # +500 = 1000, triggers compact
            else:
                yield _make_event(text="Final", is_final=True)  # 100 tokens

        mock_adk_runner = MagicMock()
        mock_adk_runner.run_async = mock_run_async
        runner._runner_factory = lambda _a, _s: mock_adk_runner  # noqa: SLF001

        collected = [event async for event in runner.run(
            agent=MagicMock(),
            session=session,
            message=None,
        )]

        assert len(collected) == 3  # 2 before compaction + 1 after
        strategy.compact.assert_called_once()
        assert run_count[0] == 2

    @pytest.mark.asyncio
    async def test_uses_actual_token_count_from_usage_metadata(self) -> None:
        """Uses actual token count from usage_metadata when available."""
        from streetrace.dsl.runtime.compacting_runner import (
            CompactingRunner,
            TruncateCompactionStrategy,
        )

        session = _make_session(events=[])
        compacted_session = _make_session(events=[])

        mock_session_service = AsyncMock()
        mock_session_service.get_session.return_value = session
        strategy = TruncateCompactionStrategy(threshold_ratio=0.8)
        strategy.compact = AsyncMock(return_value=compacted_session)

        # Token estimator returns 10, but usage_metadata has 500
        # This should use the actual 500, not the estimated 10
        runner = CompactingRunner(
            session_service=mock_session_service,
            compaction_strategy=strategy,
            max_tokens=1000,  # threshold = 800
            token_estimator=lambda _e, _m: 10,  # Would never trigger if used
        )

        run_count = [0]

        async def mock_run_async(*_args, **_kwargs) -> AsyncGenerator:
            run_count[0] += 1
            if run_count[0] == 1:
                # Events have usage_metadata with high token counts
                yield _make_event(
                    text="Event 1",
                    usage_metadata={"total_token_count": 500},
                )
                yield _make_event(
                    text="Event 2",
                    usage_metadata={"total_token_count": 500},
                )
            else:
                yield _make_event(text="Final", is_final=True)

        mock_adk_runner = MagicMock()
        mock_adk_runner.run_async = mock_run_async
        runner._runner_factory = lambda _a, _s: mock_adk_runner  # noqa: SLF001

        collected = [event async for event in runner.run(
            agent=MagicMock(),
            session=session,
            message=None,
        )]

        # Should trigger compaction because actual counts (500+500=1000) > 800
        assert len(collected) == 3
        strategy.compact.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_compaction_after_tool_call(self) -> None:
        """Compaction is deferred when last event is a tool call."""
        from streetrace.dsl.runtime.compacting_runner import (
            CompactingRunner,
            TruncateCompactionStrategy,
        )

        session = _make_session(events=[])
        mock_session_service = AsyncMock()
        strategy = TruncateCompactionStrategy(threshold_ratio=0.8)

        # Tokens: 400, 500 (tool call exceeds threshold), 50 (tool result), 10
        token_sequence = iter([400, 500, 50, 10, 10, 10])

        def track_tokens(_event, _model):
            return next(token_sequence, 10)

        runner = CompactingRunner(
            session_service=mock_session_service,
            compaction_strategy=strategy,
            max_tokens=1000,
            token_estimator=track_tokens,
        )

        events = [
            _make_event(text="Setup"),
            _make_event(function_call={"name": "search", "args": {}}),
            _make_event(function_response={"name": "search", "response": {}}),
            _make_event(text="Final", is_final=True),
        ]

        compacted_session = _make_session(events=[_make_event(text="Summary")])
        mock_session_service.get_session.return_value = session
        strategy.compact = AsyncMock(return_value=compacted_session)

        run_count = [0]
        events_before_compaction: list = []

        async def mock_run_async(*_args, **_kwargs) -> AsyncGenerator:
            run_count[0] += 1
            if run_count[0] == 1:
                for event in events:
                    events_before_compaction.append(event)
                    yield event
            else:
                yield _make_event(text="After compaction", is_final=True)

        mock_adk_runner = MagicMock()
        mock_adk_runner.run_async = mock_run_async
        runner._runner_factory = lambda _a, _s: mock_adk_runner  # noqa: SLF001

        collected = [event async for event in runner.run(
            agent=MagicMock(),
            session=session,
            message=None,
        )]

        # Tool call/result pair should complete together
        assert len(events_before_compaction) >= 3
        assert events_before_compaction[1].content.parts[0].function_call is not None
        assert len(collected) >= 4

    @pytest.mark.asyncio
    async def test_session_refetched_before_compaction(self) -> None:
        """Session is re-fetched to get latest events before compaction."""
        from streetrace.dsl.runtime.compacting_runner import (
            CompactingRunner,
            TruncateCompactionStrategy,
        )

        initial_session = _make_session(events=[])
        updated_session = _make_session(events=[_make_event(text="From runner")])
        compacted_session = _make_session(events=[_make_event(text="Summary")])

        mock_session_service = AsyncMock()
        mock_session_service.get_session.return_value = updated_session
        strategy = TruncateCompactionStrategy(threshold_ratio=0.8)
        strategy.compact = AsyncMock(return_value=compacted_session)

        token_sequence = iter([100, 10])

        runner = CompactingRunner(
            session_service=mock_session_service,
            compaction_strategy=strategy,
            max_tokens=100,  # Low threshold = 80
            token_estimator=lambda _e, _m: next(token_sequence, 10),
        )

        run_count = [0]

        async def mock_run_async(*_args, **_kwargs) -> AsyncGenerator:
            run_count[0] += 1
            if run_count[0] == 1:
                yield _make_event(text="Event 1")  # 100 >= 80, triggers
            else:
                yield _make_event(text="Done", is_final=True)

        mock_adk_runner = MagicMock()
        mock_adk_runner.run_async = mock_run_async
        runner._runner_factory = lambda _a, _s: mock_adk_runner  # noqa: SLF001

        collected = [event async for event in runner.run(
            agent=MagicMock(),
            session=initial_session,
            message=None,
        )]

        mock_session_service.get_session.assert_called()
        compact_call = strategy.compact.call_args
        assert compact_call[0][0] == updated_session
        assert len(collected) == 2

    @pytest.mark.asyncio
    async def test_runner_restarts_after_compaction(self) -> None:
        """A new runner is created after compaction to continue execution."""
        from streetrace.dsl.runtime.compacting_runner import (
            CompactingRunner,
            TruncateCompactionStrategy,
        )

        session = _make_session(events=[])
        compacted_session = _make_session(events=[_make_event(text="Summary")])

        mock_session_service = AsyncMock()
        mock_session_service.get_session.return_value = session
        strategy = TruncateCompactionStrategy(threshold_ratio=0.8)
        strategy.compact = AsyncMock(return_value=compacted_session)

        token_sequence = iter([100, 10])

        runner = CompactingRunner(
            session_service=mock_session_service,
            compaction_strategy=strategy,
            max_tokens=100,
            token_estimator=lambda _e, _m: next(token_sequence, 10),
        )

        runner_count = [0]
        run_count = [0]

        async def mock_run_async(*_args, **_kwargs) -> AsyncGenerator:
            run_count[0] += 1
            if run_count[0] == 1:
                yield _make_event(text="Triggers")
            else:
                yield _make_event(text="After", is_final=True)

        def create_runner(_agent, _sess):
            runner_count[0] += 1
            mock_runner = MagicMock()
            mock_runner.run_async = mock_run_async
            return mock_runner

        runner._runner_factory = create_runner  # noqa: SLF001

        collected = [event async for event in runner.run(
            agent=MagicMock(),
            session=session,
            message=None,
        )]

        assert runner_count[0] == 2
        assert run_count[0] == 2
        assert len(collected) == 2

    @pytest.mark.asyncio
    async def test_continuation_message_after_compaction(self) -> None:
        """Continuation message is sent after compaction (not the original)."""
        from streetrace.dsl.runtime.compacting_runner import (
            CompactingRunner,
            TruncateCompactionStrategy,
        )

        session = _make_session(events=[])
        compacted_session = _make_session(events=[])

        mock_session_service = AsyncMock()
        mock_session_service.get_session.return_value = session
        strategy = TruncateCompactionStrategy(threshold_ratio=0.8)
        strategy.compact = AsyncMock(return_value=compacted_session)

        token_sequence = iter([100, 10])

        runner = CompactingRunner(
            session_service=mock_session_service,
            compaction_strategy=strategy,
            max_tokens=100,
            token_estimator=lambda _e, _m: next(token_sequence, 10),
        )

        original_message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text="Hello")],
        )

        messages_received: list = []
        run_count = [0]

        async def mock_run_async(user_id, session_id, new_message=None):  # noqa: ARG001
            run_count[0] += 1
            messages_received.append(new_message)
            if run_count[0] == 1:
                yield _make_event(text="First")
            else:
                yield _make_event(text="Done", is_final=True)

        mock_adk_runner = MagicMock()
        mock_adk_runner.run_async = mock_run_async
        runner._runner_factory = lambda _a, _s: mock_adk_runner  # noqa: SLF001

        collected = [event async for event in runner.run(
            agent=MagicMock(),
            session=session,
            message=original_message,
        )]

        assert len(messages_received) == 2
        assert messages_received[0] == original_message
        # After compaction, a continuation message is sent (not None, not original)
        assert messages_received[1] is not None
        assert messages_received[1] != original_message
        assert "compacted" in messages_received[1].parts[0].text.lower()
        assert len(collected) == 2

    @pytest.mark.asyncio
    async def test_multiple_compactions_in_long_conversation(self) -> None:
        """Multiple compactions can occur in a very long conversation."""
        from streetrace.dsl.runtime.compacting_runner import (
            CompactingRunner,
            TruncateCompactionStrategy,
        )

        session = _make_session(events=[])
        compacted_session = _make_session(events=[])

        mock_session_service = AsyncMock()
        mock_session_service.get_session.return_value = session
        strategy = TruncateCompactionStrategy(threshold_ratio=0.8)
        strategy.compact = AsyncMock(return_value=compacted_session)

        # Each run: 100 > 80 threshold triggers, except last
        token_sequence = iter([100, 100, 100, 10])

        runner = CompactingRunner(
            session_service=mock_session_service,
            compaction_strategy=strategy,
            max_tokens=100,
            token_estimator=lambda _e, _m: next(token_sequence, 10),
        )

        run_count = [0]

        async def mock_run_async(*_args, **_kwargs) -> AsyncGenerator:
            run_count[0] += 1
            if run_count[0] < 4:
                yield _make_event(text=f"Event {run_count[0]}")
            else:
                yield _make_event(text="Final", is_final=True)

        mock_adk_runner = MagicMock()
        mock_adk_runner.run_async = mock_run_async
        runner._runner_factory = lambda _a, _s: mock_adk_runner  # noqa: SLF001

        collected = [event async for event in runner.run(
            agent=MagicMock(),
            session=session,
            message=None,
        )]

        assert len(collected) == 4
        assert strategy.compact.call_count == 3


class TestCompactionStrategy:
    """Tests for the compaction strategy interface."""

    def test_strategy_has_threshold_ratio(self) -> None:
        """Strategy provides threshold_ratio property."""
        from streetrace.dsl.runtime.compacting_runner import TruncateCompactionStrategy

        strategy = TruncateCompactionStrategy(threshold_ratio=0.75)
        assert strategy.threshold_ratio == 0.75

    def test_default_threshold_ratio(self) -> None:
        """Strategy uses default threshold_ratio if not specified."""
        from streetrace.dsl.runtime.compacting_runner import (
            DEFAULT_THRESHOLD_RATIO,
            TruncateCompactionStrategy,
        )

        strategy = TruncateCompactionStrategy()
        assert strategy.threshold_ratio == DEFAULT_THRESHOLD_RATIO

    @pytest.mark.asyncio
    async def test_truncate_strategy_keeps_recent_events(self) -> None:
        """Truncate strategy keeps system message and recent events."""
        from streetrace.dsl.runtime.compacting_runner import TruncateCompactionStrategy

        strategy = TruncateCompactionStrategy(keep_recent=3)

        events = [
            _make_event(author="system", text="System prompt"),
            _make_event(author="user", text="Message 1"),
            _make_event(author="model", text="Response 1"),
            _make_event(author="user", text="Message 2"),
            _make_event(author="model", text="Response 2"),
            _make_event(author="user", text="Message 3"),
            _make_event(author="model", text="Response 3"),
        ]

        session = _make_session(events=events)
        mock_service = AsyncMock()
        compacted = _make_session()
        mock_service.replace_events.return_value = compacted

        await strategy.compact(session, mock_service)

        mock_service.replace_events.assert_called_once()
        new_events = mock_service.replace_events.call_args.kwargs["new_events"]
        assert len(new_events) == 4  # system + 3 recent

    @pytest.mark.asyncio
    async def test_summarize_strategy_creates_summary_event(self) -> None:
        """Summarize strategy creates a summary event for older messages."""
        from streetrace.dsl.runtime.compacting_runner import (
            SummarizeCompactionStrategy,
        )

        mock_llm = AsyncMock()
        mock_llm.summarize.return_value = "Summary of conversation"

        strategy = SummarizeCompactionStrategy(llm=mock_llm, keep_recent=2)

        events = [
            _make_event(author="system", text="System prompt"),
            _make_event(author="user", text="Old message"),
            _make_event(author="model", text="Old response"),
            _make_event(author="user", text="Recent message"),
            _make_event(author="model", text="Recent response"),
        ]

        session = _make_session(events=events)
        mock_service = AsyncMock()
        compacted = _make_session()
        mock_service.replace_events.return_value = compacted

        await strategy.compact(session, mock_service)

        mock_llm.summarize.assert_called_once()
        mock_service.replace_events.assert_called_once()


class TestTokenCounting:
    """Tests for token counting functionality."""

    def test_estimate_event_tokens_for_text_event(self) -> None:
        """Token estimation for text event uses litellm."""
        from unittest.mock import patch

        from streetrace.dsl.runtime.compacting_runner import estimate_event_tokens

        event = _make_event(text="Hello, world!")

        with patch("litellm.token_counter", return_value=5):
            tokens = estimate_event_tokens(event, "gpt-4")

        assert tokens == 5

    def test_estimate_event_tokens_for_empty_event(self) -> None:
        """Token estimation for event with no content is 0."""
        from streetrace.dsl.runtime.compacting_runner import estimate_event_tokens

        event = MagicMock()
        event.content = None

        tokens = estimate_event_tokens(event, "gpt-4")
        assert tokens == 0

    def test_estimate_event_tokens_for_function_call(self) -> None:
        """Token estimation includes function call overhead."""
        from unittest.mock import patch

        from streetrace.dsl.runtime.compacting_runner import estimate_event_tokens

        event = _make_event(
            function_call={"name": "search", "args": {"query": "test"}},
        )

        with patch("litellm.token_counter", return_value=20):
            tokens = estimate_event_tokens(event, "gpt-4")

        assert tokens >= 20
