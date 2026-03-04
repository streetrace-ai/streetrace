# Extending Flow Event Yielding

This guide explains how to add new event types to the Flow Event Yielding system. Follow this
guide when you need to emit events for operations not currently covered.

## When to Add New Events

Add new FlowEvent subclasses when:

1. A new DSL statement type needs progress visibility
2. An existing operation should emit intermediate events
3. You need to distinguish different phases of an operation

Do not add events for:

- Operations already covered by ADK events
- Internal implementation details not relevant to users
- High-frequency events that would flood the UI

## Step 1: Define the Event Class

Add your event class to `src/streetrace/dsl/runtime/events.py`.

```python
@dataclass
class MyOperationStartEvent(FlowEvent):
    """Event emitted when my operation starts.

    Correspond to the DSL `my operation` statement.
    """

    operation_name: str
    """Name of the operation being executed."""

    parameters: dict[str, object]
    """Parameters passed to the operation."""

    type: str = field(default="my_operation_start", init=False)


@dataclass
class MyOperationCompleteEvent(FlowEvent):
    """Event emitted when my operation completes."""

    operation_name: str
    """Name of the operation that completed."""

    result: object
    """Result of the operation."""

    duration_ms: int
    """Duration in milliseconds."""

    type: str = field(default="my_operation_complete", init=False)
```

**Guidelines**:

- Use `@dataclass` decorator
- Inherit from `FlowEvent`
- Set `type` field with `field(default="...", init=False)`
- Use unique, lowercase type values with underscores
- Document all fields with docstrings

## Step 2: Create Renderers

Add renderers to `src/streetrace/ui/flow_event_renderer.py`.

```python
from streetrace.dsl.runtime.events import (
    LlmCallEvent,
    LlmResponseEvent,
    MyOperationStartEvent,
    MyOperationCompleteEvent,
)


@register_renderer
def render_my_operation_start(obj: MyOperationStartEvent, console: "Console") -> None:
    """Render my operation start event."""
    console.print(
        f"[My Operation] Starting {obj.operation_name}",
        style=Styles.RICH_INFO,
    )


@register_renderer
def render_my_operation_complete(
    obj: MyOperationCompleteEvent,
    console: "Console",
) -> None:
    """Render my operation complete event."""
    console.print(
        f"[My Operation] Completed {obj.operation_name} in {obj.duration_ms}ms",
        style=Styles.RICH_SUCCESS,
    )
```

**Guidelines**:

- Use `@register_renderer` decorator
- First parameter must be the exact event type (for dispatch)
- Use appropriate styles from `streetrace.ui.colors.Styles`
- Keep output concise and informative

## Step 3: Emit Events from Context Methods

Add or modify methods in `src/streetrace/dsl/runtime/context.py`.

```python
async def my_operation(
    self,
    operation_name: str,
    *args: object,
) -> AsyncGenerator[FlowEvent, None]:
    """Execute my operation, yielding events.

    Args:
        operation_name: Name of the operation.
        *args: Operation arguments.

    Yields:
        MyOperationStartEvent when operation starts.
        MyOperationCompleteEvent when operation completes.

    """
    import time

    start_time = time.monotonic()
    parameters = {"args": args}

    # Yield start event
    yield MyOperationStartEvent(
        operation_name=operation_name,
        parameters=parameters,
    )

    try:
        # Execute the actual operation
        result = await self._execute_my_operation(operation_name, *args)

        # Calculate duration
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Yield complete event
        yield MyOperationCompleteEvent(
            operation_name=operation_name,
            result=result,
            duration_ms=duration_ms,
        )

        # Store result for flow retrieval
        self._last_call_result = result

    except Exception:
        logger.exception("My operation failed: %s", operation_name)
        self._last_call_result = None
```

**Guidelines**:

- Return `AsyncGenerator[FlowEvent, None]`
- Yield events at meaningful points
- Store results in `_last_call_result`
- Handle errors gracefully

## Step 4: Update Code Generation

Modify `src/streetrace/dsl/codegen/visitors/flows.py` to generate code for your new statement.

### Add AST Node Import

```python
from streetrace.dsl.ast.nodes import (
    # ... existing imports ...
    MyOperationStmt,
)
```

### Add Statement Dispatch

```python
self._stmt_dispatch: dict[type, Callable[[object], None]] = {
    # ... existing entries ...
    MyOperationStmt: self._visit_my_operation_stmt,
}
```

### Implement Visitor Method

```python
def _visit_my_operation_stmt(self, node: MyOperationStmt) -> None:
    """Generate code for my operation statement.

    Args:
        node: My operation statement node.

    """
    source_line = node.meta.line if node.meta else None
    args_str = ", ".join(self._expr_visitor.visit(arg) for arg in node.args)

    if args_str:
        call = f"ctx.my_operation('{node.name}', {args_str})"
    else:
        call = f"ctx.my_operation('{node.name}')"

    # Generate async for loop to yield events
    self._emitter.emit(f"async for _event in {call}:", source_line=source_line)
    self._emitter.indent()
    self._emitter.emit("yield _event")
    self._emitter.dedent()

    # Assign result from context if target specified
    if node.target:
        target_name = node.target.lstrip("$")
        self._emitter.emit(f"ctx.vars['{target_name}'] = ctx.get_last_result()")
```

