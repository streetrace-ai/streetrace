# Workload Abstraction API Reference

Complete API documentation for the Workload Abstraction types introduced in the workload loading
refactoring.

## WorkloadMetadata

Immutable metadata about a workload definition.

**Location**: `src/streetrace/workloads/metadata.py:12`

### Definition

```python
@dataclass(frozen=True)
class WorkloadMetadata:
    """Immutable metadata about a workload definition."""

    name: str
    description: str
    source_path: Path
    format: Literal["dsl", "yaml", "python"]
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique identifier for the workload |
| `description` | `str` | Human-readable description of what the workload does |
| `source_path` | `Path` | Path to the source file that defines the workload |
| `format` | `Literal["dsl", "yaml", "python"]` | The format type of the workload source |

### Characteristics

- **Frozen**: Immutable after creation - attempting to modify raises `FrozenInstanceError`
- **Hashable**: Can be used as dictionary keys or in sets
- **Equality**: Two metadata instances are equal if all fields match

### Example

```python
from pathlib import Path
from streetrace.workloads import WorkloadMetadata

metadata = WorkloadMetadata(
    name="my-agent",
    description="A helpful coding assistant",
    source_path=Path("/path/to/agent.sr"),
    format="dsl",
)

# Access attributes
print(metadata.name)  # "my-agent"
print(metadata.format)  # "dsl"

