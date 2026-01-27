# Implementation Plan: Flow Event Yielding

## Overview

This document outlines the phased implementation plan for adding event yielding to DSL flows.
Each phase is designed to be independently testable and deployable.

## Phase 1: FlowEvent Infrastructure

**Goal**: Establish the event class hierarchy and rendering infrastructure.

### 1.1 Create FlowEvent Classes

**File**: `src/streetrace/dsl/runtime/events.py` (new)

```python
"""Flow events for non-ADK operations in DSL workflows."""

from dataclasses import dataclass, field


@dataclass
class FlowEvent:
    """Base class for all non-ADK flow events.

    Provides a common type for isinstance checks and a type discriminator
    for serialization.
    """

    type: str
    """Discriminator field for event type identification."""


@dataclass
class LlmCallEvent(FlowEvent):
    """Event emitted when a direct LLM call is initiated.

    Corresponds to the DSL `call llm` statement.
    """

    prompt_name: str
    """Name of the prompt being called."""

    model: str
    """Model identifier for the LLM call."""

    prompt_text: str
    """Resolved prompt text sent to the LLM."""

    type: str = field(default="llm_call", init=False)


@dataclass
class LlmResponseEvent(FlowEvent):
    """Event emitted when a direct LLM call completes.

    Contains the response from the LLM.
    """

    prompt_name: str
    """Name of the prompt that was called."""

    content: str
    """Response content from the LLM."""

    is_final: bool = True
    """Whether this is the final response (always True for LLM calls)."""

    type: str = field(default="llm_response", init=False)
```

### 1.2 Create FlowEvent Renderers

**File**: `src/streetrace/ui/flow_event_renderer.py` (new)

```python
"""Renderers for FlowEvent types."""

from typing import TYPE_CHECKING

from streetrace.dsl.runtime.events import LlmCallEvent, LlmResponseEvent
from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer

if TYPE_CHECKING:
    from rich.console import Console


@register_renderer
def render_llm_call(obj: LlmCallEvent, console: "Console") -> None:
    """Render LLM call initiation."""
    console.print(
        f"[LLM Call] {obj.prompt_name} (model: {obj.model})",
        style=Styles.RICH_INFO,
    )


@register_renderer
def render_llm_response(obj: LlmResponseEvent, console: "Console") -> None:
    """Render LLM response."""
    from rich.markdown import Markdown

    console.print(
        Markdown(obj.content, inline_code_theme=Styles.RICH_MD_CODE),
        style=Styles.RICH_MODEL,
    )
```

### 1.3 Register Renderers

**File**: `src/streetrace/ui/__init__.py`

Add import to ensure renderers are registered:
```python
from streetrace.ui import flow_event_renderer  # noqa: F401
```

### 1.4 Update Workload Protocol Type Hint

**File**: `src/streetrace/workloads/protocol.py`

Update return type annotation to include FlowEvent:
```python
from streetrace.dsl.runtime.events import FlowEvent

def run_async(
    self,
    session: "Session",
    message: "Content | None",
) -> AsyncGenerator["Event | FlowEvent", None]:
```

### 1.5 Tests for Phase 1

- Unit tests for FlowEvent dataclass creation and type field
- Unit tests for renderers (mock console)
- Verify renderers are registered in protocol registry

**Acceptance Criteria**:
- [ ] `FlowEvent`, `LlmCallEvent`, `LlmResponseEvent` classes exist
- [ ] Renderers registered and functional
- [ ] `make check` passes

---

## Phase 2: Supervisor FlowEvent Handling

**Goal**: Enable supervisor to handle both ADK Events and FlowEvents.

### 2.1 Update Supervisor Event Loop

**File**: `src/streetrace/workflow/supervisor.py`

```python
from streetrace.dsl.runtime.events import FlowEvent, LlmResponseEvent
from streetrace.ui.adk_event_renderer import Event

async for event in workload.run_async(session, content):
    if isinstance(event, FlowEvent):
        # Custom flow event - dispatch directly
        self.ui_bus.dispatch_ui_update(event)
        # Capture final response from LLM calls
        if isinstance(event, LlmResponseEvent) and event.is_final:
            if final_response_text == "Agent did not produce a final response.":
                final_response_text = event.content
    else:
        # ADK Event - wrap and dispatch
        self.ui_bus.dispatch_ui_update(Event(event=event))
        # Existing final response handling...
```

### 2.2 Tests for Phase 2

- Unit test: Supervisor correctly dispatches FlowEvent to UI bus
- Unit test: Supervisor extracts final response from LlmResponseEvent
- Unit test: ADK Event handling unchanged

**Acceptance Criteria**:
- [ ] Supervisor handles FlowEvent without errors
- [ ] Final response captured from LlmResponseEvent
- [ ] Existing ADK event tests pass

---

## Phase 3: call_llm Event Yielding

**Goal**: Make `WorkflowContext.call_llm()` yield events.