## Step 5: Handle Events in Supervisor (Optional)

If your events need special handling (e.g., capturing final responses), update
`src/streetrace/workflow/supervisor.py`.

```python
def _capture_flow_event_response(
    self,
    event: FlowEvent,
    current_response: str | None,
) -> str | None:
    # Existing LlmResponseEvent handling
    if (
        isinstance(event, LlmResponseEvent)
        and event.is_final
        and current_response == DEFAULT_NO_RESPONSE_MSG
    ):
        return event.content

    # Add handling for your event type
    if (
        isinstance(event, MyOperationCompleteEvent)
        and current_response == DEFAULT_NO_RESPONSE_MSG
    ):
        # Example: use result as final response if it's a string
        if isinstance(event.result, str):
            return event.result

    return current_response
```

## Step 6: Add Tests

### Unit Tests for Event Classes

```python
# tests/unit/dsl/runtime/test_my_operation_events.py

def test_my_operation_start_event_creation():
    """Test MyOperationStartEvent creation."""
    event = MyOperationStartEvent(
        operation_name="test_op",
        parameters={"key": "value"},
    )

    assert event.type == "my_operation_start"
    assert event.operation_name == "test_op"
    assert event.parameters == {"key": "value"}


def test_my_operation_complete_event_creation():
    """Test MyOperationCompleteEvent creation."""
    event = MyOperationCompleteEvent(
        operation_name="test_op",
        result="success",
        duration_ms=150,
    )

    assert event.type == "my_operation_complete"
    assert event.operation_name == "test_op"
    assert event.result == "success"
    assert event.duration_ms == 150
```

### Unit Tests for Yielding

```python
# tests/unit/dsl/runtime/test_my_operation_generator.py

async def test_my_operation_yields_events():
    """Test my_operation yields start and complete events."""
    ctx = create_test_context()

    events = []
    async for event in ctx.my_operation("test_op", "arg1"):
        events.append(event)

    assert len(events) == 2
    assert isinstance(events[0], MyOperationStartEvent)
    assert isinstance(events[1], MyOperationCompleteEvent)
    assert events[0].operation_name == "test_op"
    assert events[1].operation_name == "test_op"
```

### Unit Tests for Code Generation

```python
# tests/unit/dsl/codegen/test_my_operation_codegen.py

def test_my_operation_generates_async_for():
    """Test my operation generates async for loop."""
    dsl = """
    flow main:
        $result = my operation test_op $input
    """
    code = compile_dsl_to_python(dsl)

    assert "async for _event in ctx.my_operation('test_op'" in code
    assert "yield _event" in code
    assert "ctx.vars['result'] = ctx.get_last_result()" in code
```

## Complete Example: Adding a Timer Event

Here's a complete example of adding timer events for measuring operation duration.

### events.py

```python
@dataclass
class TimerStartEvent(FlowEvent):
    """Event emitted when a timer starts."""

    timer_name: str
    type: str = field(default="timer_start", init=False)


@dataclass
class TimerStopEvent(FlowEvent):
    """Event emitted when a timer stops."""

    timer_name: str
    elapsed_ms: int
    type: str = field(default="timer_stop", init=False)
```

### flow_event_renderer.py

```python
@register_renderer
def render_timer_start(obj: TimerStartEvent, console: "Console") -> None:
    console.print(f"[Timer] Started: {obj.timer_name}", style=Styles.RICH_INFO)


@register_renderer
def render_timer_stop(obj: TimerStopEvent, console: "Console") -> None:
    console.print(
        f"[Timer] {obj.timer_name}: {obj.elapsed_ms}ms",
        style=Styles.RICH_SUCCESS,
    )
```

### context.py

```python
async def start_timer(self, timer_name: str) -> AsyncGenerator[FlowEvent, None]:
    """Start a named timer."""
    import time

    self._timers[timer_name] = time.monotonic()
    yield TimerStartEvent(timer_name=timer_name)


async def stop_timer(self, timer_name: str) -> AsyncGenerator[FlowEvent, None]:
    """Stop a named timer and emit elapsed time."""
    import time

    start = self._timers.pop(timer_name, time.monotonic())
    elapsed_ms = int((time.monotonic() - start) * 1000)
    yield TimerStopEvent(timer_name=timer_name, elapsed_ms=elapsed_ms)
```

## See Also

- [Overview](overview.md) - Architecture and design
- [API Reference](api-reference.md) - Complete API documentation
- [Code Generation Guide](../extending.md) - General code generation guide
