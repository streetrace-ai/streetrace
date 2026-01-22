# Implementation Todo: Workload Abstraction Refactoring

## Feature Information

- **Feature ID**: 017-dsl
- **Task ID**: workload-abstraction
- **Task Definition**: `docs/tasks/017-dsl/workload-abstraction/task.md`
- **Branch**: feature/017-streetrace-dsl-2

---

## Phase 1: Foundation Types

**Goal:** Introduce new types alongside existing ones without breaking changes.

### 1.1 Create WorkloadMetadata

**File:** `src/streetrace/workloads/metadata.py`

- [ ] Create `metadata.py` file
- [ ] Implement `WorkloadMetadata` dataclass with `frozen=True`
  - [ ] `name: str` field
  - [ ] `description: str` field
  - [ ] `source_path: Path` field
  - [ ] `format: Literal["dsl", "yaml", "python"]` field
- [ ] Add docstring explaining immutability purpose
- [ ] Run `ruff check` on new file

### 1.2 Create WorkloadDefinition ABC

**File:** `src/streetrace/workloads/definition.py`

- [ ] Create `definition.py` file
- [ ] Import `WorkloadMetadata` from `metadata.py`
- [ ] Implement `WorkloadDefinition` abstract base class
  - [ ] `__init__(self, metadata: WorkloadMetadata)` constructor
  - [ ] `metadata` property returning `WorkloadMetadata`
  - [ ] `name` property returning `str` (delegates to metadata)
  - [ ] `@abstractmethod create_workload(...)` with all required parameters
- [ ] Use `TYPE_CHECKING` for forward references to avoid circular imports
- [ ] Add comprehensive docstrings
- [ ] Run `ruff check` and `mypy` on new file

### 1.3 Create DefinitionLoader Protocol

**File:** `src/streetrace/workloads/loader.py`

- [ ] Create `loader.py` file
- [ ] Implement `DefinitionLoader` as `typing.Protocol`
  - [ ] `can_load(self, path: Path) -> bool` method
  - [ ] `load(self, path: Path) -> WorkloadDefinition` method
  - [ ] `discover(self, directory: Path) -> list[Path]` method
- [ ] Add `@runtime_checkable` decorator
- [ ] Document that `load()` must compile/parse immediately
- [ ] Run `ruff check` and `mypy` on new file

### 1.4 Update Package Exports (Partial)

**File:** `src/streetrace/workloads/__init__.py`

- [ ] Add import for `WorkloadMetadata`
- [ ] Add import for `WorkloadDefinition`
- [ ] Add import for `DefinitionLoader`
- [ ] Update `__all__` list
- [ ] Run `ruff check` on file

### 1.5 Tests for Foundation Types

**File:** `tests/workloads/test_metadata.py`

- [ ] Test `WorkloadMetadata` is frozen (immutable)
- [ ] Test `WorkloadMetadata` equality based on fields
- [ ] Test `WorkloadMetadata` with all format values

**File:** `tests/workloads/test_definition.py`

- [ ] Test `WorkloadDefinition` cannot be instantiated directly (ABC)
- [ ] Test concrete subclass can be created
- [ ] Test `metadata` and `name` properties work correctly

**File:** `tests/workloads/test_loader_protocol.py`

- [ ] Test `DefinitionLoader` protocol compliance checking
- [ ] Test classes implementing protocol pass `isinstance` check

### 1.6 Phase 1 Verification

- [ ] Run `make test` - all tests pass
- [ ] Run `make lint` - no errors
- [ ] Run `make typed` - no type errors
- [ ] No changes to existing functionality

---

## Phase 2: DSL Definition and Loader

**Goal:** Consolidate DSL loading into single implementation with compile-on-load.

### 2.1 Create DslWorkloadDefinition

**File:** `src/streetrace/workloads/dsl_definition.py`

- [ ] Create `dsl_definition.py` file
- [ ] Import dependencies:
  - [ ] `DslAgentWorkflow` from `streetrace.dsl.runtime.workflow`
  - [ ] `SourceMapping` from `streetrace.dsl.sourcemap`
  - [ ] `WorkloadDefinition` from `.definition`
  - [ ] `WorkloadMetadata` from `.metadata`
