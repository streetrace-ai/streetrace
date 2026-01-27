# Flow Event Yielding API Reference

Complete API reference for the Flow Event Yielding feature. This document covers all public
classes, methods, and their type signatures.

## Event Classes

### FlowEvent

**Location**: `src/streetrace/dsl/runtime/events.py:10`

Base class for all non-ADK flow events.

```python
@dataclass
class FlowEvent:
    type: str
```

**Attributes**:

| Attribute | Type | Description |
|-----------|------|-------------|
| `type` | `str` | Discriminator field for event type identification |

### LlmCallEvent

**Location**: `src/streetrace/dsl/runtime/events.py:22`

Event emitted when a direct LLM call is initiated via `call llm` statement.

```python
@dataclass
class LlmCallEvent(FlowEvent):
    prompt_name: str
    model: str
    prompt_text: str
    type: str = field(default="llm_call", init=False)
```

**Attributes**:

| Attribute | Type | Description |
|-----------|------|-------------|
| `prompt_name` | `str` | Name of the prompt being called |
| `model` | `str` | Model identifier for the LLM call |
| `prompt_text` | `str` | Resolved prompt text sent to the LLM |
| `type` | `str` | Always `"llm_call"` (set automatically) |

**Example**:

```python
event = LlmCallEvent(
    prompt_name="analyze",
    model="anthropic/claude-sonnet",
    prompt_text="Analyze the following code..."
)
assert event.type == "llm_call"
```

### LlmResponseEvent

**Location**: `src/streetrace/dsl/runtime/events.py:41`

Event emitted when a direct LLM call completes.

```python
@dataclass
class LlmResponseEvent(FlowEvent):
    prompt_name: str
    content: str
    is_final: bool = True
    type: str = field(default="llm_response", init=False)
```

**Attributes**:

| Attribute | Type | Description |
|-----------|------|-------------|
| `prompt_name` | `str` | Name of the prompt that was called |
| `content` | `str` | Response content from the LLM |
| `is_final` | `bool` | Whether this is the final response (default: `True`) |
| `type` | `str` | Always `"llm_response"` (set automatically) |

**Example**:

```python
event = LlmResponseEvent(
    prompt_name="analyze",
    content="The code appears to be a sorting algorithm..."
)
assert event.type == "llm_response"
assert event.is_final is True
```

## WorkflowContext Methods

**Location**: `src/streetrace/dsl/runtime/context.py:133`

### run_agent

Run a named agent with arguments, yielding ADK events.

```python
async def run_agent(
    self,
    agent_name: str,
    *args: object,
) -> AsyncGenerator[Event, None]
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `agent_name` | `str` | Name of the agent to run |
| `*args` | `object` | Arguments joined as prompt text |

**Yields**: ADK `Event` objects from agent execution.

**Side Effects**: Stores final response in `_last_call_result`.

**Example**:

```python
async for event in ctx.run_agent("analyzer", user_input):
    yield event
result = ctx.get_last_result()
```

### run_flow

Run a named flow with arguments, yielding events.

```python
async def run_flow(
    self,
    flow_name: str,
    *args: object,
) -> AsyncGenerator[Event | FlowEvent, None]
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `flow_name` | `str` | Name of the flow to run |
| `*args` | `object` | Arguments passed to flow (reserved for future use) |

**Yields**: `Event` or `FlowEvent` objects from flow execution.

**Example**:

```python
async for event in ctx.run_flow("analyze_documents"):
    yield event
```

### call_llm

Call an LLM with a named prompt, yielding events.

```python
async def call_llm(
    self,
    prompt_name: str,
    *args: object,
    model: str | None = None,
) -> AsyncGenerator[FlowEvent, None]
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt_name` | `str` | Name of the prompt to use |
| `*args` | `object` | Arguments for prompt interpolation (stored in context) |
| `model` | `str \| None` | Optional model override |

**Yields**:

1. `LlmCallEvent` when call initiates
2. `LlmResponseEvent` when call completes

**Side Effects**: Stores response content in `_last_call_result`.

**Example**:

```python
async for event in ctx.call_llm("summarize", document_text):
    yield event
summary = ctx.get_last_result()
```

### get_last_result

Get the result from the last `run_agent` or `call_llm` operation.

```python
def get_last_result(self) -> object
```

**Returns**: The result from the most recent operation, or `None` if no operation has been
executed or the last operation failed.

**Example**:

```python
async for event in ctx.run_agent("analyzer", input_text):
    yield event
analysis = ctx.get_last_result()

async for event in ctx.call_llm("summarize", analysis):
    yield event
summary = ctx.get_last_result()
```

