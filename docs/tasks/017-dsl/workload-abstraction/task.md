# Task Definition: Workload Abstraction Refactoring

## Feature Information

- **Feature ID**: 017-dsl
- **Task ID**: workload-abstraction
- **Branch**: feature/017-streetrace-dsl-2
- **Priority**: High
- **Estimated Complexity**: Large

## Executive Summary

Refactor the agent loading and workload creation pipeline to eliminate architectural
inconsistencies, remove optional parameters that should be required, and establish
a clean separation between workload definitions (compiled artifacts) and workload
instances (running executions).

---

## Part 1: Problem Analysis

### 1.1 The Fundamental Naming Problem

The codebase uses inconsistent terminology that obscures the true abstraction:

| Current Name | What It Actually Is | Proposed Name |
|--------------|---------------------|---------------|
| `AgentInfo` | Workload definition metadata | `WorkloadMetadata` |
| `DslAgentInfo` | Incomplete DSL definition | `DslWorkloadDefinition` |
| `AgentLoader` | Definition loader protocol | `DefinitionLoader` |
| `AgentManager` | Workload manager (renamed) | `WorkloadManager` (done) |
| `DslStreetRaceAgent` | DSL definition + factory | Split into Definition + Workload |

The `WorkloadManager` rename was completed, but downstream types still use "Agent"
terminology, creating cognitive dissonance.

### 1.2 The Deferred Compilation Problem

**Current flow for DSL files:**

```
Discovery Phase:
  .sr file -> _extract_agent_info() -> DslAgentInfo(workflow_class=None)

Loading Phase (later):
  DslAgentInfo -> _load_dsl_file() -> compile_dsl() -> DslStreetRaceAgent
```

**Problems:**

1. `DslAgentInfo` exists in an incomplete state with `workflow_class=None`
2. Invalid DSL files aren't detected until load time
3. Discovery cache contains "promises" rather than compiled artifacts
4. Error messages appear late in the pipeline

**Ideal flow:**

```
Discovery Phase:
  .sr file -> DslDefinitionLoader.load() -> compile_dsl() -> DslWorkloadDefinition
  (compilation happens immediately, invalid files rejected early)

Execution Phase:
  DslWorkloadDefinition.create_workload() -> DslWorkload (running instance)
```

### 1.3 The Optional Parameters Problem

Multiple classes accept `None` for semantically required parameters:

**DslAgentWorkflow constructor (workflow.py:66-91):**
```python
def __init__(
    self,
    agent_definition: "DslStreetRaceAgent | None" = None,  # Should be required
    model_factory: "ModelFactory | None" = None,           # Should be required
    tool_provider: "ToolProvider | None" = None,           # Should be required
    system_context: "SystemContext | None" = None,         # Should be required
    session_service: "BaseSessionService | None" = None,   # Should be required
) -> None:
```

This leads to runtime validation (lines 144-151):
```python
if (
    not self._agent_def
    or not self._model_factory
    or not self._tool_provider
    or not self._system_context
):
    msg = "DslAgentWorkflow not properly initialized for agent creation"
    raise ValueError(msg)
```

**Contrast with BasicAgentWorkload (basic_workload.py:34-44):**
```python
def __init__(
    self,
    agent_definition: "StreetRaceAgent",      # Required!
    model_factory: "ModelFactory",             # Required!
    tool_provider: "ToolProvider",             # Required!
    system_context: "SystemContext",           # Required!
    session_service: "BaseSessionService",     # Required!
) -> None:
```

The inconsistency creates confusion and potential runtime failures.

### 1.4 The Dual WorkflowContext Problem

`WorkflowContext` accepts `workflow=None` and implements fallback logic:

```python
# context.py:233-252
async def run_agent(self, agent_name: str, *args: object) -> object:
    # Delegate to workflow when connected (preferred path)
    if self._workflow:
        return await self._workflow.run_agent(agent_name, *args)

    # Fallback implementation for backward compatibility
    return await self._run_agent_fallback(agent_name, *args)
```

**Problems:**

1. Two code paths for the same operation
2. Fallback behavior may diverge from primary path
3. Testing burden doubled
4. `WorkflowContext()` created with `workflow=None` in `DslStreetRaceAgent._resolve_instruction`

### 1.5 The Duplicate DslAgentLoader Problem

Two classes named `DslAgentLoader` exist:

