"""Mid-run compaction for ADK Runner execution.

Monitor token usage during agent execution and trigger compaction when
the threshold is reached, avoiding compaction during tool call/result pairs.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING, Protocol

from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk import Runner
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai import types as genai_types

logger = get_logger(__name__)

DEFAULT_THRESHOLD_RATIO = 0.80
"""Default ratio of context window at which to trigger compaction."""

DEFAULT_CONTEXT_WINDOW = 128_000
"""Default context window size when model info is unavailable."""


def is_tool_call_event(event: "Event") -> bool:
    """Check if event contains a function call (tool invocation).

    Args:
        event: The ADK event to check.

    Returns:
        True if the event contains a function call, False otherwise.

    """
    if not event.content or not event.content.parts:
        return False
    return any(part.function_call for part in event.content.parts)


def is_tool_result_event(event: "Event") -> bool:
    """Check if event contains a function response (tool result).

    Args:
        event: The ADK event to check.

    Returns:
        True if the event contains a function response, False otherwise.

    """
    if not event.content or not event.content.parts:
        return False
    return any(part.function_response for part in event.content.parts)


def get_event_token_count(event: "Event") -> int | None:
    """Extract actual token count from event usage_metadata.

    ADK events contain usage_metadata with actual token counts from the LLM.
    This is more accurate than estimation.

    Args:
        event: The ADK event to get token count from.

    Returns:
        Total token count from usage_metadata, or None if not available.

    """
    usage = getattr(event, "usage_metadata", None)
    if usage is None:
        return None

    # Try total_token_count first (most accurate)
    total = getattr(usage, "total_token_count", None)
    if total is not None:
        return int(total)

    # Fall back to sum of prompt + candidates
    prompt = getattr(usage, "prompt_token_count", 0) or 0
    candidates = getattr(usage, "candidates_token_count", 0) or 0
    if prompt or candidates:
        return prompt + candidates

    return None


def estimate_event_tokens(event: "Event", model: str) -> int:
    """Estimate tokens in an event using litellm.token_counter.

    Use this for forecasting token count of pre-existing session events
    that don't have usage_metadata (e.g., from previous runs).

    Args:
        event: The ADK event to estimate tokens for.
        model: The model identifier for tokenization.

    Returns:
        Estimated token count for the event.

    """
    if not event.content or not event.content.parts:
        return 0

    import litellm

    # Build a message representation for token counting
    parts_text = []
    for part in event.content.parts:
        if hasattr(part, "text") and part.text:
            parts_text.append(part.text)
        elif part.function_call:
            # Approximate function call tokens
            fc = part.function_call
            parts_text.append(f"function_call: {fc.name} args: {fc.args}")
        elif part.function_response:
            # Approximate function response tokens
            fr = part.function_response
            parts_text.append(f"function_response: {fr.name} response: {fr.response}")

    if not parts_text:
        return 0

    content = " ".join(parts_text)
    messages = [{"role": event.content.role or "assistant", "content": content}]

    try:
        return int(litellm.token_counter(model=model, messages=messages))
    except Exception:  # noqa: BLE001
        # Fallback: rough estimate of 4 chars per token
        return len(content) // 4


class CompactionStrategy(ABC):
    """Base class for session compaction strategies.

    Each strategy defines its own threshold ratio at which compaction triggers.
    """

    @property
    def threshold_ratio(self) -> float:
        """Ratio of context window at which to trigger compaction.

        Returns:
            Threshold ratio (0.0 to 1.0). Default is 0.80 (80%).

        """
        return DEFAULT_THRESHOLD_RATIO

    @abstractmethod
    async def compact(
        self,
        session: "Session",
        session_service: "BaseSessionService",
    ) -> "Session":
        """Compact the session history.

        Args:
            session: The session to compact.
            session_service: The session service for persistence.

        Returns:
            The compacted session.

        """


class TruncateCompactionStrategy(CompactionStrategy):
    """Compaction strategy that truncates old events, keeping recent ones."""

    def __init__(
        self,
        *,
        keep_recent: int = 6,
        threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
    ) -> None:
        """Initialize the truncate strategy.

        Args:
            keep_recent: Number of recent events to keep (excluding system).
            threshold_ratio: Ratio of context window at which to trigger compaction.

        """
        self._keep_recent = keep_recent
        self._threshold_ratio = threshold_ratio

    @property
    def threshold_ratio(self) -> float:
        """Ratio of context window at which to trigger compaction."""
        return self._threshold_ratio

    async def compact(
        self,
        session: "Session",
        session_service: "BaseSessionService",
    ) -> "Session":
        """Truncate session by keeping system message and recent events.

        Args:
            session: The session to compact.
            session_service: The session service for persistence.

        Returns:
            The compacted session.

        """
        events = session.events
        if len(events) <= self._keep_recent + 1:
            # Nothing to truncate
            return session

        # Keep first event (usually system) and last N events
        new_events = []

        # Check if first event is system-like (keep it)
        if events and events[0].author in ("system", "user"):
            new_events.append(events[0])
            recent_start = max(1, len(events) - self._keep_recent)
        else:
            recent_start = max(0, len(events) - self._keep_recent)

        # Add recent events
        new_events.extend(events[recent_start:])

        logger.info(
            "Truncating session %s: %d -> %d events",
            session.id,
            len(events),
            len(new_events),
        )

        # Use session service to replace events
        # Note: replace_events is on JSONSessionService, not BaseSessionService
        compacted = await session_service.replace_events(  # type: ignore[attr-defined]
            session=session,
            new_events=new_events,
        )
        return compacted if compacted else session


class SummarizeLlm(Protocol):
    """Protocol for LLM used in summarization."""

    async def summarize(self, text: str) -> str:
        """Summarize the given text.

        Args:
            text: The text to summarize.

        Returns:
            The summary.

        """
        ...


class SummarizeCompactionStrategy(CompactionStrategy):
    """Compaction strategy that summarizes old events using an LLM.

    This strategy is token-aware: it summarizes ALL events (not just old ones)
    to ensure the result fits within the context window.
    """

    def __init__(
        self,
        *,
        llm: SummarizeLlm,
        keep_recent: int = 4,
        threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
    ) -> None:
        """Initialize the summarize strategy.

        Args:
            llm: The LLM to use for summarization.
            keep_recent: Number of recent events to keep verbatim (if small enough).
            threshold_ratio: Ratio of context window at which to trigger compaction.

        """
        self._llm = llm
        self._keep_recent = keep_recent
        self._threshold_ratio = threshold_ratio

    @property
    def threshold_ratio(self) -> float:
        """Ratio of context window at which to trigger compaction."""
        return self._threshold_ratio

    async def compact(
        self,
        session: "Session",
        session_service: "BaseSessionService",
    ) -> "Session":
        """Summarize events to fit within context window.

        Unlike simple truncation, this strategy summarizes ALL events into a
        single concise summary. This ensures the result is small regardless of
        how large the original events were.

        Args:
            session: The session to compact.
            session_service: The session service for persistence.

        Returns:
            The compacted session.

        """
        from google.adk.events import Event
        from google.genai import types as genai_types

        events = session.events
        if len(events) <= 1:
            return session

        # Summarize ALL events (except system prompt if present)
        start_idx = 0
        new_events = []

        # Keep first event if it's a system prompt
        if events and events[0].author == "system":
            new_events.append(events[0])
            start_idx = 1

        events_to_summarize = events[start_idx:]

        if events_to_summarize:
            # Generate summary of ALL conversation events
            text_to_summarize = self._events_to_text(events_to_summarize)
            summary = await self._llm.summarize(text_to_summarize)

            # Create summary event
            summary_event = Event(
                author="system",
                content=genai_types.Content(
                    role="user",
                    parts=[
                        genai_types.Part(
                            text=f"[Previous conversation summary: {summary}]",
                        ),
                    ],
                ),
            )
            new_events.append(summary_event)

        logger.info(
            "Summarizing session %s: %d -> %d events (summarized %d)",
            session.id,
            len(events),
            len(new_events),
            len(events_to_summarize),
        )

        # Note: replace_events is on JSONSessionService, not BaseSessionService
        compacted = await session_service.replace_events(  # type: ignore[attr-defined]
            session=session,
            new_events=new_events,
        )
        return compacted if compacted else session

    def _events_to_text(self, events: list["Event"]) -> str:
        """Convert events to text for summarization.

        Args:
            events: The events to convert.

        Returns:
            Text representation of the events.

        """
        lines: list[str] = []
        for event in events:
            if not event.content or not event.content.parts:
                continue
            role = event.author or "unknown"
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    # Truncate very long texts to avoid overwhelming the summarizer
                    text = part.text
                    max_text_len = 2000
                    if len(text) > max_text_len:
                        text = text[:max_text_len] + "... [truncated]"
                    lines.append(f"{role}: {text}")
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    lines.append(f"{role}: [Called tool: {fc.name}]")
                elif hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    lines.append(f"{role}: [Tool {fr.name} returned result]")
        return "\n".join(lines)


TokenEstimator = Callable[["Event", str], int]
"""Type alias for token estimation function (for forecasting)."""

RunnerFactory = Callable[["BaseAgent", "Session"], "Runner"]
"""Type alias for runner factory function."""


class CompactingRunner:
    """Runner wrapper that monitors tokens and compacts mid-run when needed.

    This class wraps the ADK Runner to provide automatic compaction when
    the token count approaches the model's context window limit. It avoids
    compacting during tool call/result pairs to maintain conversation coherence.

    Token counting strategy:
    - For events from current run: Use actual counts from usage_metadata
    - For pre-existing session events: Estimate using litellm.token_counter
    """

    def __init__(
        self,
        *,
        session_service: "BaseSessionService",
        compaction_strategy: CompactionStrategy,
        max_tokens: int | None = None,
        model: str = "gpt-4",
        token_estimator: TokenEstimator | None = None,
    ) -> None:
        """Initialize the compacting runner.

        Args:
            session_service: The ADK session service.
            compaction_strategy: Strategy to use for compaction.
                The strategy defines the threshold_ratio.
            max_tokens: Maximum context window tokens. If None, uses model default.
            model: Model identifier for token estimation.
            token_estimator: Optional custom token estimator for testing.

        """
        self._session_service = session_service
        self._compaction_strategy = compaction_strategy
        self._max_tokens = max_tokens
        self._model = model
        self._token_estimator = token_estimator or estimate_event_tokens
        self._runner_factory: RunnerFactory | None = None

    async def run(
        self,
        *,
        agent: "BaseAgent",
        session: "Session",
        message: "genai_types.Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Execute agent with mid-run compaction when threshold reached.

        Args:
            agent: The ADK agent to execute.
            session: The session for conversation persistence.
            message: The user message to process, or None.

        Yields:
            ADK events from execution.

        """
        threshold = self._calculate_threshold()
        # Estimate tokens for pre-existing session (forecasting)
        running_token_count = self._estimate_session_tokens(session)
        current_message = message
        current_session = session

        while True:
            runner = self._create_runner(agent, current_session)
            compaction_needed = False
            last_event_was_tool_call = False

            # Get the async generator so we can properly close it if we break
            event_stream = runner.run_async(
                user_id=current_session.user_id,
                session_id=current_session.id,
                new_message=current_message,
            )

            try:
                async for event in event_stream:
                    # Get actual token count from event, fall back to estimation
                    event_tokens = get_event_token_count(event)
                    if event_tokens is None:
                        event_tokens = self._token_estimator(event, self._model)
                    running_token_count += event_tokens

                    yield event

                    # Track if this event was a tool call
                    last_event_was_tool_call = is_tool_call_event(event)

                    # Check threshold, don't compact after tool call (wait for result)
                    if (
                        running_token_count >= threshold
                        and not last_event_was_tool_call
                    ):
                        logger.info(
                            "Token threshold reached (%d >= %d), triggering compaction",
                            running_token_count,
                            threshold,
                        )
                        compaction_needed = True
                        break
            finally:
                # Properly close the async generator to clean up MCP sessions
                # and other resources when we break for compaction
                await event_stream.aclose()

            if not compaction_needed:
                # Normal completion
                break

            # Re-fetch session to get all latest events
            updated_session = await self._session_service.get_session(
                app_name=current_session.app_name,
                user_id=current_session.user_id,
                session_id=current_session.id,
            )
            if updated_session is None:
                logger.warning("Session not found after compaction trigger")
                break

            # Compact the session
            current_session = await self._compaction_strategy.compact(
                updated_session,
                self._session_service,
            )

            # Re-estimate token count for compacted session
            running_token_count = self._estimate_session_tokens(current_session)

            # Create a continuation message for ADK after compaction.
            # ADK requires new_message when the session has events; we can't pass None.
            # This minimal message signals the model to continue from where it left off.
            from google.genai import types as genai_types

            current_message = genai_types.Content(
                role="user",
                parts=[
                    genai_types.Part.from_text(
                        text="[Session compacted. Continue from where you left off.]",
                    ),
                ],
            )

            logger.info(
                "Compaction complete, restarting runner. New token count: %d",
                running_token_count,
            )

    def _create_runner(
        self,
        agent: "BaseAgent",
        session: "Session",
    ) -> "Runner":
        """Create an ADK Runner instance.

        Args:
            agent: The agent to run.
            session: The session for context.

        Returns:
            Configured ADK Runner.

        """
        # Allow injection for testing
        if self._runner_factory:
            return self._runner_factory(agent, session)

        from google.adk import Runner

        return Runner(
            app_name=session.app_name,
            session_service=self._session_service,
            agent=agent,
        )

    def _calculate_threshold(self) -> int:
        """Calculate the token threshold for triggering compaction.

        Uses the threshold_ratio from the compaction strategy.

        Returns:
            Token count threshold.

        """
        max_tokens = self._max_tokens
        if max_tokens is None:
            max_tokens = self._get_model_max_tokens()
        return int(max_tokens * self._compaction_strategy.threshold_ratio)

    def _get_model_max_tokens(self) -> int:
        """Get the max tokens for the configured model.

        Returns:
            Maximum input tokens for the model.

        """
        try:
            import litellm

            model_info = litellm.get_model_info(self._model)
            if model_info:
                max_input = model_info.get("max_input_tokens")
                if max_input is not None:
                    return int(max_input)
        except Exception:  # noqa: BLE001
            logger.warning("Could not get model info for %s", self._model)

        return DEFAULT_CONTEXT_WINDOW

    def _estimate_session_tokens(self, session: "Session") -> int:
        """Estimate total tokens in session events.

        Used for forecasting token count of pre-existing session events.
        For events from current run, use get_event_token_count() instead.

        Args:
            session: The session to estimate tokens for.

        Returns:
            Estimated total token count.

        """
        total = 0
        for event in session.events:
            total += self._token_estimator(event, self._model)
        return total