- [ ] Implement `DslWorkloadDefinition` class extending `WorkloadDefinition`
  - [ ] `__init__` with REQUIRED parameters:
    - [ ] `metadata: WorkloadMetadata`
    - [ ] `workflow_class: type[DslAgentWorkflow]`
    - [ ] `source_map: list[SourceMapping]`
  - [ ] `workflow_class` property (read-only)
  - [ ] `source_map` property (read-only)
  - [ ] `create_workload()` implementation returning `DslWorkload`
- [ ] Add docstring noting this is created ONLY after successful compilation
- [ ] Run `ruff check` and `mypy`

### 2.2 Create DslDefinitionLoader

**File:** `src/streetrace/workloads/dsl_loader.py`

- [ ] Create `dsl_loader.py` file
- [ ] Import dependencies:
  - [ ] `compile_dsl` from `streetrace.dsl.compiler`
  - [ ] `DslAgentWorkflow` from `streetrace.dsl.runtime.workflow`
  - [ ] `DslWorkloadDefinition` from `.dsl_definition`
  - [ ] `WorkloadMetadata` from `.metadata`
- [ ] Implement `DslDefinitionLoader` class
  - [ ] `can_load(self, path: Path) -> bool` - check `.sr` extension
  - [ ] `load(self, path: Path) -> DslWorkloadDefinition`:
    - [ ] Read source file
    - [ ] Call `compile_dsl()` to get bytecode and source_map
    - [ ] Execute bytecode in namespace
    - [ ] Find workflow class using `_find_workflow_class()`
    - [ ] Extract metadata using helper methods
    - [ ] Return complete `DslWorkloadDefinition`
  - [ ] `discover(self, directory: Path) -> list[Path]` - glob for `*.sr`
  - [ ] `_find_workflow_class()` helper - search namespace for DslAgentWorkflow subclass
  - [ ] `_extract_name()` helper - get name from class or filename
  - [ ] `_extract_description()` helper - get description from class or default
- [ ] Add security comment for bytecode execution (noqa: S102)
- [ ] Run `ruff check` and `mypy`

### 2.3 Create DslWorkload Runtime

**File:** `src/streetrace/workloads/dsl_workload.py`

- [ ] Create `dsl_workload.py` file
- [ ] Import dependencies with TYPE_CHECKING guards
- [ ] Implement `DslWorkload` class
  - [ ] `__init__` with ALL REQUIRED parameters:
    - [ ] `definition: DslWorkloadDefinition`
    - [ ] `model_factory: ModelFactory`
    - [ ] `tool_provider: ToolProvider`
    - [ ] `system_context: SystemContext`
    - [ ] `session_service: BaseSessionService`
  - [ ] In `__init__`:
    - [ ] Store all dependencies
    - [ ] Create workflow instance: `definition.workflow_class()`
    - [ ] Call `_workflow.set_dependencies(...)` (added in Phase 3)
    - [ ] Create context: `WorkflowContext(workflow=self._workflow)`
  - [ ] `run_async()` method implementing Workload protocol
  - [ ] `close()` method for cleanup
- [ ] Ensure no Optional types for required fields
- [ ] Run `ruff check` and `mypy`

### 2.4 Update Package Exports

**File:** `src/streetrace/workloads/__init__.py`

- [ ] Add import for `DslWorkloadDefinition`
- [ ] Add import for `DslDefinitionLoader`
- [ ] Add import for `DslWorkload`
- [ ] Update `__all__` list

### 2.5 Tests for DSL Components

**File:** `tests/workloads/test_dsl_definition.py`

- [ ] Test `DslWorkloadDefinition` requires all parameters
- [ ] Test `workflow_class` property returns correct type
- [ ] Test `source_map` property returns correct list
- [ ] Test `create_workload()` returns `DslWorkload`

**File:** `tests/workloads/test_dsl_loader.py`

