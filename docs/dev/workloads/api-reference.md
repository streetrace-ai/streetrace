# Workload API Reference

Complete API documentation for the Workload Protocol and related components.

## Workload Protocol

The core protocol that all executable units must implement.

**Location**: `src/streetrace/workloads/protocol.py:17`

### Definition

```python
@runtime_checkable
class Workload(Protocol):
    """Protocol for all executable workloads."""

    def run_async(
        self,
        session: Session,
        message: Content | None,
    ) -> AsyncGenerator[Event, None]:
        """Execute the workload and yield events."""
        ...

    async def close(self) -> None:
        """Clean up all resources allocated by this workload."""
        ...
```

### Methods

#### `run_async`

Execute the workload and yield ADK events.

**Signature**:
```python
def run_async(
    self,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event, None]
```

**Parameters**:
- `session` (`google.adk.sessions.Session`): ADK session for conversation persistence
- `message` (`google.genai.types.Content | None`): User message to process, or None for initial runs

**Yields**:
- `google.adk.events.Event`: ADK events from execution

**Example**:
```python
async for event in workload.run_async(session, content):
    if event.is_final_response():
        print(event.content.parts[0].text)
```

#### `close`

Clean up all resources allocated by this workload.

**Signature**:
```python
async def close(self) -> None
```

Called automatically when using `WorkloadManager.create_workload()` as a context manager.

---

## WorkloadManager

Discovers, loads, and creates runnable workloads.

**Location**: `src/streetrace/workloads/manager.py:148`

### Constructor

```python
def __init__(
    self,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
    work_dir: Path,
    session_service: BaseSessionService | None = None,
    http_auth: str | None = None,
) -> None
```

**Parameters**:
- `model_factory` (`ModelFactory`): Factory for creating and managing LLM models
- `tool_provider` (`ToolProvider`): Provider of tools for the agents
- `system_context` (`SystemContext`): System context containing project-level instructions
- `work_dir` (`Path`): Current working directory for relative path resolution
- `session_service` (`BaseSessionService | None`): ADK session service for workload execution
- `http_auth` (`str | None`): Authorization header value for HTTP agent URIs

### Methods

#### `discover`

Discover all known workloads with location-first priority.

**Signature**:
```python
def discover(self) -> list[AgentInfo]
```

**Returns**:
- `list[AgentInfo]`: List of discovered workload information, deduplicated by name with location priority

**Search Locations** (in priority order):
1. `STREETRACE_AGENT_PATHS` environment variable (highest priority)
2. Current working directory (`./agents`, `.`, `.streetrace/agents`)
3. User home directory (`~/.streetrace/agents`)
4. Bundled agents

**Example**:
```python
manager = WorkloadManager(model_factory, tool_provider, system_context, work_dir)
for agent_info in manager.discover():
    print(f"{agent_info.name} ({agent_info.kind})")
```

#### `create_workload`

Create a runnable workload from an identifier.

**Signature**:
```python
@asynccontextmanager
async def create_workload(
    self,
    identifier: str,
) -> AsyncGenerator[Workload, None]
```

**Parameters**:
- `identifier` (`str`): Workload identifier (name, path, or URL)

**Yields**:
- `Workload`: The created workload instance

**Raises**:
- `ValueError`: If workload creation fails or session_service is not set

**Example**:
```python
async with manager.create_workload("my_agent") as workload:
    async for event in workload.run_async(session, message):
        # Process events
        pass
```

#### `create_agent` (deprecated)

Create agent from identifier with location-first priority.

**Signature**:
```python
@asynccontextmanager
async def create_agent(
    self,
    agent_identifier: str,
) -> AsyncGenerator[BaseAgent, None]
```

Maintains backward compatibility with the original AgentManager interface. Prefer
`create_workload()` for new code.

### Class Variables

#### `SEARCH_LOCATION_SPECS`

Search location specifications in priority order.

```python
SEARCH_LOCATION_SPECS: ClassVar[list[tuple[str, list[str]]]] = [
    ("cwd", ["./agents", ".", ".streetrace/agents"]),
    ("home", ["~/.streetrace/agents"]),
    ("bundled", []),  # Computed from __file__
]
```

---

## BasicAgentWorkload

Workload wrapper for Python and YAML agents.

**Location**: `src/streetrace/workloads/basic_workload.py:29`

### Constructor

```python
def __init__(
    self,
    agent_definition: StreetRaceAgent,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
    session_service: BaseSessionService,
) -> None
```

**Parameters**:
- `agent_definition` (`StreetRaceAgent`): The StreetRaceAgent definition to wrap
- `model_factory` (`ModelFactory`): Factory for creating and managing LLM models
- `tool_provider` (`ToolProvider`): Provider of tools for the agent
- `system_context` (`SystemContext`): System context containing project-level instructions
- `session_service` (`BaseSessionService`): ADK session service for conversation persistence

### Methods

#### `run_async`

Execute the agent and yield events.

**Signature**:
```python
async def run_async(
    self,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event, None]
```

