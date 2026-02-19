# RFC: Conversation History Management for DSL Agents

## Problem Statement

DSL agents can exceed the LLM context window limit during long-running sessions, causing errors like:
```
litellm.ContextWindowExceededError: prompt is too long: 215098 tokens > 200000 maximum
```

This RFC proposes a solution for managing conversation history within DSL agents to prevent context window overflow.

## Goals

1. **Context Window Awareness**: Know the total context window size of the model being used
2. **Strategy-Based Management**: Define how history should be managed via configurable strategies
3. **DSL Integration**: Allow agents to specify their history management strategy
4. **Extensibility**: Support built-in strategies now with a path to custom strategies later

## Design Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         DSL Definition                           │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ model main:                                                 │ │
│  │     provider: anthropic                                     │ │
│  │     name: claude-sonnet                                     │ │
│  │     max_input_tokens: 200000  # NEW: explicit context size  │ │
│  │                                                             │ │
│  │ agent reviewer:                                             │ │
│  │     tools ...                                               │ │
│  │     instruction ...                                         │ │
│  │     history: summarize  # NEW: strategy reference           │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Runtime Execution                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ DslAgentWorkflow._execute_agent()                          │ │
│  │     │                                                       │ │
│  │     ├─> Run agent via Runner                               │ │
│  │     │                                                       │ │
│  │     └─> [HOOK] HistoryManager.check_and_apply()            │ │
│  │             │                                               │ │
│  │             ├─ Get current token count                      │ │
│  │             ├─ Compare to threshold (80%)                   │ │
│  │             └─ Apply strategy if needed                     │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Context Window Size Support

### 1.1 LiteLLM Integration

LiteLLM provides `get_model_info()` which returns context window information:

```python
import litellm

info = litellm.get_model_info("anthropic/claude-sonnet-4-20250514")
# Returns: {'max_input_tokens': 200000, 'max_output_tokens': 16384, ...}
```

### 1.2 DSL Grammar Extension

Extend `model_property` in `streetrace.lark`:

```lark
model_property: "provider" ":" NAME _NL               -> model_provider
              | "name" ":" NAME _NL                   -> model_name
              | "temperature" ":" NUMBER _NL          -> model_temperature
              | "max_tokens" ":" INT _NL              -> model_max_tokens
              | "max_input_tokens" ":" INT _NL        -> model_max_input_tokens  # NEW
```

### 1.3 Model Info Resolution

Create `ModelInfo` dataclass to hold resolved model metadata:

```python
@dataclass
class ModelInfo:
    """Resolved model information including context limits."""
    name: str
    provider: str
    max_input_tokens: int  # Context window size
    max_output_tokens: int

    @classmethod
    def from_litellm(cls, model_id: str) -> "ModelInfo":
        """Resolve from LiteLLM's model registry."""
        try:
            info = litellm.get_model_info(model_id)
            return cls(
                name=model_id,
                provider=info.get("litellm_provider", "unknown"),
                max_input_tokens=info.get("max_input_tokens", 4096),
                max_output_tokens=info.get("max_output_tokens", 4096),
            )
        except Exception:
            # Fallback for custom/unknown models
            return cls(
                name=model_id,
                provider="unknown",
                max_input_tokens=4096,
                max_output_tokens=4096,
            )
```

### 1.4 Priority Resolution

When determining context window size:
1. **Explicit DSL value** (highest priority): `max_input_tokens: 200000`
2. **LiteLLM lookup** (fallback): Query `get_model_info()`
3. **Default** (last resort): 4096 tokens

---

## Part 2: History Management Strategies

### 2.1 Strategy Interface

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from google.genai import types as genai_types

class HistoryStrategy(ABC):
    """Base class for conversation history management strategies."""

    @abstractmethod
    async def apply(
        self,
        events: list[Event],
        model_info: ModelInfo,
        llm_interface: LlmInterface,
    ) -> AsyncGenerator[Event, None]:
        """Apply the strategy to compact history.

        Args:
            events: Current conversation history
            model_info: Model metadata including context limits
            llm_interface: For strategies that need LLM calls (summarization)

        Yields:
            Compacted events to replace the original history
        """
        pass

    @abstractmethod
    def should_trigger(
        self,
        events: list[Event],
        model_info: ModelInfo,
    ) -> bool:
        """Check if this strategy should be applied.

        Returns:
            True if history management is needed
        """
        pass