# Immutability - raises FrozenInstanceError
# metadata.name = "other"  # TypeError!
```

---

## WorkloadDefinition

Abstract base class for compiled workload definitions.

**Location**: `src/streetrace/workloads/definition.py:22`

### Definition

```python
class WorkloadDefinition(ABC):
    """Abstract base class for compiled workload definitions."""

    def __init__(self, metadata: WorkloadMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> WorkloadMetadata:
        return self._metadata

    @property
    def name(self) -> str:
        return self._metadata.name

    @abstractmethod
    def create_workload(
        self,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
        session_service: BaseSessionService,
    ) -> Workload:
        ...
```

### Constructor

```python
def __init__(self, metadata: WorkloadMetadata) -> None
```

**Parameters**:
- `metadata` (`WorkloadMetadata`): Immutable metadata describing this workload

### Properties

#### `metadata`

Get the workload metadata.

**Signature**:
```python
@property
def metadata(self) -> WorkloadMetadata
```

**Returns**:
- `WorkloadMetadata`: The immutable metadata for this workload definition

#### `name`

Get the workload name (convenience property).

**Signature**:
```python
@property
def name(self) -> str
```

**Returns**:
- `str`: The name of this workload (delegates to `metadata.name`)

### Abstract Methods

#### `create_workload`

Create a runnable workload instance from this definition.

**Signature**:
```python
@abstractmethod
def create_workload(
    self,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
    session_service: BaseSessionService,
) -> Workload
```

**Parameters**:
- `model_factory` (`ModelFactory`): Factory for creating and managing LLM models
- `tool_provider` (`ToolProvider`): Provider of tools for the workload
- `system_context` (`SystemContext`): System context containing project-level settings
- `session_service` (`BaseSessionService`): ADK session service for conversation persistence

**Returns**:
- `Workload`: A Workload instance ready to be executed

---

## DefinitionLoader Protocol

Protocol for loading workload definitions from various source formats.

**Location**: `src/streetrace/workloads/loader.py:14`

### Definition

```python
@runtime_checkable
class DefinitionLoader(Protocol):
    """Protocol for loading workload definitions."""

    def can_load(self, path: Path) -> bool:
        ...

    def load(self, path: Path) -> WorkloadDefinition:
        ...

    def discover(self, directory: Path) -> list[Path]:
        ...
```

### Methods

#### `can_load`

Check if this loader can handle the given file type.

**Signature**:
```python
def can_load(self, path: Path) -> bool
```

**Parameters**:
- `path` (`Path`): Path to the file to check

**Returns**:
- `bool`: True if this loader can load the file, False otherwise

#### `load`

Load and compile/parse a workload definition.

**Signature**:
```python
def load(self, path: Path) -> WorkloadDefinition
```

**Parameters**:
- `path` (`Path`): Path to the source file to load

**Returns**:
- `WorkloadDefinition`: A fully populated WorkloadDefinition instance

**Raises**:
- `FileNotFoundError`: If the source file does not exist
- `ValueError`: If the source file cannot be parsed or is invalid

**Contract**: This method must compile/parse the source file immediately. Invalid files should
raise appropriate exceptions rather than returning incomplete definitions.

#### `discover`

Find all loadable files in a directory.

**Signature**:
```python
def discover(self, directory: Path) -> list[Path]
```

**Parameters**:
- `directory` (`Path`): Directory to search for loadable files

**Returns**:
- `list[Path]`: List of paths to files that can be loaded by this loader

### Protocol Compliance

The protocol is runtime-checkable, allowing `isinstance()` verification:

```python
from streetrace.workloads import DefinitionLoader, DslDefinitionLoader

loader = DslDefinitionLoader()
assert isinstance(loader, DefinitionLoader)  # True
```

#### `load_from_url`

Load a workload definition from an HTTP(S) URL.

**Signature**:
```python
def load_from_url(self, url: str) -> WorkloadDefinition
```

**Parameters**:
- `url` (`str`): HTTP(S) URL pointing to the workload definition

**Returns**:
- `WorkloadDefinition`: A fully populated WorkloadDefinition instance

**Raises**:
- `ValueError`: If the URL is invalid, HTTP loading is not supported for this format,
  or content cannot be fetched/parsed

**Note**: Only `YamlDefinitionLoader` supports HTTP loading. `DslDefinitionLoader` and
`PythonDefinitionLoader` reject HTTP URLs for security reasons.

#### `load_from_source`

Load a workload definition from any source type (unified method).

**Signature**:
```python
def load_from_source(
    self,
    identifier: str,
    base_path: Path | None = None,
) -> WorkloadDefinition
```

**Parameters**:
- `identifier` (`str`): Source identifier (URL, path, or name)
- `base_path` (`Path | None`): Base path for resolving relative paths

**Returns**:
- `WorkloadDefinition`: A fully populated WorkloadDefinition instance

**Behavior**:
- HTTP(S) URLs: Delegates to `load_from_url()`
- File paths (absolute, relative, ~/): Delegates to `load()`
- Names: Not supported at loader level (use WorkloadManager)

### Protocol Compliance

The protocol is runtime-checkable, allowing `isinstance()` verification:

```python
from streetrace.workloads import DefinitionLoader, DslDefinitionLoader

loader = DslDefinitionLoader()
assert isinstance(loader, DefinitionLoader)  # True
```

---

## DslAgentFactory

Factory for creating ADK agents from DSL workflow definitions.

**Location**: `src/streetrace/workloads/dsl_agent_factory.py:29`

### Definition

```python
class DslAgentFactory:
    """Factory for creating ADK agents from DSL workflow definitions."""

    def __init__(
        self,
        workflow_class: type[DslAgentWorkflow],
        source_file: Path,
        source_map: list[SourceMapping],
    ) -> None:
        ...
```

### Constructor

```python
def __init__(
    self,
    workflow_class: type[DslAgentWorkflow],
    source_file: Path,
    source_map: list[SourceMapping],
) -> None
```

**Parameters**:
- `workflow_class` (`type[DslAgentWorkflow]`): The compiled DSL workflow class
- `source_file` (`Path`): Path to the source .sr file
- `source_map` (`list[SourceMapping]`): Source mappings for error translation

### Properties

#### `workflow_class`

Get the workflow class.

**Signature**:
```python
@property
def workflow_class(self) -> type[DslAgentWorkflow]
```

#### `source_file`

Get the source file path.

**Signature**:
```python
@property
def source_file(self) -> Path
```

#### `source_map`

Get the source mappings.

**Signature**:
```python
@property
def source_map(self) -> list[SourceMapping]
```

### Methods

#### `create_root_agent`

Create the root ADK agent from the DSL workflow.

**Signature**:
```python
async def create_root_agent(
    self,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
) -> BaseAgent
```

**Parameters**:
- `model_factory` (`ModelFactory`): Factory for creating LLM models
- `tool_provider` (`ToolProvider`): Provider for tools
- `system_context` (`SystemContext`): System context

**Returns**:
- `BaseAgent`: The root ADK agent (typically an `LlmAgent`)

**Behavior**:
- Resolves instruction from the default agent's prompt
- Resolves model (prompt-specific or "main" model)
- Resolves tools from tool definitions
- Creates sub-agents for `delegate` pattern
- Creates agent tools for `use` pattern

#### `create_agent`

Create an LlmAgent from an agent definition dict.

**Signature**:
```python
async def create_agent(
    self,
    agent_name: str,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
) -> BaseAgent
```

**Parameters**:
- `agent_name` (`str`): Name of the agent to create
- `model_factory` (`ModelFactory`): Factory for creating LLM models
- `tool_provider` (`ToolProvider`): Provider for tools
- `system_context` (`SystemContext`): System context

**Returns**:
- `BaseAgent`: The created ADK agent

**Raises**:
- `ValueError`: If agent not found in workflow

**Note**: This method is used for creating both the root agent and sub-agents.
It handles instruction, model, tools resolution and recursively resolves nested patterns.

#### `close`

Clean up resources including sub-agents and agent tools.

**Signature**:
```python
async def close(self, agent_instance: BaseAgent) -> None
```

**Parameters**:
- `agent_instance` (`BaseAgent`): The root agent instance to close

**Behavior**:
- Recursively closes sub-agents (depth-first)
- Closes AgentTool wrappers
- Calls `close()` on tools that support it

### Example

```python
from pathlib import Path
from streetrace.workloads import DslDefinitionLoader

# Load a DSL definition
loader = DslDefinitionLoader()
definition = loader.load(Path("./agents/my_agent.sr"))

# Get the agent factory
factory = definition.agent_factory

# Create the root agent
agent = await factory.create_root_agent(
    model_factory=model_factory,
    tool_provider=tool_provider,
    system_context=system_context,
)

# Use the agent...

# Clean up
await factory.close(agent)
```

---

## DslWorkloadDefinition

Compiled DSL workload definition.

**Location**: `src/streetrace/workloads/dsl_definition.py:25`

### Definition

```python
class DslWorkloadDefinition(WorkloadDefinition):
    """Compiled DSL workload definition."""

    def __init__(
        self,
        metadata: WorkloadMetadata,
        workflow_class: type[DslAgentWorkflow],
        source_map: list[SourceMapping],
    ) -> None:
        ...
```

### Constructor

```python
def __init__(
    self,
    metadata: WorkloadMetadata,
    workflow_class: type[DslAgentWorkflow],
    source_map: list[SourceMapping],
) -> None
```

**Parameters**:
- `metadata` (`WorkloadMetadata`): Immutable metadata describing this workload
- `workflow_class` (`type[DslAgentWorkflow]`): The compiled workflow class from DSL (REQUIRED)
- `source_map` (`list[SourceMapping]`): Source mappings for translating generated code positions back to original DSL source

### Properties

#### `workflow_class`

Get the compiled workflow class.

**Signature**:
```python
@property
def workflow_class(self) -> type[DslAgentWorkflow]
```

**Returns**:
- `type[DslAgentWorkflow]`: The workflow class generated from DSL compilation

#### `source_map`

Get the source mappings.

**Signature**:
```python
@property
def source_map(self) -> list[SourceMapping]
```

**Returns**:
- `list[SourceMapping]`: List of source mappings for error translation

#### `agent_factory`

Get the agent factory for creating ADK agents.

**Signature**:
```python
@property
def agent_factory(self) -> DslAgentFactory
```

**Returns**:
- `DslAgentFactory`: Factory instance configured for this workflow

**Behavior**:
- Created lazily on first access
- Cached for subsequent accesses
- Used by `DslWorkload` for agent creation

### Methods

#### `create_workload`

Create a runnable DslWorkload instance from this definition.

**Signature**:
```python
def create_workload(
    self,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
    session_service: BaseSessionService,
) -> DslWorkload
```

**Returns**:
- `DslWorkload`: A DslWorkload instance ready to be executed

---

## DslDefinitionLoader

Loader for `.sr` DSL files.

**Location**: `src/streetrace/workloads/dsl_loader.py:23`

### Definition

```python
class DslDefinitionLoader:
    """Loader for .sr DSL files."""

    def can_load(self, path: Path) -> bool:
        ...

    def load(self, path: Path) -> DslWorkloadDefinition:
        ...

    def discover(self, directory: Path) -> list[Path]:
        ...
```

### Methods

#### `can_load`

Check if this loader can handle the given file type.

**Signature**:
```python
def can_load(self, path: Path) -> bool
```

**Returns**:
- `bool`: True if path has `.sr` extension and is a file, False otherwise

#### `load`

Load and compile a DSL file.

**Signature**:
```python
def load(self, path: Path) -> DslWorkloadDefinition
```

**Parameters**:
- `path` (`Path`): Path to the `.sr` file to load

**Returns**:
- `DslWorkloadDefinition`: A fully populated definition with `workflow_class`

**Raises**:
- `FileNotFoundError`: If the DSL file does not exist
- `DslSyntaxError`: If parsing fails
- `DslSemanticError`: If semantic analysis fails
- `ValueError`: If no workflow class is found in compiled code

**Behavior**:
- Compilation happens immediately, not deferred
- Extracts name from filename (stem)
- Extracts description from first comment line or uses default
- Source mappings are preserved for error translation

#### `discover`

Find all `.sr` files in a directory.

**Signature**:
```python
def discover(self, directory: Path) -> list[Path]
```

**Parameters**:
- `directory` (`Path`): Directory to search for `.sr` files

**Returns**:
- `list[Path]`: List of paths to `.sr` files found (recursively)

### Example

```python
from pathlib import Path
from streetrace.workloads import DslDefinitionLoader, DslWorkloadDefinition

loader = DslDefinitionLoader()

# Check if can load
assert loader.can_load(Path("agent.sr"))
assert not loader.can_load(Path("agent.yaml"))

# Load a definition
definition = loader.load(Path("./agents/my_agent.sr"))
assert isinstance(definition, DslWorkloadDefinition)
assert definition.workflow_class is not None

# Discover all DSL files
paths = loader.discover(Path("./agents"))
for path in paths:
    print(f"Found: {path}")
```

---

## DslWorkload

Runnable DSL workload implementing the Workload protocol.

**Location**: `src/streetrace/workloads/dsl_workload.py:27`

### Definition

```python
class DslWorkload:
    """Runnable DSL workload implementing the Workload protocol."""

    def __init__(
        self,
        definition: DslWorkloadDefinition,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
        session_service: BaseSessionService,
    ) -> None:
        ...
```

### Constructor

All parameters are REQUIRED. This workload should only be created through
`DslWorkloadDefinition.create_workload()`.

```python
def __init__(
    self,
    definition: DslWorkloadDefinition,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
    session_service: BaseSessionService,
) -> None
```

**Parameters**:
- `definition` (`DslWorkloadDefinition`): The compiled DSL workload definition
- `model_factory` (`ModelFactory`): Factory for creating and managing LLM models
- `tool_provider` (`ToolProvider`): Provider of tools for the workload
- `system_context` (`SystemContext`): System context containing project-level settings
- `session_service` (`BaseSessionService`): ADK session service for conversation persistence

### Methods

#### `run_async`

Execute the workload and yield events.

**Signature**:
```python
async def run_async(
    self,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event, None]
```

**Parameters**:
- `session` (`Session`): ADK session for conversation persistence
- `message` (`Content | None`): User message to process, or None for initial runs

**Yields**:
- `Event`: ADK events from execution

#### `close`

Clean up all resources allocated by this workload.

**Signature**:
```python
async def close(self) -> None
```

### Properties

#### `definition`

Get the workload definition.

**Signature**:
```python
@property
def definition(self) -> DslWorkloadDefinition
```

#### `workflow`

Get the underlying workflow instance.

**Signature**:
```python
@property
def workflow(self) -> DslAgentWorkflow
```

---

## YamlWorkloadDefinition

Parsed YAML workload definition.

**Location**: `src/streetrace/workloads/yaml_definition.py:23`

### Definition

```python
class YamlWorkloadDefinition(WorkloadDefinition):
    """Parsed YAML workload definition."""

    def __init__(
        self,
        metadata: WorkloadMetadata,
        spec: YamlAgentSpec,
    ) -> None:
        ...
```

### Constructor

```python
def __init__(
    self,
    metadata: WorkloadMetadata,
    spec: YamlAgentSpec,
) -> None
```

**Parameters**:
- `metadata` (`WorkloadMetadata`): Immutable metadata describing this workload
- `spec` (`YamlAgentSpec`): The parsed YAML agent specification (REQUIRED)

### Properties

#### `spec`

Get the YAML agent specification.

**Signature**:
```python
@property
def spec(self) -> YamlAgentSpec
```

**Returns**:
- `YamlAgentSpec`: The YamlAgentSpec containing the agent definition

### Methods

#### `create_workload`

Create a runnable BasicAgentWorkload instance from this definition.

**Signature**:
```python
def create_workload(
    self,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
    session_service: BaseSessionService,
) -> BasicAgentWorkload
```

**Returns**:
- `BasicAgentWorkload`: A BasicAgentWorkload instance ready to be executed

---

## YamlDefinitionLoader

Loader for YAML agent files.

**Location**: `src/streetrace/workloads/yaml_loader.py:24`

### Definition

```python
class YamlDefinitionLoader:
    """Loader for YAML agent files."""

    def __init__(self, http_auth: str | None = None) -> None:
        ...

    def can_load(self, path: Path) -> bool:
        ...

    def load(self, path: Path) -> YamlWorkloadDefinition:
        ...

    def discover(self, directory: Path) -> list[Path]:
        ...
```

### Constructor

```python
def __init__(self, http_auth: str | None = None) -> None
```

**Parameters**:
- `http_auth` (`str | None`): Optional authorization header value for HTTP agent URIs

### Methods

#### `can_load`

Check if this loader can handle the given file type.

**Signature**:
```python
def can_load(self, path: Path) -> bool
```

**Returns**:
- `bool`: True if path has `.yaml` or `.yml` extension and is a file

#### `load`

Load and parse a YAML agent file.

**Signature**:
```python
def load(self, path: Path) -> YamlWorkloadDefinition
```

**Raises**:
- `FileNotFoundError`: If the YAML file does not exist
- `AgentValidationError`: If parsing or validation fails

#### `discover`

Find all YAML files in a directory.

**Signature**:
```python
def discover(self, directory: Path) -> list[Path]
```

**Returns**:
- `list[Path]`: List of paths to `.yaml` and `.yml` files found (recursively)

---

## PythonWorkloadDefinition

Python module workload definition.

**Location**: `src/streetrace/workloads/python_definition.py:24`

### Definition

```python
class PythonWorkloadDefinition(WorkloadDefinition):
    """Python module workload definition."""

    def __init__(
        self,
        metadata: WorkloadMetadata,
        agent_class: type[StreetRaceAgent],
        module: ModuleType,
    ) -> None:
        ...
```

### Constructor

```python
def __init__(
    self,
    metadata: WorkloadMetadata,
    agent_class: type[StreetRaceAgent],
    module: ModuleType,
) -> None
```

**Parameters**:
- `metadata` (`WorkloadMetadata`): Immutable metadata describing this workload
- `agent_class` (`type[StreetRaceAgent]`): The StreetRaceAgent subclass found in the module
- `module` (`ModuleType`): The Python module containing the agent class

### Properties

#### `agent_class`

Get the agent class.

**Signature**:
```python
@property
def agent_class(self) -> type[StreetRaceAgent]
```

#### `module`

Get the module.

**Signature**:
```python
@property
def module(self) -> ModuleType
```

### Methods

#### `create_workload`

Create a runnable BasicAgentWorkload instance from this definition.

**Signature**:
```python
def create_workload(
    self,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
    session_service: BaseSessionService,
) -> BasicAgentWorkload
```

---

## PythonDefinitionLoader

Loader for Python agent modules.

**Location**: `src/streetrace/workloads/python_loader.py:23`

### Definition

```python
class PythonDefinitionLoader:
    """Loader for Python agent modules."""

    def can_load(self, path: Path) -> bool:
        ...

    def load(self, path: Path) -> PythonWorkloadDefinition:
        ...

    def discover(self, directory: Path) -> list[Path]:
        ...
```

### Methods

#### `can_load`

Check if this loader can handle the given path.

**Signature**:
```python
def can_load(self, path: Path) -> bool
```

**Returns**:
- `bool`: True if path is a directory containing `agent.py`, False otherwise

#### `load`

Load and validate a Python agent module.

**Signature**:
```python
def load(self, path: Path) -> PythonWorkloadDefinition
```

**Parameters**:
- `path` (`Path`): Path to the agent directory (must contain `agent.py`)

**Raises**:
- `FileNotFoundError`: If the directory or `agent.py` does not exist
- `ValueError`: If the module cannot be imported or has no StreetRaceAgent

#### `discover`

Find all Python agent directories.

**Signature**:
```python
def discover(self, directory: Path) -> list[Path]
```

**Returns**:
- `list[Path]`: List of paths to directories containing `agent.py`

---

## WorkloadNotFoundError

Exception raised when a workload definition cannot be found by name.

**Location**: `src/streetrace/workloads/manager.py:93`

### Definition

```python
class WorkloadNotFoundError(Exception):
    """Raised when a workload definition cannot be found by name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Workload '{name}' not found")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | The name of the workload that could not be found |

### Example

```python
from streetrace.workloads import WorkloadManager, WorkloadNotFoundError

try:
    workload = manager.create_workload_from_definition("nonexistent")
except WorkloadNotFoundError as e:
    print(f"Workload not found: {e.name}")
```

---

## WorkloadManager New Methods

Extended methods on WorkloadManager for the unified definition system.

**Location**: `src/streetrace/workloads/manager.py:169`

### `discover_definitions`

Discover and compile all workload definitions.

**Signature**:
```python
def discover_definitions(self) -> list[WorkloadDefinition]
```

**Returns**:
- `list[WorkloadDefinition]`: List of successfully loaded WorkloadDefinition objects

**Behavior**:
- Uses the new DefinitionLoader system
- Compilation happens immediately during `load()`
- Invalid files are logged as warnings but don't stop discovery
- Results are cached in `_definitions` dict

### `create_workload_from_definition`

Create a runnable workload by name using the new definition system.

**Signature**:
```python
def create_workload_from_definition(self, name: str) -> Workload
```

**Parameters**:
- `name` (`str`): The workload name to create

**Returns**:
- `Workload`: A Workload instance ready for execution

**Raises**:
- `WorkloadNotFoundError`: If no definition with this name is found
- `ValueError`: If session_service is not set

**Behavior**:
- Checks cache first
- Runs discovery if not in cache
- Delegates to `definition.create_workload()` for workload creation

### Example

```python
from streetrace.workloads import WorkloadManager

# Discover all definitions
definitions = manager.discover_definitions()
for defn in definitions:
    print(f"{defn.name} ({defn.metadata.format})")

# Create and use a workload
workload = manager.create_workload_from_definition("my_agent")
try:
    async for event in workload.run_async(session, message):
        process_event(event)
finally:
    await workload.close()
```

---

## Type Imports

For type checking, import from the main package:

```python
from streetrace.workloads import (
    BasicAgentWorkload,
    DefinitionLoader,
    DslDefinitionLoader,
    DslWorkload,
    DslWorkloadDefinition,
    PythonDefinitionLoader,
    PythonWorkloadDefinition,
    Workload,
    WorkloadDefinition,
    WorkloadManager,
    WorkloadMetadata,
    WorkloadNotFoundError,
    YamlDefinitionLoader,
    YamlWorkloadDefinition,
)

# DslAgentFactory is imported from its module directly
from streetrace.workloads.dsl_agent_factory import DslAgentFactory
```

For TYPE_CHECKING imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
```

---

## See Also

- [Architecture](architecture.md) - Design overview and component relationships
- [Extension Guide](extension-guide.md) - Creating custom DefinitionLoader implementations
- [DSL Runtime](../dsl/architecture.md) - DSL compiler and runtime details