- [ ] Test `can_load()` returns True for `.sr` files
- [ ] Test `can_load()` returns False for other extensions
- [ ] Test `load()` compiles valid DSL file
- [ ] Test `load()` raises `FileNotFoundError` for missing file
- [ ] Test `load()` raises `DslSyntaxError` for invalid syntax
- [ ] Test `load()` raises `ValueError` for missing workflow class
- [ ] Test `discover()` finds all `.sr` files recursively
- [ ] Test metadata extraction from compiled class

**File:** `tests/workloads/test_dsl_workload.py`

- [ ] Test `DslWorkload` requires all constructor parameters
- [ ] Test workflow instance created during init
- [ ] Test context created with workflow reference
- [ ] Test `run_async()` delegates to workflow
- [ ] Test `close()` cleans up resources

### 2.6 Phase 2 Verification

- [ ] Run `make test` - all tests pass
- [ ] Run `make lint` - no errors
- [ ] Run `make typed` - no type errors
- [ ] DSL files compile during `load()`, not deferred

---

## Phase 3: Refactor DslAgentWorkflow and WorkflowContext

**Goal:** Remove optional parameters, make workflow required in context.

### 3.1 Add set_dependencies() to DslAgentWorkflow

**File:** `src/streetrace/dsl/runtime/workflow.py`

- [ ] Modify `DslAgentWorkflow.__init__()`:
  - [ ] Remove all optional parameters from signature
  - [ ] Initialize `_model_factory = None`
  - [ ] Initialize `_tool_provider = None`
  - [ ] Initialize `_system_context = None`
  - [ ] Initialize `_session_service = None`
  - [ ] Initialize `_initialized = False`
- [ ] Add `set_dependencies()` method:
  - [ ] All parameters REQUIRED (no Optional types)
  - [ ] Set `_initialized = True` after setting deps
- [ ] Add `_ensure_initialized()` helper:
  - [ ] Raise `RuntimeError` if `not self._initialized`
- [ ] Update all methods that need deps to call `_ensure_initialized()`:
  - [ ] `run_async()`
  - [ ] `_create_agent()`
  - [ ] `run_agent()`
  - [ ] `run_flow()`
- [ ] Run `ruff check` and `mypy`

### 3.2 Make workflow Required in WorkflowContext

**File:** `src/streetrace/dsl/runtime/context.py`

- [ ] Modify `WorkflowContext.__init__()`:
  - [ ] Change `workflow: DslAgentWorkflow | None = None` to `workflow: DslAgentWorkflow`
  - [ ] Remove default value
- [ ] Remove fallback methods:
  - [ ] Delete `_run_agent_fallback()`
  - [ ] Delete `_run_flow_fallback()`
- [ ] Simplify `run_agent()`:
  - [ ] Remove `if self._workflow:` check
  - [ ] Always delegate to `self._workflow.run_agent()`
- [ ] Simplify `run_flow()`:
  - [ ] Remove `if self._workflow:` check
  - [ ] Always delegate to `self._workflow.run_flow()`
- [ ] Update type hints to remove `| None`
- [ ] Run `ruff check` and `mypy`

### 3.3 Create PromptResolutionContext

**File:** `src/streetrace/dsl/runtime/prompt_context.py`

- [ ] Create `prompt_context.py` file
- [ ] Implement `PromptResolutionContext` class:
  - [ ] `__init__(self)` - no parameters required
  - [ ] `vars: dict[str, object]` attribute
  - [ ] `message: str` attribute
  - [ ] Only prompt-related methods (no `run_agent`/`run_flow`)
- [ ] Add docstring explaining this is for prompt evaluation only
- [ ] Run `ruff check` and `mypy`

### 3.4 Update DslStreetRaceAgent to Use PromptResolutionContext

**File:** `src/streetrace/agents/dsl_agent_loader.py`

- [ ] Import `PromptResolutionContext`
- [ ] Update `_resolve_instruction()` method:
  - [ ] Replace `WorkflowContext()` with `PromptResolutionContext()`
- [ ] Update any other places using `WorkflowContext()` without workflow
- [ ] Run `ruff check` and `mypy`

### 3.5 Update DslWorkload to Use set_dependencies()

**File:** `src/streetrace/workloads/dsl_workload.py`