## DslAgentWorkflow Methods

**Location**: `src/streetrace/dsl/runtime/workflow.py:45`

### run_async

Execute the workload based on DSL definition.

```python
async def run_async(
    self,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event | FlowEvent, None]
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `session` | `Session` | ADK session for conversation persistence |
| `message` | `Content \| None` | User message to process |

**Yields**: Events from execution (ADK events or FlowEvents).

**Entry Point Selection**:

1. If DSL defines a `main` flow -> execute flow
2. Else if DSL defines a `default` flow -> execute flow
3. Else if DSL defines a `main` agent -> execute agent
4. Else if DSL defines a `default` agent -> execute agent
5. Else if only one agent defined -> execute that agent
6. Else raise `ValueError`

### run_agent

Run an agent from within a flow, yielding events.

```python
async def run_agent(
    self,
    agent_name: str,
    *args: object,
) -> AsyncGenerator[Event, None]
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `agent_name` | `str` | Name of the agent to run |
| `*args` | `object` | Arguments passed to agent as prompt |

**Yields**: ADK events from agent execution.

**Side Effects**: Stores final response in `WorkflowContext._last_call_result`.

### run_flow

Run a flow from within another flow, yielding events.

```python
async def run_flow(
    self,
    flow_name: str,
    *args: object,
) -> AsyncGenerator[Event | FlowEvent, None]
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `flow_name` | `str` | Name of the flow to run |
| `*args` | `object` | Arguments (reserved for future use) |

**Yields**: Events from flow execution.

**Raises**: `ValueError` if flow not found.

## Supervisor Methods

**Location**: `src/streetrace/workflow/supervisor.py:56`

### handle

Run the payload through the workload.

```python
async def handle(self, ctx: InputContext) -> HandlerResult
```

**Event Handling Logic**:

```python
async for event in workload.run_async(session, content):
    if isinstance(event, FlowEvent):
        self.ui_bus.dispatch_ui_update(event)
        # Capture LlmResponseEvent content if is_final
    else:
        self.ui_bus.dispatch_ui_update(Event(event=event))
        # Capture ADK final response
```

### _capture_flow_event_response

Capture final response from FlowEvent if applicable.

```python
def _capture_flow_event_response(
    self,
    event: FlowEvent,
    current_response: str | None,
) -> str | None
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `event` | `FlowEvent` | The FlowEvent to check |
| `current_response` | `str \| None` | Current captured response |

**Returns**: Updated response text if this event provides a final response.

### _capture_adk_event_response

Capture final response from ADK Event if applicable.

```python
def _capture_adk_event_response(
    self,
    event: AdkEvent,
    current_response: str | None,
) -> str | None
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `event` | `AdkEvent` | The ADK Event to check |
| `current_response` | `str \| None` | Current captured response |

**Returns**: Updated response text if this event provides a final response.

## Renderer Functions

**Location**: `src/streetrace/ui/flow_event_renderer.py`

### render_llm_call

Render LLM call initiation event.

```python
@register_renderer
def render_llm_call(obj: LlmCallEvent, console: Console) -> None
```

**Output Format**: `[LLM Call] {prompt_name} (model: {model})`

### render_llm_response

Render LLM response event as markdown.

```python
@register_renderer
def render_llm_response(obj: LlmResponseEvent, console: Console) -> None
```

**Output**: Renders `obj.content` as Rich Markdown.

## Type Aliases

### Event Union Type

Used throughout the system for return type annotations:

```python
Event | FlowEvent
```

Where:

- `Event` is from `google.adk.events`
- `FlowEvent` is from `streetrace.dsl.runtime.events`

## Code Generation

### Flow Method Signature

Generated flow methods have this signature:

```python
async def flow_{name}(
    self, ctx: WorkflowContext
) -> AsyncGenerator[Event | FlowEvent, None]:
```

### Run Agent Pattern

DSL `run agent` statements generate:

```python
async for _event in ctx.run_agent('{agent_name}', {args}):
    yield _event
ctx.vars['{target}'] = ctx.get_last_result()
```

### Call LLM Pattern

DSL `call llm` statements generate:

```python
async for _event in ctx.call_llm('{prompt_name}', {args}):
    yield _event
ctx.vars['{target}'] = ctx.get_last_result()
```

### Return Statement Pattern

DSL `return` statements generate:

```python
ctx.vars['_return_value'] = {expression}
return
```

## See Also

- [Overview](overview.md) - Architecture and design
- [Extending](extending.md) - Adding new event types
- [DSL Syntax Reference](../../../user/dsl/syntax-reference.md) - DSL language reference