| Location | Purpose | Returns |
|----------|---------|---------|
| `agents/dsl_agent_loader.py:59` | AgentLoader interface for WorkloadManager | `DslStreetRaceAgent` |
| `dsl/loader.py:37` | Public API for direct loading | `type[DslAgentWorkflow]` |

Both contain nearly identical bytecode execution logic. This violates DRY and
creates maintenance burden.

### 1.6 The Polymorphic AgentInfo Problem

`AgentInfo` uses optional fields to represent a union type:

```python
class AgentInfo:
    def __init__(
        self,
        name: str,
        description: str,
        file_path: Path | None = None,      # Set for file-based
        module: ModuleType | None = None,    # Set for Python
        yaml_document: YamlAgentDocument | None = None,  # Set for YAML
    ) -> None:
```

The `kind` property determines type at runtime:
```python
@property
def kind(self) -> Literal["python", "yaml"]:
    if self.yaml_document is not None:
        return "yaml"
    if self.module is not None:
        return "python"
    raise ValueError(...)  # Runtime error if neither set!
```

This is a union type disguised as optional fields, leading to potential runtime errors.

---

## Part 2: Target Architecture

### 2.1 Design Principles

1. **No Optional fields for semantically required data**
   - If a field is needed for the object to function, it's required at construction
   - Type system enforces correctness, not runtime checks

2. **Compile during discovery, not loading**
   - Invalid files are rejected immediately
   - Cache contains only valid, compiled definitions
   - Errors surface early with clear context

3. **Single source of truth**
   - One loader per format, no duplicates
   - Clear ownership of compilation logic

4. **Immutable definitions**
   - `WorkloadDefinition` is frozen after creation
   - No state changes between discovery and execution

5. **Clear lifecycle separation**
   - Definition (compiled artifact) -> Workload (running instance) -> Context (execution state)

6. **Consistent naming**
   - All types use "Workload" terminology
   - No mixed Agent/Workload naming

### 2.2 Type Hierarchy

```
WorkloadMetadata (dataclass, frozen)
+-- name: str
+-- description: str
+-- source_path: Path
+-- format: Literal["dsl", "yaml", "python"]

WorkloadDefinition (ABC)
+-- metadata: WorkloadMetadata
+-- create_workload(...) -> Workload
|
+-- DslWorkloadDefinition
|   +-- workflow_class: type[DslAgentWorkflow]  # REQUIRED
|   +-- source_map: list[SourceMapping]          # REQUIRED
|
+-- YamlWorkloadDefinition
|   +-- spec: YamlAgentSpec                      # REQUIRED
|
+-- PythonWorkloadDefinition
    +-- agent_class: type[StreetRaceAgent]       # REQUIRED

DefinitionLoader (Protocol)
+-- can_load(path) -> bool
+-- load(path) -> WorkloadDefinition
+-- discover(directory) -> list[Path]
|
+-- DslDefinitionLoader
+-- YamlDefinitionLoader
+-- PythonDefinitionLoader

Workload (Protocol)
+-- run_async(session, message) -> AsyncGenerator[Event, None]
+-- close() -> None
|
+-- DslWorkload
|   +-- definition: DslWorkloadDefinition  # REQUIRED
|   +-- model_factory: ModelFactory        # REQUIRED
|   +-- ... (all required)
|
+-- BasicWorkload (for YAML/Python)
    +-- definition: WorkloadDefinition     # REQUIRED
    +-- ... (all required)

WorkflowContext
+-- workflow: DslAgentWorkflow  # REQUIRED (not Optional)
```

### 2.3 Data Flow

```
DISCOVERY PHASE
===============
.sr file --> DslDefinitionLoader.load() --> compile_dsl()
                                            |
                                            v
                                 DslWorkloadDefinition
                                 (workflow_class populated)
                                            |
                                            v
                           WorkloadManager._definitions cache

EXECUTION PHASE
===============
WorkloadManager.create_workload(name)
        |
        v
definition.create_workload(model_factory, tool_provider, ...)
        |
        v
DslWorkload(
    definition=definition,        # Has workflow_class
    model_factory=...,            # All required
)
        |
        +---> self._workflow = definition.workflow_class()
        |
        +---> self._context = WorkflowContext(workflow=self._workflow)
                                              |
                                              v
                                 Context always has workflow ref
```

### 2.4 File Structure