- [ ] Update `__init__()`:
  - [ ] After creating workflow instance, call `set_dependencies()`
  - [ ] Pass all required dependencies

### 3.6 Tests for Refactored Components

**File:** `tests/dsl/runtime/test_workflow_dependencies.py`

- [ ] Test `DslAgentWorkflow()` can be instantiated without args
- [ ] Test `set_dependencies()` requires all parameters
- [ ] Test `_ensure_initialized()` raises before `set_dependencies()`
- [ ] Test methods work after `set_dependencies()` called

**File:** `tests/dsl/runtime/test_context_required_workflow.py`

- [ ] Test `WorkflowContext` requires workflow parameter
- [ ] Test `WorkflowContext(workflow=None)` raises TypeError
- [ ] Test `run_agent()` delegates to workflow
- [ ] Test `run_flow()` delegates to workflow

**File:** `tests/dsl/runtime/test_prompt_context.py`

- [ ] Test `PromptResolutionContext` can be created without args
- [ ] Test `vars` and `message` attributes work
- [ ] Test no `run_agent`/`run_flow` methods exist

### 3.7 Update Existing Tests

- [ ] Find all tests creating `WorkflowContext()` without workflow
- [ ] Update to provide mock workflow or use `PromptResolutionContext`
- [ ] Find all tests creating `DslAgentWorkflow` with deps in constructor
- [ ] Update to use `set_dependencies()` pattern

### 3.8 Phase 3 Verification

- [ ] Run `make test` - all tests pass
- [ ] Run `make lint` - no errors
- [ ] Run `make typed` - no type errors
- [ ] No fallback code paths in WorkflowContext
- [ ] All DslAgentWorkflow deps set via `set_dependencies()`

---

## Phase 4: YAML and Python Definitions

**Goal:** Create definition types for YAML and Python workloads.

### 4.1 Create YamlWorkloadDefinition

**File:** `src/streetrace/workloads/yaml_definition.py`

- [ ] Create `yaml_definition.py` file
- [ ] Import `YamlAgentSpec` from `streetrace.agents.yaml_models`
- [ ] Implement `YamlWorkloadDefinition` class:
  - [ ] `__init__` with REQUIRED parameters:
    - [ ] `metadata: WorkloadMetadata`
    - [ ] `spec: YamlAgentSpec`
  - [ ] `spec` property (read-only)
  - [ ] `create_workload()` returning `BasicWorkload`
- [ ] Run `ruff check` and `mypy`

### 4.2 Create PythonWorkloadDefinition

**File:** `src/streetrace/workloads/python_definition.py`

- [ ] Create `python_definition.py` file
- [ ] Import `StreetRaceAgent` from `streetrace.agents.street_race_agent`
- [ ] Implement `PythonWorkloadDefinition` class:
  - [ ] `__init__` with REQUIRED parameters:
    - [ ] `metadata: WorkloadMetadata`
    - [ ] `agent_class: type[StreetRaceAgent]`
    - [ ] `module: ModuleType`
  - [ ] `agent_class` property (read-only)
  - [ ] `module` property (read-only)
  - [ ] `create_workload()` returning `BasicWorkload`
- [ ] Run `ruff check` and `mypy`

### 4.3 Create YamlDefinitionLoader

**File:** `src/streetrace/workloads/yaml_loader.py`

- [ ] Create `yaml_loader.py` file
- [ ] Implement `YamlDefinitionLoader` class:
  - [ ] `can_load()` - check `.yaml` or `.yml` extension
  - [ ] `load()` - parse YAML, create `YamlWorkloadDefinition`
  - [ ] `discover()` - glob for `*.yaml` and `*.yml`
- [ ] Reuse parsing logic from `yaml_agent_loader.py`
- [ ] Run `ruff check` and `mypy`

### 4.4 Create PythonDefinitionLoader

**File:** `src/streetrace/workloads/python_loader.py`

- [ ] Create `python_loader.py` file
- [ ] Implement `PythonDefinitionLoader` class:
  - [ ] `can_load()` - check for agent directory structure
  - [ ] `load()` - import module, create `PythonWorkloadDefinition`
  - [ ] `discover()` - find agent directories