```

### 2.2 Built-in Strategies

#### `summarize` Strategy

At 80% of context window, run a summarization prompt:

```python
class SummarizeStrategy(HistoryStrategy):
    """Summarize conversation history preserving goal and recent context."""

    THRESHOLD = 0.8  # Trigger at 80% capacity
    PRESERVE_RECENT_FILES = 10  # Keep last 10 read/modified files

    async def apply(
        self,
        events: list[Event],
        model_info: ModelInfo,
        llm_interface: LlmInterface,
    ) -> AsyncGenerator[Event, None]:
        # 1. Extract first user message (contains goal)
        first_user_event = self._find_first_user_event(events)

        # 2. Identify last N files from tool calls
        recent_files = self._extract_recent_files(events, limit=10)

        # 3. Build summarization prompt
        summary_prompt = self._build_summary_prompt(
            events=events,
            goal=first_user_event.content if first_user_event else None,
            files_to_preserve=recent_files,
        )

        # 4. Call LLM for summary
        summary = await llm_interface.generate_async(
            messages=[{"role": "user", "content": summary_prompt}],
        )

        # 5. Yield compacted history
        if first_user_event:
            yield first_user_event  # Preserve original goal

        yield Event(
            author="system",
            content=genai_types.Content(
                role="model",
                parts=[Part.from_text(f"[Conversation Summary]\n{summary}")]
            )
        )

        # 6. Yield recent tool results for preserved files
        for event in self._filter_recent_file_events(events, recent_files):
            yield event

    def should_trigger(
        self,
        events: list[Event],
        model_info: ModelInfo,
    ) -> bool:
        current_tokens = self._estimate_tokens(events)
        threshold = int(model_info.max_input_tokens * self.THRESHOLD)
        return current_tokens > threshold
```

#### `truncate` Strategy

At 80% of context window, drop early messages while keeping first and recent:

```python
class TruncateStrategy(HistoryStrategy):
    """Truncate history keeping first message and recent context."""

    THRESHOLD = 0.8  # Trigger at 80% capacity
    TARGET_RATIO = 0.7  # Compact to 70% of context

    async def apply(
        self,
        events: list[Event],
        model_info: ModelInfo,
        llm_interface: LlmInterface,
    ) -> AsyncGenerator[Event, None]:
        target_tokens = int(model_info.max_input_tokens * self.TARGET_RATIO)

        # 1. Always keep first user message
        first_user_event = self._find_first_user_event(events)
        kept_events = [first_user_event] if first_user_event else []
        first_tokens = self._estimate_tokens(kept_events)

        # 2. Add from tail until we hit target
        remaining_budget = target_tokens - first_tokens
        tail_events = []

        for event in reversed(events[1:]):  # Skip first, iterate backwards
            event_tokens = self._estimate_tokens([event])
            if remaining_budget - event_tokens > 0:
                tail_events.insert(0, event)
                remaining_budget -= event_tokens
            else:
                break

        # 3. Add truncation marker
        yield from kept_events

        dropped_count = len(events) - len(kept_events) - len(tail_events)
        if dropped_count > 0:
            yield Event(
                author="system",
                content=genai_types.Content(
                    role="model",
                    parts=[Part.from_text(
                        f"[{dropped_count} earlier messages truncated to fit context window]"
                    )]
                )
            )

        yield from tail_events

    def should_trigger(
        self,
        events: list[Event],
        model_info: ModelInfo,
    ) -> bool:
        current_tokens = self._estimate_tokens(events)
        threshold = int(model_info.max_input_tokens * self.THRESHOLD)
        return current_tokens > threshold
```

### 2.3 Strategy Registry

```python
BUILTIN_STRATEGIES: dict[str, type[HistoryStrategy]] = {
    "summarize": SummarizeStrategy,
    "truncate": TruncateStrategy,
}
```

---

## Part 3: DSL Integration

### 3.1 Grammar Extension for Agent History

Add `history` property to `agent_property`:

```lark
agent_property: "tools" name_list _NL                 -> agent_tools
              | "instruction" NAME _NL                -> agent_instruction
              | "prompt" NAME _NL                     -> agent_prompt
              | "produces" NAME _NL                   -> agent_produces
              | "retry" NAME _NL                      -> agent_retry
              | "timeout" timeout_value _NL           -> agent_timeout
              | "description" STRING _NL              -> agent_description
              | "delegate" name_list _NL              -> agent_delegate
              | "use" name_list _NL                   -> agent_use
              | "history" NAME _NL                    -> agent_history  # NEW
```

### 3.2 AST Extension

Update `AgentDef` in `nodes.py`:

```python
@dataclass
class AgentDef:
    name: str | None
    tools: list[str]
    instruction: str
    prompt: str | None
    produces: str | None
    delegate: list[str] | None
    use: list[str] | None
    retry: str | None
    timeout_ref: str | None
    timeout_value: int | None
    timeout_unit: str | None
    description: str | None
    history: str | None  # NEW: strategy name
    meta: SourcePosition | None