```
src/streetrace/workloads/
+-- __init__.py              # Public exports
+-- protocol.py              # Workload protocol (exists)
+-- metadata.py              # NEW: WorkloadMetadata dataclass
+-- definition.py            # NEW: WorkloadDefinition ABC
+-- dsl_definition.py        # NEW: DslWorkloadDefinition
+-- yaml_definition.py       # NEW: YamlWorkloadDefinition
+-- python_definition.py     # NEW: PythonWorkloadDefinition
+-- loader.py                # NEW: DefinitionLoader protocol
+-- dsl_loader.py            # NEW: DslDefinitionLoader (consolidated)
+-- yaml_loader.py           # NEW: YamlDefinitionLoader
+-- python_loader.py         # NEW: PythonDefinitionLoader
+-- dsl_workload.py          # NEW: DslWorkload (runtime)
+-- basic_workload.py        # EXISTS: Rename internals
+-- manager.py               # EXISTS: Refactor to use new types

src/streetrace/dsl/
+-- loader.py                # DELETE: Consolidated into workloads/dsl_loader.py
+-- runtime/
    +-- workflow.py          # MODIFY: Remove optional deps from __init__
    +-- context.py           # MODIFY: Make workflow required

src/streetrace/agents/
+-- dsl_agent_loader.py      # DELETE: Consolidated into workloads/dsl_loader.py
+-- base_agent_loader.py     # DEPRECATE: Keep for backward compat
+-- yaml_agent_loader.py     # MODIFY: Delegate to workloads/yaml_loader.py
+-- py_agent_loader.py       # MODIFY: Delegate to workloads/python_loader.py
```

---

## Part 3: Phased Implementation Plan

### Phase 1: Foundation Types (No Breaking Changes)

**Goal:** Introduce new types alongside existing ones.

#### 1.1 Create WorkloadMetadata

**File:** `src/streetrace/workloads/metadata.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass(frozen=True)
class WorkloadMetadata:
    """Immutable metadata about a workload definition."""

    name: str
    description: str
    source_path: Path
    format: Literal["dsl", "yaml", "python"]
```

#### 1.2 Create WorkloadDefinition ABC

**File:** `src/streetrace/workloads/definition.py`

```python
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from streetrace.workloads.protocol import Workload
    # ... other imports

class WorkloadDefinition(ABC):
    """Base class for compiled workload definitions."""

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
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> "Workload":
        """Create a runnable workload instance."""
        ...
```

#### 1.3 Create DefinitionLoader Protocol

**File:** `src/streetrace/workloads/loader.py`

```python
from pathlib import Path
from typing import Protocol

from streetrace.workloads.definition import WorkloadDefinition

class DefinitionLoader(Protocol):
    """Protocol for loading workload definitions."""

    def can_load(self, path: Path) -> bool:
        """Check if this loader handles the given file type."""
        ...

    def load(self, path: Path) -> WorkloadDefinition:
        """Load and compile/parse a workload definition."""
        ...

    def discover(self, directory: Path) -> list[Path]:
        """Find all loadable files in a directory."""
        ...
```

#### 1.4 Tests for Foundation Types

- Unit tests for WorkloadMetadata immutability
- Unit tests for WorkloadDefinition ABC
- Unit tests for DefinitionLoader protocol compliance

---

### Phase 2: DSL Definition and Loader

**Goal:** Consolidate DSL loading into single implementation.

#### 2.1 Create DslWorkloadDefinition

**File:** `src/streetrace/workloads/dsl_definition.py`

```python
from dataclasses import dataclass
from typing import TYPE_CHECKING

from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.dsl.sourcemap import SourceMapping
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.metadata import WorkloadMetadata

if TYPE_CHECKING:
    from streetrace.workloads.dsl_workload import DslWorkload

@dataclass
class DslWorkloadDefinition(WorkloadDefinition):
    """Compiled DSL workload definition.

    Created ONLY after successful DSL compilation.
    """

    _workflow_class: type[DslAgentWorkflow]
    _source_map: list[SourceMapping]

    def __init__(
        self,
        metadata: WorkloadMetadata,
        workflow_class: type[DslAgentWorkflow],
        source_map: list[SourceMapping],
    ) -> None:
        super().__init__(metadata)
        self._workflow_class = workflow_class
        self._source_map = source_map

    @property
    def workflow_class(self) -> type[DslAgentWorkflow]:
        return self._workflow_class

    @property
    def source_map(self) -> list[SourceMapping]:
        return self._source_map

    def create_workload(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> "DslWorkload":
        from streetrace.workloads.dsl_workload import DslWorkload

        return DslWorkload(
            definition=self,
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            session_service=session_service,
        )
```