- [ ] Reuse validation logic from `py_agent_loader.py`
- [ ] Run `ruff check` and `mypy`

### 4.5 Update BasicWorkload

**File:** `src/streetrace/workloads/basic_workload.py`

- [ ] Update `__init__` signature:
  - [ ] Accept `definition: YamlWorkloadDefinition | PythonWorkloadDefinition`
  - [ ] Keep all other params REQUIRED
- [ ] Update internal logic to use definition
- [ ] Ensure backward compatibility with existing usage
- [ ] Run `ruff check` and `mypy`

### 4.6 Update Package Exports

**File:** `src/streetrace/workloads/__init__.py`

- [ ] Add import for `YamlWorkloadDefinition`
- [ ] Add import for `PythonWorkloadDefinition`
- [ ] Add import for `YamlDefinitionLoader`
- [ ] Add import for `PythonDefinitionLoader`
- [ ] Update `__all__` list

### 4.7 Tests for YAML/Python Components

**File:** `tests/workloads/test_yaml_definition.py`

- [ ] Test `YamlWorkloadDefinition` requires all parameters
- [ ] Test `spec` property returns correct type
- [ ] Test `create_workload()` returns `BasicWorkload`

**File:** `tests/workloads/test_python_definition.py`

- [ ] Test `PythonWorkloadDefinition` requires all parameters
- [ ] Test `agent_class` property returns correct type
- [ ] Test `create_workload()` returns `BasicWorkload`

**File:** `tests/workloads/test_yaml_loader.py`

- [ ] Test `can_load()` for YAML files
- [ ] Test `load()` parses valid YAML
- [ ] Test `load()` raises for invalid YAML
- [ ] Test `discover()` finds YAML files

**File:** `tests/workloads/test_python_loader.py`

- [ ] Test `can_load()` for Python agent directories
- [ ] Test `load()` imports valid modules
- [ ] Test `load()` raises for invalid modules
- [ ] Test `discover()` finds agent directories

### 4.8 Phase 4 Verification

- [ ] Run `make test` - all tests pass
- [ ] Run `make lint` - no errors
- [ ] Run `make typed` - no type errors
- [ ] All three formats have Definition and Loader types

---

## Phase 5: Integrate with WorkloadManager

**Goal:** Update WorkloadManager to use new unified types.

### 5.1 Update WorkloadManager Initialization

**File:** `src/streetrace/workloads/manager.py`

- [ ] Replace format_loaders dict:
  - [ ] Change from `dict[str, AgentLoader]` to `dict[str, DefinitionLoader]`
  - [ ] Initialize with:
    - [ ] `".sr": DslDefinitionLoader()`
    - [ ] `".yaml": YamlDefinitionLoader()`
    - [ ] `".yml": YamlDefinitionLoader()`
- [ ] Replace `_discovery_cache` with `_definitions`:
  - [ ] Change type from `dict[str, tuple[...]]` to `dict[str, WorkloadDefinition]`
- [ ] Update imports for new loader types

### 5.2 Update discover() Method

**File:** `src/streetrace/workloads/manager.py`

- [ ] Rewrite `discover()` method:
  - [ ] Find all workload files using loaders
  - [ ] For each file, call `loader.load()` (compiles immediately)
  - [ ] Catch and log compilation errors
  - [ ] Store successful definitions in `_definitions`
  - [ ] Return `list[WorkloadDefinition]`
- [ ] Remove `_extract_agent_info` style logic
- [ ] Remove deferred compilation logic

### 5.3 Update create_workload() Method

**File:** `src/streetrace/workloads/manager.py`

- [ ] Rewrite `create_workload()` method:
  - [ ] Look up definition in `_definitions`
  - [ ] If not found, call `discover()` and retry
  - [ ] Call `definition.create_workload(...)` with all deps
  - [ ] Return the created `Workload`
- [ ] Remove `_is_dsl_definition()` check
- [ ] Remove `_create_dsl_workload()` method
- [ ] Remove `_create_basic_workload()` method
- [ ] Definition handles format-specific creation

### 5.4 Remove Deprecated Methods