### 3.1 Convert call_llm to Generator

**File**: `src/streetrace/dsl/runtime/context.py`

```python
from collections.abc import AsyncGenerator
from streetrace.dsl.runtime.events import FlowEvent, LlmCallEvent, LlmResponseEvent

async def call_llm(
    self,
    prompt_name: str,
    *args: object,
    model: str | None = None,
) -> AsyncGenerator[FlowEvent, None]:
    """Call an LLM with a named prompt, yielding events.

    Yields:
        LlmCallEvent when call initiates
        LlmResponseEvent when call completes

    """
    # ... existing prompt resolution ...

    # Yield call event
    yield LlmCallEvent(
        prompt_name=prompt_name,
        model=resolved_model,
        prompt_text=prompt_text,
    )

    try:
        response = await litellm.acompletion(
            model=resolved_model,
            messages=messages,
        )
        # Extract content...
        content = ...

        # Yield response event
        yield LlmResponseEvent(
            prompt_name=prompt_name,
            content=content,
        )

        # Store result for flow retrieval
        self._last_call_result = content

    except Exception:
        logger.exception("LLM call failed for prompt '%s'", prompt_name)
        self._last_call_result = None
```

### 3.2 Add Result Retrieval Method

**File**: `src/streetrace/dsl/runtime/context.py`

```python
def get_last_result(self) -> object:
    """Get the result from the last run_agent or call_llm operation.

    Returns:
        The result from the most recent operation.

    """
    return getattr(self, "_last_call_result", None)
```

### 3.3 Tests for Phase 3

- Unit test: `call_llm` yields LlmCallEvent then LlmResponseEvent
- Unit test: `get_last_result()` returns correct value
- Unit test: Error handling preserves None result

**Acceptance Criteria**:
- [ ] `call_llm` is an async generator
- [ ] Events yielded in correct order
- [ ] Result retrievable via `get_last_result()`

---

## Phase 4: run_agent Event Yielding

**Goal**: Make `DslAgentWorkflow.run_agent()` yield ADK events.

### 4.1 Convert run_agent to Generator

**File**: `src/streetrace/dsl/runtime/workflow.py`

```python
async def run_agent(
    self,
    agent_name: str,
    *args: object,
) -> AsyncGenerator["Event", None]:
    """Run an agent from within a flow, yielding events.

    Yields:
        ADK events from agent execution.

    """
    agent = await self._create_agent(agent_name)

    # ... existing setup ...

    final_response: object = None
    async for event in runner.run_async(...):
        yield event  # Forward event to caller
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response = event.content.parts[0].text

    # Store result for context retrieval
    if self._context:
        self._context._last_call_result = final_response
```

### 4.2 Update WorkflowContext.run_agent

**File**: `src/streetrace/dsl/runtime/context.py`

```python
async def run_agent(
    self,
    agent_name: str,
    *args: object,
) -> AsyncGenerator["Event", None]:
    """Run a named agent with arguments, yielding events.

    Yields:
        ADK events from agent execution.

    """
    async for event in self._workflow.run_agent(agent_name, *args):
        yield event
```

### 4.3 Tests for Phase 4

- Unit test: `run_agent` yields ADK events
- Unit test: Final response captured correctly
- Unit test: Multiple agents yield interleaved events

**Acceptance Criteria**:
- [ ] `run_agent` is an async generator
- [ ] All ADK events yielded
- [ ] Final response stored in context

---

## Phase 5: Flow Execution Event Propagation

**Goal**: Make `_execute_flow()` yield all events from contained operations.

### 5.1 Update _execute_flow

**File**: `src/streetrace/dsl/runtime/workflow.py`

```python
async def _execute_flow(
    self,
    flow_name: str,
    session: "Session",
    message: "Content | None",
) -> AsyncGenerator["Event | FlowEvent", None]:
    """Execute a flow, yielding events.

    Yields:
        Events from all operations within the flow.

    """
    flow_method = getattr(self, f"flow_{flow_name}", None)
    if flow_method is None:
        msg = f"Flow '{flow_name}' not found"
        raise ValueError(msg)

    input_text = self._extract_message_text(message)
    ctx = self.create_context(input_prompt=input_text)

    # Flow method is now a generator
    async for event in flow_method(ctx):
        yield event
```

### 5.2 Update run_async for Flows

**File**: `src/streetrace/dsl/runtime/workflow.py`

```python
async def run_async(
    self,
    session: "Session",
    message: "Content | None",
) -> AsyncGenerator["Event | FlowEvent", None]:
    """Execute the workload based on DSL definition.

    Yields:
        Events from execution.

    """
    entry_point = self._determine_entry_point()

    if entry_point.type == "flow":
        async for event in self._execute_flow(entry_point.name, session, message):
            yield event
    else:
        async for event in self._execute_agent(entry_point.name, session, message):
            yield event
```