Creates the agent if not already created, then runs it via ADK Runner. All events from the
Runner are yielded to the caller.

#### `close`

Clean up all resources allocated by this workload.

**Signature**:
```python
async def close(self) -> None
```

Calls the agent definition's close method and sets the agent reference to None.

### Properties

#### `agent`

Get the created agent instance.

**Signature**:
```python
@property
def agent(self) -> BaseAgent | None
```

**Returns**:
- `BaseAgent | None`: The BaseAgent instance if created, None otherwise

---

## DslAgentWorkflow

Base class for generated DSL workflows. Implements the Workload protocol.

**Location**: `src/streetrace/dsl/runtime/workflow.py:44`

### Constructor

```python
def __init__(
    self,
    agent_definition: DslStreetRaceAgent | None = None,
    model_factory: ModelFactory | None = None,
    tool_provider: ToolProvider | None = None,
    system_context: SystemContext | None = None,
    session_service: BaseSessionService | None = None,
) -> None
```

**Parameters**:
- `agent_definition` (`DslStreetRaceAgent | None`): DslStreetRaceAgent for composition (agent creation)
- `model_factory` (`ModelFactory | None`): Factory for creating LLM models
- `tool_provider` (`ToolProvider | None`): Provider for tools
- `system_context` (`SystemContext | None`): System context
- `session_service` (`BaseSessionService | None`): Session service for Runner

### Class Variables

```python
_models: ClassVar[dict[str, str]] = {}
"""Model definitions for this workflow."""

_prompts: ClassVar[dict[str, object]] = {}
"""Prompt definitions for this workflow."""

_tools: ClassVar[dict[str, dict[str, object]]] = {}
"""Tool definitions for this workflow."""

_agents: ClassVar[dict[str, dict[str, object]]] = {}
"""Agent definitions for this workflow."""
```

These are populated by the DSL code generator for each compiled workflow.

### Methods

#### `run_async`

Execute the workload based on DSL definition.

**Signature**:
```python
async def run_async(
    self,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event, None]
```

Entry point selection:
1. If DSL defines a `main` flow, run that flow
2. Else if DSL defines a `default` agent, run that agent
3. Else run the first defined agent

#### `run_agent`

Run an agent from within a flow.

**Signature**:
```python
async def run_agent(self, agent_name: str, *args: object) -> object
```

**Parameters**:
- `agent_name` (`str`): Name of the agent to run
- `*args` (`object`): Arguments to pass to the agent (joined as prompt text)

**Returns**:
- Final response from the agent execution

Called by generated flow code via `ctx.run_agent()`. Uses `_create_agent()` which delegates
to DslStreetRaceAgent for full tool resolution.

#### `run_flow`

Run a flow from within another flow.

**Signature**:
```python
async def run_flow(self, flow_name: str, *args: object) -> object
```

**Parameters**:
- `flow_name` (`str`): Name of the flow to run
- `*args` (`object`): Arguments to pass to the flow

**Returns**:
- Result from the flow execution

#### `close`

Clean up all created agents.

**Signature**:
```python
async def close(self) -> None
```

Closes all agents that were created during execution by delegating to
`self._agent_def.close(agent)` for each created agent.

#### `create_context`

Create a new workflow context.

**Signature**:
```python
def create_context(self) -> WorkflowContext
```

**Returns**:
- `WorkflowContext`: A fresh WorkflowContext connected to this workflow

### Event Handlers

Override these methods in generated workflows to handle lifecycle events:

| Method | Description |
|--------|-------------|
| `on_start(ctx)` | Handle workflow start event |
| `on_input(ctx)` | Handle input event |
| `on_output(ctx)` | Handle output event |
| `on_tool_call(ctx)` | Handle tool call event |
| `on_tool_result(ctx)` | Handle tool result event |
| `after_start(ctx)` | Handle after start event |
| `after_input(ctx)` | Handle after input event |
| `after_output(ctx)` | Handle after output event |
| `after_tool_call(ctx)` | Handle after tool call event |
| `after_tool_result(ctx)` | Handle after tool result event |

---

## EntryPoint

Dataclass representing an entry point for workflow execution.

**Location**: `src/streetrace/dsl/runtime/workflow.py:33`

```python
@dataclass
class EntryPoint:
    type: str
    """Entry point type: 'flow' or 'agent'."""

    name: str
    """Name of the flow or agent."""
```

---

## Type Aliases

### Workload Type Checking

```python
from streetrace.workloads import Workload

# Runtime type checking
if isinstance(obj, Workload):
    async for event in obj.run_async(session, message):
        ...
```

### Type Imports

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `STREETRACE_AGENT_PATHS` | Colon-separated list of additional search paths (highest priority) |
| `STREETRACE_AGENT_URI_AUTH` | Default authorization for HTTP agent URIs |

---

## See Also

- [Architecture](architecture.md) - Design overview and component relationships
- [Extension Guide](extension-guide.md) - Creating custom Workload implementations
- [DSL Runtime](../dsl/architecture.md) - DSL compiler and runtime details