**File:** `src/streetrace/workloads/manager.py`

- [ ] Remove or deprecate `_load_definition()` if no longer needed
- [ ] Remove or deprecate `_load_by_name()` if no longer needed
- [ ] Remove `_is_dsl_definition()` helper
- [ ] Remove `_create_dsl_workload()` helper
- [ ] Remove `_create_basic_workload()` helper
- [ ] Clean up unused imports

### 5.5 Update Supervisor Integration

**File:** `src/streetrace/workflow/supervisor.py`

- [ ] Verify `create_workload()` call still works
- [ ] Update any type hints if needed
- [ ] Test full flow from Supervisor to Workload

### 5.6 Tests for WorkloadManager

**File:** `tests/workloads/test_manager_unified.py`

- [ ] Test `discover()` compiles all workload types
- [ ] Test `discover()` handles compilation errors gracefully
- [ ] Test `create_workload()` returns correct Workload type for DSL
- [ ] Test `create_workload()` returns correct Workload type for YAML
- [ ] Test `create_workload()` returns correct Workload type for Python
- [ ] Test `create_workload()` raises for unknown name
- [ ] Test definitions are cached after discovery

### 5.7 Integration Tests

**File:** `tests/integration/test_workload_pipeline.py`

- [ ] Test full pipeline: .sr file -> discover -> create_workload -> run_async
- [ ] Test full pipeline: .yaml file -> discover -> create_workload -> run_async
- [ ] Test invalid DSL rejected at discovery time
- [ ] Test WorkflowContext always has workflow reference

### 5.8 Phase 5 Verification

- [ ] Run `make test` - all tests pass
- [ ] Run `make lint` - no errors
- [ ] Run `make typed` - no type errors
- [ ] WorkloadManager uses unified Definition/Loader types
- [ ] No deferred compilation anywhere

---

## Phase 6: Cleanup and Migration

**Goal:** Remove deprecated types, update documentation.

### 6.1 Delete Duplicate DslAgentLoader

**File:** `src/streetrace/dsl/loader.py`

- [ ] Delete entire file
- [ ] Update `src/streetrace/dsl/__init__.py`:
  - [ ] Remove `DslAgentLoader` import
  - [ ] Remove from `__all__`
  - [ ] Add comment pointing to new location

### 6.2 Delete Old DSL Agent Types

**File:** `src/streetrace/agents/dsl_agent_loader.py`

- [ ] Delete `DslAgentInfo` class
- [ ] Delete `DslAgentLoader` class
- [ ] Keep `DslStreetRaceAgent` if still needed, or delete if replaced
- [ ] Update file to only contain still-needed code
- [ ] If file becomes empty, delete it

### 6.3 Deprecate AgentInfo and AgentLoader

**File:** `src/streetrace/agents/base_agent_loader.py`

- [ ] Add deprecation warning to `AgentInfo.__init__()`:
  ```python
  warnings.warn(
      "AgentInfo is deprecated, use WorkloadDefinition instead",
      DeprecationWarning,
      stacklevel=2,
  )
  ```
- [ ] Add deprecation warning to `AgentLoader` class
- [ ] Keep for backward compatibility (one release cycle)

### 6.4 Update YAML Agent Loader

**File:** `src/streetrace/agents/yaml_agent_loader.py`

- [ ] Add deprecation warning
- [ ] Optionally delegate to `YamlDefinitionLoader`
- [ ] Or keep as-is with deprecation notice

### 6.5 Update Python Agent Loader

**File:** `src/streetrace/agents/py_agent_loader.py`

- [ ] Add deprecation warning
- [ ] Optionally delegate to `PythonDefinitionLoader`
- [ ] Or keep as-is with deprecation notice

### 6.6 Update vulture_allow.txt

**File:** `vulture_allow.txt`

- [ ] Remove entries for deleted classes
- [ ] Add entries for any new intentionally unused code
- [ ] Run `make unusedcode` to verify

### 6.7 Update Documentation

**File:** `docs/dev/workloads/architecture.md`

- [ ] Document new type hierarchy
- [ ] Document DefinitionLoader protocol
- [ ] Document compile-on-load behavior
- [ ] Add diagrams for new architecture