```

### 3.3 Usage Example

```
streetrace v1

model main:
    provider: anthropic
    name: claude-sonnet
    max_input_tokens: 200000

agent code_reviewer:
    tools mcp.read_file, mcp.list_directory
    instruction code_review_prompt
    history summarize
```

---

## Part 4: Runtime Integration

### 4.1 HistoryManager Class

New module: `src/streetrace/dsl/runtime/history.py`

```python
class HistoryManager:
    """Manages conversation history for DSL agents."""

    def __init__(
        self,
        strategy: HistoryStrategy | None,
        model_info: ModelInfo,
        llm_interface: LlmInterface,
    ):
        self._strategy = strategy
        self._model_info = model_info
        self._llm_interface = llm_interface

    async def check_and_apply(
        self,
        session: Session,
        session_service: BaseSessionService,
    ) -> bool:
        """Check if history management is needed and apply if so.

        Returns:
            True if history was compacted
        """
        if not self._strategy:
            return False

        if not self._strategy.should_trigger(session.events, self._model_info):
            return False

        # Apply strategy
        new_events = []
        async for event in self._strategy.apply(
            session.events,
            self._model_info,
            self._llm_interface,
        ):
            new_events.append(event)

        # Replace session events
        await session_service.replace_events(session, new_events)
        return True
```

### 4.2 Integration Point

In `DslAgentWorkflow._execute_agent()`:

```python
async def _execute_agent(
    self,
    agent_name: str,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event, None]:
    # ... existing agent creation and execution ...

    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=message,
    ):
        yield event

    # NEW: Check and apply history management
    if self._history_managers.get(agent_name):
        compacted = await self._history_managers[agent_name].check_and_apply(
            session,
            self._session_service,
        )
        if compacted:
            yield self._create_system_event(
                f"[History compacted using {agent_def.get('history')} strategy]"
            )
```

---

## Part 5: Implementation Plan

### Phase 1: Model Context Window Support

**Files to modify:**
- `src/streetrace/dsl/grammar/streetrace.lark` - Add `max_input_tokens` model property
- `src/streetrace/dsl/ast/nodes.py` - Update ModelDef properties
- `src/streetrace/dsl/ast/transformer.py` - Add transformer for new property
- `src/streetrace/llm/model_info.py` (NEW) - ModelInfo class with LiteLLM resolution

**Tests:**
- `tests/dsl/test_model_context_window.py`
- `tests/llm/test_model_info.py`

### Phase 2: Strategy Framework

**Files to create:**
- `src/streetrace/dsl/runtime/history.py` - HistoryStrategy ABC, HistoryManager
- `src/streetrace/dsl/runtime/strategies/` (directory)
  - `__init__.py` - Strategy registry
  - `summarize.py` - SummarizeStrategy
  - `truncate.py` - TruncateStrategy

**Tests:**
- `tests/dsl/runtime/test_history_strategies.py`
- `tests/dsl/runtime/test_history_manager.py`

### Phase 3: DSL Agent Integration

**Files to modify:**
- `src/streetrace/dsl/grammar/streetrace.lark` - Add `history` agent property
- `src/streetrace/dsl/ast/nodes.py` - Update AgentDef
- `src/streetrace/dsl/ast/transformer.py` - Add transformer for history
- `src/streetrace/dsl/codegen/visitors/workflow.py` - Emit history config
- `src/streetrace/dsl/runtime/workflow.py` - Create and use HistoryManager

**Tests:**
- `tests/dsl/test_agent_history.py`
- `tests/dsl/runtime/test_workflow_history.py`

### Phase 4: Token Counting Utilities

**Files to modify/create:**
- `src/streetrace/dsl/runtime/tokens.py` (NEW) - Token counting utilities
  - Uses `litellm.token_counter()` for accurate counting
  - Caches results for performance

**Tests:**
- `tests/dsl/runtime/test_token_counting.py`

---

## Design Decisions

1. **Threshold**: Fixed at 80% - not configurable per-agent (simplicity)
2. **Strategy Parameters**: Simple strategy names only, no parameters (e.g., `history: summarize`)
3. **Visibility**: Compaction events are visible to the user as system events
4. **Implementation**: Full integration approach - all phases together

---

## Future Extensions

1. **Custom Strategies**: Allow DSL-defined strategies using flows
2. **Hybrid Strategies**: Combine summarization with truncation
3. **Intelligent Preservation**: Use embeddings to identify important context
4. **Cross-Agent History**: Share history summaries between agents