### 5.3 Tests for Phase 5

- Unit test: Flow execution yields events from run_agent calls
- Unit test: Flow execution yields events from call_llm calls
- Unit test: Sequential agents yield interleaved events
- Integration test: Full flow execution with UI rendering

**Acceptance Criteria**:
- [ ] `_execute_flow` is an async generator
- [ ] Events from all operations propagate
- [ ] `run_async` works for both flows and agents

---

## Phase 6: Code Generation Updates

**Goal**: Update code generation to produce async generator flow methods.

### 6.1 Update Flow Method Signature Generation

**File**: `src/streetrace/dsl/codegen/visitors/flows.py`

Change flow method signature from:
```python
async def flow_{name}(self, ctx: WorkflowContext) -> Any:
```

To:
```python
async def flow_{name}(
    self, ctx: WorkflowContext
) -> AsyncGenerator[Event | FlowEvent, None]:
```

### 6.2 Update run_agent Statement Generation

**File**: `src/streetrace/dsl/codegen/visitors/flows.py`

Change from:
```python
ctx.vars['result'] = await ctx.run_agent('analyzer', ctx.vars['input'])
```

To:
```python
async for _event in ctx.run_agent('analyzer', ctx.vars['input']):
    yield _event
ctx.vars['result'] = ctx.get_last_result()
```

### 6.3 Update call_llm Statement Generation

**File**: `src/streetrace/dsl/codegen/visitors/flows.py`

Change from:
```python
ctx.vars['result'] = await ctx.call_llm('prompt_name', ctx.vars['input'])
```

To:
```python
async for _event in ctx.call_llm('prompt_name', ctx.vars['input']):
    yield _event
ctx.vars['result'] = ctx.get_last_result()
```

### 6.4 Tests for Phase 6

- Unit test: Generated code has correct signature
- Unit test: run_agent generates async for pattern
- Unit test: call_llm generates async for pattern
- Integration test: Compiled DSL produces working generator

**Acceptance Criteria**:
- [ ] Generated flow methods are async generators
- [ ] Generated code yields events correctly
- [ ] Result assignment uses `get_last_result()`
- [ ] Existing DSL files compile and work

---

## Phase 7: Integration Testing and Documentation

**Goal**: Comprehensive testing and documentation updates.

### 7.1 Integration Tests

Create test file: `tests/integration/dsl/test_flow_event_yielding.py`

Test cases:
- Single agent flow yields all ADK events
- Multiple agent flow yields interleaved events
- Flow with call_llm yields LlmCallEvent and LlmResponseEvent
- Mixed flow (agents + LLM calls) yields correct event sequence
- Nested flows propagate events correctly
- UI renders all event types correctly

### 7.2 Update Tech Debt Document

**File**: `docs/tasks/017-dsl/tech_debt.md`

Move "Flow Execution Does Not Yield ADK Events" from Open Issues to Resolved Issues.

### 7.3 Update Architecture Documentation

**File**: `docs/dev/dsl/architecture.md`

Update "Flow Event Streaming" section from "Open" to documenting the implementation.

### 7.4 Tests for Phase 7

- All integration tests pass
- Documentation is accurate

**Acceptance Criteria**:
- [ ] Integration tests cover all scenarios
- [ ] Documentation updated
- [ ] `make check` passes
- [ ] No regressions in existing functionality

---

## Implementation Order Summary

| Phase | Description | Dependencies | Est. Complexity |
|-------|-------------|--------------|-----------------|
| 1 | FlowEvent Infrastructure | None | Low |
| 2 | Supervisor FlowEvent Handling | Phase 1 | Low |
| 3 | call_llm Event Yielding | Phase 1 | Medium |
| 4 | run_agent Event Yielding | Phase 1 | Medium |
| 5 | Flow Execution Propagation | Phases 3, 4 | Medium |
| 6 | Code Generation Updates | Phase 5 | High |
| 7 | Integration Testing | All | Medium |

## Rollback Plan

Each phase is designed to be independently revertable:

- **Phase 1-2**: New files can be deleted, supervisor changes reverted
- **Phase 3-4**: Methods can be reverted to non-generator versions
- **Phase 5**: `_execute_flow` can be reverted to await-based
- **Phase 6**: Code generation can be reverted (most impactful)

If issues arise after Phase 6, the safest approach is to maintain both patterns
with a feature flag until the new pattern is stable.

## Testing Strategy

1. **Unit tests**: Each phase adds unit tests for new functionality
2. **Regression tests**: Existing tests must continue to pass
3. **Integration tests**: Phase 7 adds end-to-end tests
4. **Manual testing**: Test with example DSL files from `agents/examples/`

## Definition of Done

- [ ] All phases implemented
- [ ] All tests pass (`make check`)
- [ ] No regressions in existing functionality
- [ ] Documentation updated
- [ ] Tech debt item resolved
- [ ] Code reviewed