**File:** `docs/dev/workloads/api-reference.md`

- [ ] Document `WorkloadMetadata`
- [ ] Document `WorkloadDefinition` and subclasses
- [ ] Document `DefinitionLoader` and implementations
- [ ] Document `DslWorkload`

**File:** `docs/user/dsl/getting-started.md`

- [ ] Update any loading examples
- [ ] Remove references to `DslAgentLoader` from `dsl/loader.py`

**File:** `docs/dev/dsl/api-reference.md`

- [ ] Update loader documentation
- [ ] Point to new workloads package

### 6.8 Migration Guide

**File:** `docs/dev/workloads/migration-guide.md`

- [ ] Create migration guide for external users
- [ ] Document old -> new type mappings
- [ ] Provide code examples for migration
- [ ] Note deprecation timeline

### 6.9 Update Tests

- [ ] Delete tests for removed classes:
  - [ ] `tests/dsl/test_loader.py` (if testing old DslAgentLoader)
- [ ] Update test imports throughout
- [ ] Remove any tests using deprecated patterns
- [ ] Ensure all new code has test coverage

### 6.10 Final Cleanup

- [ ] Run `make check` - all checks pass
- [ ] Run `make coverage` - verify coverage > 90%
- [ ] Review all TODO comments added during refactoring
- [ ] Update COMPONENTS.md if needed
- [ ] Update any remaining documentation references

### 6.11 Phase 6 Verification

- [ ] Run `make check` - all checks pass
- [ ] No duplicate loader implementations
- [ ] No Optional parameters for required fields
- [ ] Consistent "Workload" naming throughout
- [ ] Documentation updated

---

## Final Verification Checklist

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

## Files Summary

### New Files to Create

| File | Phase | Description |
|------|-------|-------------|
| `src/streetrace/workloads/metadata.py` | 1 | WorkloadMetadata dataclass |
| `src/streetrace/workloads/definition.py` | 1 | WorkloadDefinition ABC |
| `src/streetrace/workloads/loader.py` | 1 | DefinitionLoader protocol |
| `src/streetrace/workloads/dsl_definition.py` | 2 | DslWorkloadDefinition |
| `src/streetrace/workloads/dsl_loader.py` | 2 | DslDefinitionLoader |
| `src/streetrace/workloads/dsl_workload.py` | 2 | DslWorkload runtime |
| `src/streetrace/dsl/runtime/prompt_context.py` | 3 | PromptResolutionContext |
| `src/streetrace/workloads/yaml_definition.py` | 4 | YamlWorkloadDefinition |
| `src/streetrace/workloads/python_definition.py` | 4 | PythonWorkloadDefinition |
| `src/streetrace/workloads/yaml_loader.py` | 4 | YamlDefinitionLoader |
| `src/streetrace/workloads/python_loader.py` | 4 | PythonDefinitionLoader |

### Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `src/streetrace/workloads/__init__.py` | 1-5 | Add exports |
| `src/streetrace/dsl/runtime/workflow.py` | 3 | Add set_dependencies() |
| `src/streetrace/dsl/runtime/context.py` | 3 | Make workflow required |
| `src/streetrace/agents/dsl_agent_loader.py` | 3 | Use PromptResolutionContext |
| `src/streetrace/workloads/basic_workload.py` | 4 | Accept definition types |
| `src/streetrace/workloads/manager.py` | 5 | Use unified loaders |

### Files to Delete

| File | Phase | Reason |
|------|-------|--------|
| `src/streetrace/dsl/loader.py` | 6 | Duplicate DslAgentLoader |
| `src/streetrace/agents/dsl_agent_loader.py` | 6 | Consolidated (partial) |

### Files to Deprecate

| File | Phase | Deprecation |
|------|-------|-------------|
| `src/streetrace/agents/base_agent_loader.py` | 6 | AgentInfo, AgentLoader |
| `src/streetrace/agents/yaml_agent_loader.py` | 6 | YamlAgentLoader |
| `src/streetrace/agents/py_agent_loader.py` | 6 | PythonAgentLoader |