#### 2.2 Create DslDefinitionLoader (Consolidated)

**File:** `src/streetrace/workloads/dsl_loader.py`

Consolidates logic from:
- `src/streetrace/agents/dsl_agent_loader.py` (DslAgentLoader class)
- `src/streetrace/dsl/loader.py` (DslAgentLoader class)

```python
from pathlib import Path

from streetrace.dsl.compiler import compile_dsl
from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.workloads.dsl_definition import DslWorkloadDefinition
from streetrace.workloads.loader import DefinitionLoader
from streetrace.workloads.metadata import WorkloadMetadata

class DslDefinitionLoader:
    """Loader for .sr DSL files.

    Compiles DSL source during load() - no deferred compilation.
    """

    def can_load(self, path: Path) -> bool:
        return path.suffix == ".sr"

    def load(self, path: Path) -> DslWorkloadDefinition:
        """Load and compile a DSL file.

        Compilation happens immediately. Invalid files raise exceptions.
        """
        if not path.exists():
            msg = f"DSL file not found: {path}"
            raise FileNotFoundError(msg)

        source = path.read_text()
        bytecode, source_map = compile_dsl(source, str(path))

        # Run bytecode to get workflow class
        namespace: dict[str, object] = {}
        compiled_code = compile(bytecode, str(path), "exec")
        # SECURITY: Bytecode is from validated DSL, not arbitrary input
        exec(compiled_code, namespace)  # noqa: S102  # nosec B102

        workflow_class = self._find_workflow_class(namespace, path)

        # Extract metadata from compiled class
        metadata = WorkloadMetadata(
            name=self._extract_name(workflow_class, path),
            description=self._extract_description(workflow_class, path),
            source_path=path,
            format="dsl",
        )

        return DslWorkloadDefinition(
            metadata=metadata,
            workflow_class=workflow_class,
            source_map=source_map,
        )

    def discover(self, directory: Path) -> list[Path]:
        if not directory.is_dir():
            return []
        return list(directory.rglob("*.sr"))

    def _find_workflow_class(
        self,
        namespace: dict[str, object],
        path: Path,
    ) -> type[DslAgentWorkflow]:
        for obj in namespace.values():
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, DslAgentWorkflow):
                continue
            if obj is DslAgentWorkflow:
                continue
            return obj

        msg = f"No workflow class found in compiled DSL: {path}"
        raise ValueError(msg)

    def _extract_name(
        self,
        workflow_class: type[DslAgentWorkflow],
        path: Path,
    ) -> str:
        # Try to get from class attribute, fall back to filename
        if hasattr(workflow_class, "_dsl_name"):
            return str(workflow_class._dsl_name)
        return path.stem

    def _extract_description(
        self,
        workflow_class: type[DslAgentWorkflow],
        path: Path,
    ) -> str:
        if hasattr(workflow_class, "_dsl_description"):
            return str(workflow_class._dsl_description)
        return f"DSL workload from {path.name}"
```

#### 2.3 Create DslWorkload (Runtime)

**File:** `src/streetrace/workloads/dsl_workload.py`

```python
from typing import TYPE_CHECKING, AsyncGenerator

from streetrace.dsl.runtime.context import WorkflowContext
from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.workloads.dsl_definition import DslWorkloadDefinition

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.genai.types import Content

    from streetrace.llm import ModelFactory
    from streetrace.session import SystemContext
    from streetrace.session.base_session_service import BaseSessionService
    from streetrace.tools import ToolProvider

class DslWorkload:
    """Runnable DSL workload - implements Workload protocol.

    All dependencies are REQUIRED at construction time.
    """

    def __init__(
        self,
        definition: DslWorkloadDefinition,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> None:
        # All fields required - enforced by type system
        self._definition = definition
        self._model_factory = model_factory
        self._tool_provider = tool_provider
        self._system_context = system_context
        self._session_service = session_service

        # Create workflow instance immediately
        self._workflow: DslAgentWorkflow = definition.workflow_class()

        # Initialize workflow with dependencies
        self._workflow.set_dependencies(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            session_service=session_service,
        )

        # Create context WITH workflow reference - never None
        self._context = WorkflowContext(workflow=self._workflow)

    async def run_async(
        self,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Run the workload."""
        async for event in self._workflow.run_async(session, message):
            yield event

    async def close(self) -> None:
        """Clean up resources."""
        await self._workflow.close()
```

