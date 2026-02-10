"""History compaction for DSL agent conversations.

Provide automatic history management to prevent context window overflow.
When conversation history reaches 80% of the model's context limit, apply
either summarize or truncate strategy.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.events import Event

logger = get_logger(__name__)

COMPACTION_THRESHOLD = 0.80
"""Trigger compaction when history reaches 80% of context window."""

DEFAULT_CONTEXT_WINDOW = 128_000
"""Default context window size when model info is unavailable."""

MINIMUM_RECENT_MESSAGES = 4
"""Minimum number of recent messages to preserve during truncation."""


@dataclass
class CompactionResult:
    """Result of a history compaction operation."""

    compacted_messages: list[dict[str, object]]
    """The compacted message history."""

    original_tokens: int
    """Token count before compaction."""

    compacted_tokens: int
    """Token count after compaction."""

    messages_removed: int
    """Number of messages removed during compaction."""


class CompactionStrategy(ABC):
    """Base class for history compaction strategies."""

    @abstractmethod
    async def compact(
        self,
        messages: list[dict[str, object]],
        target_tokens: int,
        model: str,
    ) -> list[dict[str, object]]:
        """Compact messages to fit within target token limit.

        Args:
            messages: The conversation history to compact.
            target_tokens: Target token count after compaction.
            model: The model identifier for token counting.

        Returns:
            Compacted message list.

        """


class TruncateStrategy(CompactionStrategy):
    """Truncate strategy that keeps first and most recent messages.

    Preserve the system message and initial context, plus the most
    recent messages that fit within the target token limit.
    """

    async def compact(
        self,
        messages: list[dict[str, object]],
        target_tokens: int,
        model: str,
    ) -> list[dict[str, object]]:
        """Truncate messages by removing middle portion.

        Keep the first message (usually system/context) and as many
        recent messages as will fit within the target token count.

        Args:
            messages: The conversation history to compact.
            target_tokens: Target token count after compaction.
            model: The model identifier for token counting.

        Returns:
            Truncated message list.

        """
        if len(messages) <= MINIMUM_RECENT_MESSAGES:
            return messages

        # Keep first message and find how many recent messages fit
        first_message = [messages[0]] if messages else []
        remaining = messages[1:]

        # Start from most recent and work backwards
        first_tokens = _count_message_tokens(first_message, model)
        result_messages = first_message.copy()
        current_tokens = first_tokens

        for msg in reversed(remaining):
            msg_tokens = _count_message_tokens([msg], model)
            if current_tokens + msg_tokens <= target_tokens:
                result_messages.insert(1, msg)
                current_tokens += msg_tokens
            else:
                break

        logger.debug(
            "Truncated history from %d to %d messages",
            len(messages),
            len(result_messages),
        )

        return result_messages


class SummarizeStrategy(CompactionStrategy):
    """Summarize strategy that uses LLM to create a summary.

    Create a condensed summary of older messages while preserving
    the goal and recent context.
    """

    def __init__(
        self,
        *,
        llm_client: object | None = None,
    ) -> None:
        """Initialize the summarize strategy.

        Args:
            llm_client: Optional LLM client for generating summaries.
                If not provided, falls back to truncation.

        """
        self._llm_client = llm_client

    async def compact(
        self,
        messages: list[dict[str, object]],
        target_tokens: int,
        model: str,
    ) -> list[dict[str, object]]:
        """Summarize older messages while keeping recent context.

        Create an LLM-generated summary of older messages and prepend
        it as context for the conversation.

        Args:
            messages: The conversation history to compact.
            target_tokens: Target token count after compaction.
            model: The model identifier for token counting.

        Returns:
            Compacted message list with summary.

        """
        if len(messages) <= MINIMUM_RECENT_MESSAGES:
            return messages

        if self._llm_client is None:
            # Fall back to truncation if no LLM client available
            logger.debug("No LLM client available, falling back to truncation")
            truncate = TruncateStrategy()
            return await truncate.compact(messages, target_tokens, model)

        # Split messages: keep system/first message, summarize middle, keep recent
        first_message = messages[0] if messages else None
        recent_count = min(MINIMUM_RECENT_MESSAGES, len(messages) - 1)
        recent_messages = messages[-recent_count:] if recent_count > 0 else []
        has_middle = len(messages) > recent_count + 1
        middle_messages = messages[1:-recent_count] if has_middle else []

        if not middle_messages:
            return messages

        # Generate summary of middle messages
        summary = await self._generate_summary(middle_messages, model)

        # Build result with summary as context
        result = []
        if first_message:
            result.append(first_message)

        if summary:
            result.append(
                {
                    "role": "system",
                    "content": f"[Previous conversation summary: {summary}]",
                },
            )

        result.extend(recent_messages)

        logger.debug(
            "Summarized history: %d messages -> %d (summary of %d middle messages)",
            len(messages),
            len(result),
            len(middle_messages),
        )

        return result

    async def _generate_summary(
        self,
        messages: list[dict[str, object]],
        model: str,
    ) -> str:
        """Generate a summary of the given messages.

        Args:
            messages: Messages to summarize.
            model: Model to use for summarization.

        Returns:
            Summary text.

        """
        # Format messages for summarization
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")

        conversation_text = "\n".join(formatted)

        summary_prompt = (
            "Summarize the following conversation concisely, "
            "preserving key decisions, context, and any important details:\n\n"
            f"{conversation_text}\n\n"
            "Summary:"
        )

        # Use the LLM client to generate summary
        if not hasattr(self._llm_client, "complete"):
            return ""

        try:
            response = await self._llm_client.complete(
                model=model,
                prompt=summary_prompt,
                max_tokens=500,
            )
            return str(response)
        except (ValueError, RuntimeError, OSError):
            logger.exception("Failed to generate summary")
            return ""


class HistoryCompactor:
    """Manage conversation history compaction for DSL agents.

    Check if history exceeds threshold and compact using configured strategy.
    """

    def __init__(
        self,
        *,
        strategy: str = "truncate",
        llm_client: object | None = None,
    ) -> None:
        """Initialize the history compactor.

        Args:
            strategy: Compaction strategy name ('summarize' or 'truncate').
            llm_client: Optional LLM client for summarize strategy.

        """
        self._strategy_name = strategy
        self._llm_client = llm_client

    def _get_strategy(self) -> CompactionStrategy:
        """Get the compaction strategy instance."""
        if self._strategy_name == "summarize":
            return SummarizeStrategy(llm_client=self._llm_client)
        return TruncateStrategy()

    def should_compact(
        self,
        messages: list[dict[str, object]],
        model: str,
        max_input_tokens: int | None = None,
    ) -> bool:
        """Check if history should be compacted.

        Args:
            messages: Current conversation history.
            model: Model identifier for context window lookup.
            max_input_tokens: Optional explicit max input tokens from DSL.

        Returns:
            True if history exceeds threshold and should be compacted.

        """
        current_tokens = _count_message_tokens(messages, model)
        context_window = _get_context_window(model, max_input_tokens)
        threshold = int(context_window * COMPACTION_THRESHOLD)

        should = current_tokens >= threshold

        if should:
            logger.debug(
                "History compaction needed: %d tokens >= %d threshold (%.0f%% of %d)",
                current_tokens,
                threshold,
                COMPACTION_THRESHOLD * 100,
                context_window,
            )

        return should

    async def compact(
        self,
        messages: list[dict[str, object]],
        model: str,
        max_input_tokens: int | None = None,
    ) -> CompactionResult:
        """Compact conversation history.

        Args:
            messages: Current conversation history.
            model: Model identifier for token counting.
            max_input_tokens: Optional explicit max input tokens from DSL.

        Returns:
            CompactionResult with compacted messages and metrics.

        """
        original_tokens = _count_message_tokens(messages, model)
        context_window = _get_context_window(model, max_input_tokens)

        # Target 50% of context window after compaction to leave room
        target_tokens = int(context_window * 0.5)

        strategy = self._get_strategy()
        compacted = await strategy.compact(messages, target_tokens, model)
        compacted_tokens = _count_message_tokens(compacted, model)

        return CompactionResult(
            compacted_messages=compacted,
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            messages_removed=len(messages) - len(compacted),
        )

    def count_tokens(
        self,
        messages: list[dict[str, object]],
        model: str,
    ) -> int:
        """Count tokens in messages.

        Args:
            messages: Messages to count tokens for.
            model: Model identifier for tokenization.

        Returns:
            Token count.

        """
        return _count_message_tokens(messages, model)


def _count_message_tokens(
    messages: list[dict[str, object]],
    model: str,
) -> int:
    """Count tokens in a list of messages.

    Args:
        messages: Messages to count.
        model: Model identifier for tokenization.

    Returns:
        Approximate token count.

    """
    import litellm

    result = litellm.token_counter(model=model, messages=messages)
    return int(result)


def _get_context_window(
    model: str,
    max_input_tokens: int | None = None,
) -> int:
    """Get the context window size for a model.

    Priority:
    1. Explicit max_input_tokens from DSL
    2. LiteLLM model info lookup
    3. Default fallback

    Args:
        model: Model identifier.
        max_input_tokens: Optional explicit value from DSL.

    Returns:
        Context window size in tokens.

    """
    if max_input_tokens is not None:
        return max_input_tokens

    try:
        import litellm

        model_info = litellm.get_model_info(model)
        max_tokens = model_info.get("max_input_tokens") if model_info else None
        if max_tokens is not None:
            return int(max_tokens)
    except (ImportError, ValueError, RuntimeError, KeyError):
        raise
    except Exception:  # noqa: BLE001
        # LiteLLM raises generic Exception for unknown models
        logger.warning("Could not get model info for %s", model)

    return DEFAULT_CONTEXT_WINDOW


def extract_messages_from_events(events: list["Event"]) -> list[dict[str, object]]:
    """Extract conversation messages from ADK events.

    Convert ADK events into a message list format suitable for
    token counting and compaction.

    Args:
        events: List of ADK events.

    Returns:
        List of message dicts with 'role' and 'content' keys.

    """
    messages: list[dict[str, object]] = []
    for event in events:
        if not hasattr(event, "content") or not event.content:
            continue

        # Determine role from event author
        role: object = "assistant"
        if hasattr(event, "author") and event.author == "user":
            role = "user"

        # Extract content text
        content: object = ""
        parts = getattr(event.content, "parts", None)
        if parts:
            texts = [part.text for part in parts if hasattr(part, "text") and part.text]
            content = " ".join(texts)

        if content:
            messages.append({"role": role, "content": content})

    return messages
