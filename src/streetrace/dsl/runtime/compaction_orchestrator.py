"""Compaction orchestration for DSL runtime history management.

Provide compaction strategy resolution, model lookup, and history
compaction execution for DSL agent workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from streetrace.dsl.runtime.events import HistoryCompactionEvent
from streetrace.dsl.runtime.history_compactor import (
    HistoryCompactor,
    extract_messages_from_events,
)
from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from google.adk.events import Event

    from streetrace.dsl.runtime.compacting_runner import CompactionStrategy
    from streetrace.llm.model_factory import ModelFactory

logger = get_logger(__name__)


class CompactionOrchestrator:
    """Orchestrate history compaction for DSL agent workflows.

    Encapsulate the logic for resolving compaction strategies from
    DSL model/agent definitions, and driving HistoryCompactor when
    history exceeds token limits.
    """

    def __init__(
        self,
        *,
        models: dict[str, str],
        agents: dict[str, dict[str, object]],
        compaction_policy: dict[str, object] | None,
        model_factory: ModelFactory | None,
    ) -> None:
        """Initialize with DSL definitions.

        Args:
            models: Model name to identifier mapping.
            agents: Agent definitions dict.
            compaction_policy: Default compaction policy, or None.
            model_factory: Factory for creating LLM interfaces.

        """
        self._models = models
        self._agents = agents
        self._compaction_policy = compaction_policy
        self._model_factory = model_factory

    def get_history_strategy(self, agent_name: str) -> str | None:
        """Get the history management strategy for an agent.

        Priority:
        1. Agent's explicit history property
        2. Compaction policy's strategy (workflow default)

        Args:
            agent_name: Name of the agent.

        Returns:
            Strategy name ('summarize' or 'truncate') or None.

        """
        agent_def = self._agents.get(agent_name)

        # First check agent's explicit history property
        if agent_def:
            history = agent_def.get("history")
            if history:
                return str(history)

        # Fall back to compaction policy if defined
        if self._compaction_policy:
            strategy = self._compaction_policy.get("strategy")
            if strategy:
                return str(strategy)

        return None

    def get_agent_model(self, agent_name: str) -> str:
        """Resolve the model name for an agent.

        Look up the agent's model from its definition or use default.

        Args:
            agent_name: Name of the agent.

        Returns:
            Model identifier string.

        """
        # Check if agent has a specific model configured
        agent_def = self._agents.get(agent_name)
        if agent_def:
            model_name = agent_def.get("model")
            if model_name and isinstance(model_name, str):
                if model_name in self._models:
                    return self._models[model_name]
                return model_name

        # Use first model defined or default
        if self._models:
            return next(iter(self._models.values()))

        return "gpt-4"  # Default fallback

    def get_model_max_input_tokens(self, agent_name: str) -> int | None:
        """Get max_input_tokens setting for an agent's model.

        Args:
            agent_name: Name of the agent.

        Returns:
            Max input tokens or None to use LiteLLM lookup.

        """
        agent_def = self._agents.get(agent_name)
        if not agent_def:
            return None

        model_name = agent_def.get("model")
        if not model_name or not isinstance(model_name, str):
            model_name = (
                next(iter(self._models.keys()), None) if self._models else None
            )

        if not model_name:
            return None

        # Will be enhanced when model properties are fully exposed
        return None

    def create_strategy(self, agent_name: str) -> CompactionStrategy | None:
        """Create a compaction strategy for the agent if configured.

        Args:
            agent_name: Name of the agent.

        Returns:
            CompactionStrategy instance, or None if not configured.

        """
        from streetrace.dsl.runtime.compacting_runner import (
            SummarizeCompactionStrategy,
            TruncateCompactionStrategy,
        )

        strategy_name = self.get_history_strategy(agent_name)
        if not strategy_name:
            return None

        if strategy_name == "summarize" and self._model_factory:
            from streetrace.dsl.runtime.workflow import SummarizeLlmAdapter

            model = self.get_agent_model(agent_name)
            llm_adapter = SummarizeLlmAdapter(self._model_factory, model)
            return SummarizeCompactionStrategy(llm=llm_adapter)

        # Default to truncate strategy
        return TruncateCompactionStrategy(keep_recent=6)

    async def check_and_compact_history(
        self,
        agent_name: str,
        events: list[Event],
        strategy: str,
    ) -> AsyncGenerator[HistoryCompactionEvent, None]:
        """Check if history needs compaction and perform it if needed.

        Args:
            agent_name: Name of the agent for model lookup.
            events: Collected events from agent execution.
            strategy: Compaction strategy name.

        Yields:
            HistoryCompactionEvent if compaction was performed.

        """
        model = self.get_agent_model(agent_name)
        max_input_tokens = self.get_model_max_input_tokens(agent_name)

        # Extract messages from events
        messages = extract_messages_from_events(events)

        if not messages:
            return

        # Create compactor with strategy
        llm_adapter = None
        if strategy == "summarize" and self._model_factory:
            from streetrace.dsl.runtime.workflow import SummarizeLlmAdapter

            model_id = self.get_agent_model(agent_name)
            llm_adapter = SummarizeLlmAdapter(self._model_factory, model_id)

        compactor = HistoryCompactor(
            strategy=strategy,
            llm=llm_adapter,
        )

        # Check if compaction is needed
        if not compactor.should_compact(messages, model, max_input_tokens):
            return

        # Perform compaction
        result = await compactor.compact(messages, model, max_input_tokens)

        logger.info(
            "Compacted history for agent '%s': %d -> %d tokens, "
            "%d messages removed",
            agent_name,
            result.original_tokens,
            result.compacted_tokens,
            result.messages_removed,
        )

        # Yield compaction event for visibility
        yield HistoryCompactionEvent(
            strategy=strategy,
            original_tokens=result.original_tokens,
            compacted_tokens=result.compacted_tokens,
            messages_removed=result.messages_removed,
        )