#### 2.4 Tests for DSL Components

- Unit tests for DslWorkloadDefinition
- Unit tests for DslDefinitionLoader (compile on load)
- Unit tests for DslWorkload (all deps required)
- Integration tests for full DSL loading pipeline

---

### Phase 3: Refactor DslAgentWorkflow and WorkflowContext

**Goal:** Remove optional parameters, make workflow required in context.

#### 3.1 Add set_dependencies() to DslAgentWorkflow

**File:** `src/streetrace/dsl/runtime/workflow.py`

```python
class DslAgentWorkflow:
    """Base class for generated DSL workflows."""

    def __init__(self) -> None:
        """Initialize the workflow.

        Dependencies are set via set_dependencies() after construction.
        This allows the compiled class to be instantiated without args.
        """
        self._model_factory: ModelFactory | None = None
        self._tool_provider: ToolProvider | None = None
        self._system_context: SystemContext | None = None
        self._session_service: BaseSessionService | None = None
        self._context: WorkflowContext | None = None
        self._initialized = False

    def set_dependencies(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> None:
        """Set runtime dependencies.

        Must be called before run_async(). All parameters required.
        """
        self._model_factory = model_factory
        self._tool_provider = tool_provider
        self._system_context = system_context
        self._session_service = session_service
        self._initialized = True

    def _ensure_initialized(self) -> None:
        """Raise if dependencies not set."""
        if not self._initialized:
            msg = "DslAgentWorkflow.set_dependencies() must be called first"
            raise RuntimeError(msg)
```

#### 3.2 Make workflow Required in WorkflowContext

**File:** `src/streetrace/dsl/runtime/context.py`

```python
class WorkflowContext:
    """Execution context for DSL workflows.

    The workflow reference is REQUIRED - no fallback paths.
    """

    def __init__(self, workflow: "DslAgentWorkflow") -> None:
        """Initialize the workflow context.

        Args:
            workflow: Parent workflow for delegation. REQUIRED.
        """
        self._workflow = workflow  # Not Optional!
        self.vars: dict[str, object] = {}
        self.message: str = ""
        self.guardrails = GuardrailProvider()

    async def run_agent(self, agent_name: str, *args: object) -> object:
        """Run a named agent - always delegates to workflow."""
        # Single code path - no fallback
        return await self._workflow.run_agent(agent_name, *args)

    async def run_flow(self, flow_name: str, *args: object) -> object:
        """Run a named flow - always delegates to workflow."""
        return await self._workflow.run_flow(flow_name, *args)
```

#### 3.3 Create Lightweight Context for Prompt Resolution

For `DslStreetRaceAgent._resolve_instruction()` which needs a context without
full workflow, create a specialized minimal context:

**File:** `src/streetrace/dsl/runtime/prompt_context.py`

```python
class PromptResolutionContext:
    """Minimal context for resolving prompts during agent creation.

    Unlike WorkflowContext, this doesn't require a workflow reference
    because it's only used for prompt evaluation, not agent execution.
    """

    def __init__(self) -> None:
        self.vars: dict[str, object] = {}
        self.message: str = ""

    # Only prompt-related methods, no run_agent/run_flow
```

#### 3.4 Tests for Refactored Components

- Test WorkflowContext requires workflow
- Test DslAgentWorkflow.set_dependencies() pattern
- Test PromptResolutionContext for prompt evaluation
- Verify no fallback paths remain

---

### Phase 4: YAML and Python Definitions

**Goal:** Create definition types for YAML and Python workloads.

#### 4.1 Create YamlWorkloadDefinition

**File:** `src/streetrace/workloads/yaml_definition.py`

```python
from streetrace.agents.yaml_models import YamlAgentSpec
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.metadata import WorkloadMetadata

class YamlWorkloadDefinition(WorkloadDefinition):
    """Parsed YAML workload definition."""

    def __init__(
        self,
        metadata: WorkloadMetadata,
        spec: YamlAgentSpec,
    ) -> None:
        super().__init__(metadata)
        self._spec = spec

    @property
    def spec(self) -> YamlAgentSpec:
        return self._spec

    def create_workload(self, ...) -> "BasicWorkload":
        from streetrace.workloads.basic_workload import BasicWorkload
        return BasicWorkload(definition=self, ...)
```

#### 4.2 Create PythonWorkloadDefinition

**File:** `src/streetrace/workloads/python_definition.py`

```python
from types import ModuleType

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.metadata import WorkloadMetadata

class PythonWorkloadDefinition(WorkloadDefinition):
    """Python module workload definition."""

    def __init__(
        self,
        metadata: WorkloadMetadata,
        agent_class: type[StreetRaceAgent],
        module: ModuleType,
    ) -> None:
        super().__init__(metadata)
        self._agent_class = agent_class
        self._module = module

    @property
    def agent_class(self) -> type[StreetRaceAgent]:
        return self._agent_class

    def create_workload(self, ...) -> "BasicWorkload":
        from streetrace.workloads.basic_workload import BasicWorkload
        return BasicWorkload(definition=self, ...)
```

#### 4.3 Create YamlDefinitionLoader and PythonDefinitionLoader

Implement loaders that parse/validate during load(), not discovery.

#### 4.4 Update BasicWorkload

**File:** `src/streetrace/workloads/basic_workload.py`

```python
class BasicWorkload:
    """Workload for Python and YAML definitions."""

    def __init__(
        self,
        definition: YamlWorkloadDefinition | PythonWorkloadDefinition,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> None:
        self._definition = definition
        # ... all required
```

---

### Phase 5: Integrate with WorkloadManager

**Goal:** Update WorkloadManager to use new types.

#### 5.1 Update WorkloadManager

**File:** `src/streetrace/workloads/manager.py`

```python
class WorkloadManager:
    """Discover and create workloads."""

    def __init__(self, ...) -> None:
        # Loaders by file extension
        self._loaders: dict[str, DefinitionLoader] = {
            ".sr": DslDefinitionLoader(),
            ".yaml": YamlDefinitionLoader(),
            ".yml": YamlDefinitionLoader(),
        }

        # Cache of COMPILED definitions
        self._definitions: dict[str, WorkloadDefinition] = {}

    def discover(self) -> list[WorkloadDefinition]:
        """Discover and compile all workloads."""
        definitions: list[WorkloadDefinition] = []

        for path in self._find_workload_files():
            loader = self._get_loader(path)
            if not loader:
                continue

            try:
                definition = loader.load(path)  # Compile NOW
                definitions.append(definition)
                self._definitions[definition.name] = definition
            except Exception as e:
                logger.warning("Failed to load %s: %s", path, e)

        return definitions

    def create_workload(self, name: str) -> Workload:
        """Create a runnable workload by name."""
        definition = self._definitions.get(name)
        if not definition:
            self.discover()
            definition = self._definitions.get(name)

        if not definition:
            raise WorkloadNotFoundError(name)

        return definition.create_workload(
            model_factory=self._model_factory,
            tool_provider=self._tool_provider,
            system_context=self._system_context,
            session_service=self._session_service,
        )
```

#### 5.2 Update Package Exports

**File:** `src/streetrace/workloads/__init__.py`

```python
from streetrace.workloads.basic_workload import BasicWorkload
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.dsl_definition import DslWorkloadDefinition
from streetrace.workloads.dsl_loader import DslDefinitionLoader
from streetrace.workloads.dsl_workload import DslWorkload
from streetrace.workloads.loader import DefinitionLoader
from streetrace.workloads.manager import WorkloadManager
from streetrace.workloads.metadata import WorkloadMetadata
from streetrace.workloads.protocol import Workload
from streetrace.workloads.python_definition import PythonWorkloadDefinition
from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

__all__ = [
    "BasicWorkload",
    "DefinitionLoader",
    "DslDefinitionLoader",
    "DslWorkload",
    "DslWorkloadDefinition",
    "Workload",
    "WorkloadDefinition",
    "WorkloadManager",
    "WorkloadMetadata",
    "PythonWorkloadDefinition",
    "YamlWorkloadDefinition",
]
```

---

### Phase 6: Cleanup and Migration

**Goal:** Remove deprecated types, update documentation.

#### 6.1 Delete Deprecated Files

- `src/streetrace/dsl/loader.py` (DslAgentLoader)
- `src/streetrace/agents/dsl_agent_loader.py` (DslAgentLoader, DslAgentInfo, DslStreetRaceAgent)

#### 6.2 Update dsl Package Exports

**File:** `src/streetrace/dsl/__init__.py`

Remove `DslAgentLoader` export, add note about new location.

#### 6.3 Deprecate AgentInfo and AgentLoader

Keep `base_agent_loader.py` with deprecation warnings for backward compatibility.

#### 6.4 Update Documentation

- Update `docs/dev/workloads/` with new architecture
- Update `docs/user/dsl/` with new loading patterns
- Add migration guide for external users

#### 6.5 Update Tests

- Migrate all tests to use new types
- Remove tests for deprecated types
- Add comprehensive tests for new pipeline

---

## Part 4: Success Criteria

### Functional Requirements

- [ ] All workload types (DSL, YAML, Python) load through unified pipeline
- [ ] DSL files are compiled during discovery, not deferred
- [ ] Invalid DSL files are rejected immediately with clear errors
- [ ] WorkflowContext always has a workflow reference
- [ ] No Optional parameters for semantically required fields
- [ ] Single DslDefinitionLoader implementation (no duplicates)

### Non-Functional Requirements

- [ ] No breaking changes to DSL syntax
- [ ] No breaking changes to YAML agent format
- [ ] No breaking changes to Python agent interface
- [ ] All existing tests pass
- [ ] Test coverage > 90% for new code
- [ ] `make check` passes

### Code Quality

- [ ] Consistent "Workload" naming throughout
- [ ] No runtime type checks that should be compile-time
- [ ] Clear separation: Definition (compiled) vs Workload (running)
- [ ] Immutable WorkloadMetadata and WorkloadDefinition

---

## Part 5: Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Breaking external DSL users | High | Low | Keep `dsl/__init__.py` exports with deprecation |
| Performance regression in discovery | Medium | Medium | Benchmark before/after, consider lazy compilation option |
| Circular imports | Medium | Medium | Use TYPE_CHECKING, careful import structure |
| Test migration complexity | Medium | High | Migrate tests incrementally per phase |
| Backward compat for agents/ package | Medium | Medium | Keep deprecated types with warnings |

---

## Part 6: Dependencies

### Internal Dependencies

- Workload protocol (exists)
- DSL compiler (exists)
- YAML agent models (exists)
- Python agent loader (exists)

### External Dependencies

None - pure refactoring of internal architecture.

---

## Part 7: Estimated Effort

| Phase | Description | Complexity |
|-------|-------------|------------|
| 1 | Foundation Types | Small |
| 2 | DSL Definition and Loader | Medium |
| 3 | Refactor Workflow/Context | Medium |
| 4 | YAML and Python Definitions | Medium |
| 5 | Integrate with WorkloadManager | Medium |
| 6 | Cleanup and Migration | Small |

**Total:** Large refactoring, recommend incremental delivery with each phase
producing working code.

---

## Appendix: Current vs Target Comparison

### AgentInfo to WorkloadMetadata + WorkloadDefinition

**Current:**
```python
class AgentInfo:
    name: str
    description: str
    file_path: Path | None = None      # Optional
    module: ModuleType | None = None   # Optional
    yaml_document: YamlAgentDocument | None = None  # Optional
```

**Target:**
```python
@dataclass(frozen=True)
class WorkloadMetadata:
    name: str
    description: str
    source_path: Path
    format: Literal["dsl", "yaml", "python"]

class DslWorkloadDefinition(WorkloadDefinition):
    _workflow_class: type[DslAgentWorkflow]  # Required
    _source_map: list[SourceMapping]          # Required
```

### DslAgentInfo to DslWorkloadDefinition

**Current:**
```python
class DslAgentInfo(AgentInfo):
    workflow_class: type[DslAgentWorkflow] | None = None  # Optional!
```

**Target:**
```python
class DslWorkloadDefinition(WorkloadDefinition):
    _workflow_class: type[DslAgentWorkflow]  # Required - no None state
```

### WorkflowContext

**Current:**
```python
def __init__(self, workflow: DslAgentWorkflow | None = None) -> None:
    self._workflow = workflow  # Can be None
```

**Target:**
```python
def __init__(self, workflow: DslAgentWorkflow) -> None:
    self._workflow = workflow  # Always set
```

### DslAgentWorkflow

**Current:**
```python
def __init__(
    self,
    agent_definition: DslStreetRaceAgent | None = None,
    model_factory: ModelFactory | None = None,
    ...
) -> None:
```

**Target:**
```python
def __init__(self) -> None:
    # No deps at construction

def set_dependencies(
    self,
    model_factory: ModelFactory,  # Required
    ...
) -> None:
```
