# Implementation Todo: Workload Abstraction Refactoring

## Feature Information

- **Feature ID**: 017-dsl
- **Task ID**: workload-abstraction
- **Task Definition**: `docs/tasks/017-dsl/workload-abstraction/task.md`
- **Branch**: feature/017-streetrace-dsl-2

---

## Phase 1: Foundation Types [COMPLETED]

**Goal:** Introduce new types alongside existing ones without breaking changes.

### 1.1 Create WorkloadMetadata

**File:** `src/streetrace/workloads/metadata.py`

- [x] Create `metadata.py` file
- [x] Implement `WorkloadMetadata` dataclass with `frozen=True`
  - [x] `name: str` field
  - [x] `description: str` field
  - [x] `source_path: Path` field
  - [x] `format: Literal["dsl", "yaml", "python"]` field
- [x] Add docstring explaining immutability purpose
- [x] Run `ruff check` on new file

### 1.2 Create WorkloadDefinition ABC

**File:** `src/streetrace/workloads/definition.py`

- [x] Create `definition.py` file
- [x] Import `WorkloadMetadata` from `metadata.py`
- [x] Implement `WorkloadDefinition` abstract base class
  - [x] `__init__(self, metadata: WorkloadMetadata)` constructor
  - [x] `metadata` property returning `WorkloadMetadata`
  - [x] `name` property returning `str` (delegates to metadata)
  - [x] `@abstractmethod create_workload(...)` with all required parameters
- [x] Use `TYPE_CHECKING` for forward references to avoid circular imports
- [x] Add comprehensive docstrings
- [x] Run `ruff check` and `mypy` on new file

### 1.3 Create DefinitionLoader Protocol

**File:** `src/streetrace/workloads/loader.py`

- [x] Create `loader.py` file
- [x] Implement `DefinitionLoader` as `typing.Protocol`
  - [x] `can_load(self, path: Path) -> bool` method
  - [x] `load(self, path: Path) -> WorkloadDefinition` method
  - [x] `discover(self, directory: Path) -> list[Path]` method
- [x] Add `@runtime_checkable` decorator
- [x] Document that `load()` must compile/parse immediately
- [x] Run `ruff check` and `mypy` on new file

### 1.4 Update Package Exports (Partial)

**File:** `src/streetrace/workloads/__init__.py`

- [x] Add import for `WorkloadMetadata`
- [x] Add import for `WorkloadDefinition`
- [x] Add import for `DefinitionLoader`
- [x] Update `__all__` list
- [x] Run `ruff check` on file

### 1.5 Tests for Foundation Types

**File:** `tests/workloads/test_metadata.py`

- [x] Test `WorkloadMetadata` is frozen (immutable)
- [x] Test `WorkloadMetadata` equality based on fields
- [x] Test `WorkloadMetadata` with all format values

**File:** `tests/workloads/test_definition.py`

- [x] Test `WorkloadDefinition` cannot be instantiated directly (ABC)
- [x] Test concrete subclass can be created
- [x] Test `metadata` and `name` properties work correctly

**File:** `tests/workloads/test_loader_protocol.py`

- [x] Test `DefinitionLoader` protocol compliance checking
- [x] Test classes implementing protocol pass `isinstance` check

### 1.6 Phase 1 Verification

- [x] Run `make test` - all tests pass
- [x] Run `make lint` - no errors
- [x] Run `make typed` - no type errors
- [x] No changes to existing functionality

---

## Phase 2: DSL Definition and Loader [COMPLETED]

**Goal:** Consolidate DSL loading into single implementation with compile-on-load.

### 2.1 Create DslWorkloadDefinition

**File:** `src/streetrace/workloads/dsl_definition.py`

- [x] Create `dsl_definition.py` file
- [x] Import dependencies:
  - [x] `DslAgentWorkflow` from `streetrace.dsl.runtime.workflow`
  - [x] `SourceMapping` from `streetrace.dsl.sourcemap`
  - [x] `WorkloadDefinition` from `.definition`
  - [x] `WorkloadMetadata` from `.metadata`
- [x] Implement `DslWorkloadDefinition` class extending `WorkloadDefinition`
  - [x] `__init__` with REQUIRED parameters:
    - [x] `metadata: WorkloadMetadata`
    - [x] `workflow_class: type[DslAgentWorkflow]`
    - [x] `source_map: list[SourceMapping]`
  - [x] `workflow_class` property (read-only)
  - [x] `source_map` property (read-only)
  - [x] `create_workload()` implementation returning `DslWorkload`
- [x] Add docstring noting this is created ONLY after successful compilation
- [x] Run `ruff check` and `mypy`

### 2.2 Create DslDefinitionLoader

**File:** `src/streetrace/workloads/dsl_loader.py`

- [x] Create `dsl_loader.py` file
- [x] Import dependencies:
  - [x] `compile_dsl` from `streetrace.dsl.compiler`
  - [x] `DslAgentWorkflow` from `streetrace.dsl.runtime.workflow`
  - [x] `DslWorkloadDefinition` from `.dsl_definition`
  - [x] `WorkloadMetadata` from `.metadata`
- [x] Implement `DslDefinitionLoader` class
  - [x] `can_load(self, path: Path) -> bool` - check `.sr` extension
  - [x] `load(self, path: Path) -> DslWorkloadDefinition`:
    - [x] Read source file
    - [x] Call `compile_dsl()` to get bytecode and source_map
    - [x] Execute bytecode in namespace
    - [x] Find workflow class using `_find_workflow_class()`
    - [x] Extract metadata using helper methods
    - [x] Return complete `DslWorkloadDefinition`
  - [x] `discover(self, directory: Path) -> list[Path]` - glob for `*.sr`
  - [x] `_find_workflow_class()` helper - search namespace for DslAgentWorkflow subclass
  - [x] `_extract_name()` helper - get name from class or filename
  - [x] `_extract_description()` helper - get description from class or default
- [x] Add security comment for bytecode execution (noqa: S102)
- [x] Run `ruff check` and `mypy`

### 2.3 Create DslWorkload Runtime

**File:** `src/streetrace/workloads/dsl_workload.py`

- [x] Create `dsl_workload.py` file
- [x] Import dependencies with TYPE_CHECKING guards
- [x] Implement `DslWorkload` class
  - [x] `__init__` with ALL REQUIRED parameters:
    - [x] `definition: DslWorkloadDefinition`
    - [x] `model_factory: ModelFactory`
    - [x] `tool_provider: ToolProvider`
    - [x] `system_context: SystemContext`
    - [x] `session_service: BaseSessionService`
  - [x] In `__init__`:
    - [x] Store all dependencies
    - [x] Create workflow instance: `definition.workflow_class()`
    - [ ] Call `_workflow.set_dependencies(...)` (deferred to Phase 3)
  - [x] `run_async()` method implementing Workload protocol
  - [x] `close()` method for cleanup
- [x] Ensure no Optional types for required fields
- [x] Run `ruff check` and `mypy`

### 2.4 Update Package Exports

**File:** `src/streetrace/workloads/__init__.py`

- [x] Add import for `DslWorkloadDefinition`
- [x] Add import for `DslDefinitionLoader`
- [x] Add import for `DslWorkload`
- [x] Update `__all__` list

### 2.5 Tests for DSL Components

**File:** `tests/workloads/test_dsl_definition.py`

- [x] Test `DslWorkloadDefinition` requires all parameters
- [x] Test `workflow_class` property returns correct type
- [x] Test `source_map` property returns correct list
- [x] Test `create_workload()` returns `DslWorkload`

**File:** `tests/workloads/test_dsl_loader.py`

- [x] Test `can_load()` returns True for `.sr` files
- [x] Test `can_load()` returns False for other extensions
- [x] Test `load()` compiles valid DSL file
- [x] Test `load()` raises `FileNotFoundError` for missing file
- [x] Test `load()` raises `DslSyntaxError` for invalid syntax
- [x] Test `discover()` finds all `.sr` files recursively
- [x] Test metadata extraction from compiled class

**File:** `tests/workloads/test_dsl_workload_class.py`

- [x] Test `DslWorkload` requires all constructor parameters
- [x] Test workflow instance created during init
- [x] Test `run_async()` delegates to workflow
- [x] Test `close()` cleans up resources

### 2.6 Phase 2 Verification

- [x] Run `make test` - all tests pass (1574 passed)
- [x] Run `make lint` - no errors
- [x] Run `make typed` - no type errors
- [x] DSL files compile during `load()`, not deferred

---

## Phase 3: Refactor DslAgentWorkflow and WorkflowContext [COMPLETED]

**Goal:** Remove optional parameters, make workflow required in context.

### 3.1 Add set_dependencies() to DslAgentWorkflow

**File:** `src/streetrace/dsl/runtime/workflow.py`

- [x] Modify `DslAgentWorkflow.__init__()`:
  - [x] Keep optional parameters for backward compatibility
  - [x] Initialize `_model_factory = None`
  - [x] Initialize `_tool_provider = None`
  - [x] Initialize `_system_context = None`
  - [x] Initialize `_session_service = None`
  - [x] Initialize `_initialized = False` (True if all deps provided in constructor)
- [x] Add `set_dependencies()` method:
  - [x] All parameters REQUIRED (no Optional types)
  - [x] Set `_initialized = True` after setting deps
- [x] Add `_ensure_initialized()` helper:
  - [x] Raise `RuntimeError` if `not self._initialized`
- [x] Update all methods that need deps to call `_ensure_initialized()`:
  - [x] `_create_agent()`
  - [x] `run_agent()`
- [x] Run `ruff check` and `mypy`

### 3.2 Make workflow Required in WorkflowContext

**File:** `src/streetrace/dsl/runtime/context.py`

- [x] Modify `WorkflowContext.__init__()`:
  - [x] Change `workflow: DslAgentWorkflow | None = None` to `workflow: DslAgentWorkflow`
  - [x] Remove default value
- [x] Remove fallback methods:
  - [x] Delete `_run_agent_fallback()`
  - [x] Delete `_resolve_instruction()` (only used by fallback)
  - [x] Delete `_extract_final_response()` (only used by fallback)
- [x] Simplify `run_agent()`:
  - [x] Remove `if self._workflow:` check
  - [x] Always delegate to `self._workflow.run_agent()`
- [x] Add `run_flow()` method:
  - [x] Always delegate to `self._workflow.run_flow()`
- [x] Update type hints to remove `| None`
- [x] Run `ruff check` and `mypy`

### 3.3 Create PromptResolutionContext

**File:** `src/streetrace/dsl/runtime/prompt_context.py`

- [x] Create `prompt_context.py` file
- [x] Implement `PromptResolutionContext` class:
  - [x] `__init__(self)` - no parameters required
  - [x] `vars: dict[str, object]` attribute
  - [x] `message: str` attribute
  - [x] Only prompt-related methods (no `run_agent`/`run_flow`)
- [x] Add docstring explaining this is for prompt evaluation only
- [x] Run `ruff check` and `mypy`

### 3.4 Update DslStreetRaceAgent to Use PromptResolutionContext

**File:** `src/streetrace/agents/dsl_agent_loader.py`

- [x] Import `PromptResolutionContext`
- [x] Update `_resolve_instruction()` method:
  - [x] Replace `WorkflowContext()` with `PromptResolutionContext()`
- [x] Run `ruff check` and `mypy`

### 3.5 Update DslWorkload to Use set_dependencies()

**File:** `src/streetrace/workloads/dsl_workload.py`

- [x] Update `__init__()`:
  - [x] After creating workflow instance, call `set_dependencies()`
  - [x] Pass all required dependencies

### 3.6 Tests for Refactored Components

**File:** `tests/dsl/runtime/test_workflow_dependencies.py`

- [x] Test `DslAgentWorkflow()` can be instantiated without args
- [x] Test `set_dependencies()` requires all parameters
- [x] Test `_ensure_initialized()` raises before `set_dependencies()`
- [x] Test methods work after `set_dependencies()` called
- [x] Test backward compatibility with old constructor signature

**File:** `tests/dsl/runtime/test_context_required_workflow.py`

- [x] Test `WorkflowContext` requires workflow parameter
- [x] Test `run_agent()` delegates to workflow
- [x] Test `run_flow()` delegates to workflow
- [x] Test no fallback methods exist

**File:** `tests/dsl/runtime/test_prompt_context.py`

- [x] Test `PromptResolutionContext` can be created without args
- [x] Test `vars` and `message` attributes work
- [x] Test no `run_agent`/`run_flow` methods exist

### 3.7 Update Existing Tests

- [x] Updated `tests/dsl/test_context_call_llm.py` to provide mock workflow
- [x] Updated `tests/dsl/test_context_methods.py` to provide mock workflow
- [x] Updated `tests/dsl/test_context_run_agent.py` to test delegation
- [x] Updated `tests/dsl/test_flow_execution.py` to use mock workflow
- [x] Updated `tests/dsl/test_guardrails.py` to provide mock workflow
- [x] Updated `tests/dsl/test_workflow_workload.py` for new error types

### 3.8 Phase 3 Verification

- [x] Run `make test` - all tests pass (1607 passed)
- [x] Run `make lint` - no errors
- [x] Run `make typed` - no type errors
- [x] No fallback code paths in WorkflowContext
- [x] DslWorkload calls `set_dependencies()` on workflow

---

## Phase 4: YAML and Python Definitions [COMPLETED]

**Goal:** Create definition types for YAML and Python workloads.

### 4.1 Create YamlWorkloadDefinition

**File:** `src/streetrace/workloads/yaml_definition.py`

- [x] Create `yaml_definition.py` file
- [x] Import `YamlAgentSpec` from `streetrace.agents.yaml_models`
- [x] Implement `YamlWorkloadDefinition` class:
  - [x] `__init__` with REQUIRED parameters:
    - [x] `metadata: WorkloadMetadata`
    - [x] `spec: YamlAgentSpec`
  - [x] `spec` property (read-only)
  - [x] `create_workload()` returning `BasicWorkload`
- [x] Run `ruff check` and `mypy`

### 4.2 Create PythonWorkloadDefinition

**File:** `src/streetrace/workloads/python_definition.py`

- [x] Create `python_definition.py` file
- [x] Import `StreetRaceAgent` from `streetrace.agents.street_race_agent`
- [x] Implement `PythonWorkloadDefinition` class:
  - [x] `__init__` with REQUIRED parameters:
    - [x] `metadata: WorkloadMetadata`
    - [x] `agent_class: type[StreetRaceAgent]`
    - [x] `module: ModuleType`
  - [x] `agent_class` property (read-only)
  - [x] `module` property (read-only)
  - [x] `create_workload()` returning `BasicWorkload`
- [x] Run `ruff check` and `mypy`

### 4.3 Create YamlDefinitionLoader

**File:** `src/streetrace/workloads/yaml_loader.py`

- [x] Create `yaml_loader.py` file
- [x] Implement `YamlDefinitionLoader` class:
  - [x] `can_load()` - check `.yaml` or `.yml` extension
  - [x] `load()` - parse YAML, create `YamlWorkloadDefinition`
  - [x] `discover()` - glob for `*.yaml` and `*.yml`
- [x] Reuse parsing logic from `yaml_agent_loader.py`
- [x] Run `ruff check` and `mypy`

### 4.4 Create PythonDefinitionLoader

**File:** `src/streetrace/workloads/python_loader.py`

- [x] Create `python_loader.py` file
- [x] Implement `PythonDefinitionLoader` class:
  - [x] `can_load()` - check for agent directory structure
  - [x] `load()` - import module, create `PythonWorkloadDefinition`
  - [x] `discover()` - find agent directories
- [x] Reuse validation logic from `py_agent_loader.py`
- [x] Run `ruff check` and `mypy`

### 4.5 Update BasicWorkload

**File:** `src/streetrace/workloads/basic_workload.py`

- [x] BasicWorkload continues to accept `StreetRaceAgent` directly
- [x] YamlWorkloadDefinition and PythonWorkloadDefinition create agents
  and pass them to BasicWorkload via `create_workload()`
- [x] Backward compatibility maintained
- [x] Run `ruff check` and `mypy`

### 4.6 Update Package Exports

**File:** `src/streetrace/workloads/__init__.py`

- [x] Add import for `YamlWorkloadDefinition`
- [x] Add import for `PythonWorkloadDefinition`
- [x] Add import for `YamlDefinitionLoader`
- [x] Add import for `PythonDefinitionLoader`
- [x] Update `__all__` list

### 4.7 Tests for YAML/Python Components

**File:** `tests/workloads/test_yaml_definition.py`

- [x] Test `YamlWorkloadDefinition` requires all parameters
- [x] Test `spec` property returns correct type
- [x] Test `create_workload()` returns `BasicWorkload`

**File:** `tests/workloads/test_python_definition.py`

- [x] Test `PythonWorkloadDefinition` requires all parameters
- [x] Test `agent_class` property returns correct type
- [x] Test `create_workload()` returns `BasicWorkload`

**File:** `tests/workloads/test_yaml_loader.py`

- [x] Test `can_load()` for YAML files
- [x] Test `load()` parses valid YAML
- [x] Test `load()` raises for invalid YAML
- [x] Test `discover()` finds YAML files

**File:** `tests/workloads/test_python_loader.py`

- [x] Test `can_load()` for Python agent directories
- [x] Test `load()` imports valid modules
- [x] Test `load()` raises for invalid modules
- [x] Test `discover()` finds agent directories

### 4.8 Phase 4 Verification

- [x] Run `make test` - all tests pass (1681 passed)
- [x] Run `make lint` - no errors
- [x] Run `make typed` - no type errors
- [x] All three formats have Definition and Loader types

---

## Phase 5: Integrate with WorkloadManager [COMPLETED]

**Goal:** Update WorkloadManager to use new unified types alongside existing methods.

### 5.1 Update WorkloadManager Initialization

**File:** `src/streetrace/workloads/manager.py`

- [x] Add new `_definition_loaders` dict (alongside existing `format_loaders`):
  - [x] `dict[str, DefinitionLoader]` type
  - [x] Initialize with:
    - [x] `".sr": DslDefinitionLoader()`
    - [x] `".yaml": YamlDefinitionLoader()`
    - [x] `".yml": YamlDefinitionLoader()`
- [x] Add new `_definitions` cache (alongside existing `_discovery_cache`):
  - [x] `dict[str, WorkloadDefinition]` type
- [x] Update imports for new loader types
- [x] Add `WorkloadNotFoundError` exception class

### 5.2 Add discover_definitions() Method

**File:** `src/streetrace/workloads/manager.py`

- [x] Add new `discover_definitions()` method (alongside existing `discover()`):
  - [x] Find all workload files using `_find_workload_files()`
  - [x] For each file, call `loader.load()` (compiles immediately)
  - [x] Catch and log compilation errors gracefully
  - [x] Store successful definitions in `_definitions`
  - [x] Return `list[WorkloadDefinition]`
- [x] Note: Existing `discover()` method preserved for backward compatibility

### 5.3 Add create_workload_from_definition() Method

**File:** `src/streetrace/workloads/manager.py`

- [x] Add new `create_workload_from_definition()` method (alongside existing `create_workload()`):
  - [x] Look up definition in `_definitions`
  - [x] If not found, call `discover_definitions()` and retry
  - [x] Call `definition.create_workload(...)` with all deps
  - [x] Return the created `Workload`
  - [x] Raise `WorkloadNotFoundError` for unknown names
- [x] Note: Existing `create_workload()` method preserved for backward compatibility

### 5.4 Add Helper Methods

**File:** `src/streetrace/workloads/manager.py`

- [x] Add `_find_workload_files()` helper:
  - [x] Search through all search locations
  - [x] Use each loader's `discover()` method
  - [x] Return list of unique paths
- [x] Add `_get_definition_loader()` helper:
  - [x] Map file extension to appropriate loader
  - [x] Return None for unknown extensions

### 5.5 Backward Compatibility Preserved

**File:** `src/streetrace/workloads/manager.py`

- [x] Existing `format_loaders` dict kept for old-style loaders
- [x] Existing `discover()` method unchanged
- [x] Existing `create_workload()` context manager unchanged
- [x] Existing `_load_definition()` method unchanged
- [x] Phase 6 will handle migration

### 5.6 Tests for WorkloadManager

**File:** `tests/workloads/test_manager_unified.py`

- [x] Test `discover_definitions()` compiles all workload types
- [x] Test `discover_definitions()` handles compilation errors gracefully
- [x] Test `create_workload_from_definition()` returns correct Workload type for DSL
- [x] Test `create_workload_from_definition()` returns correct Workload type for YAML
- [x] Test `create_workload_from_definition()` raises for unknown name
- [x] Test `create_workload_from_definition()` auto-discovers if not cached
- [x] Test definitions are cached after discovery
- [x] Test existing `discover()` method still works
- [x] Test existing `create_workload()` method still works

### 5.7 Integration Tests

**File:** `tests/integration/test_workload_pipeline.py`

- [x] Test full pipeline: .sr file -> discover_definitions -> create_workload_from_definition
- [x] Test full pipeline: .yaml file -> discover_definitions -> create_workload_from_definition
- [x] Test invalid DSL rejected at discovery time
- [x] Test valid files still load when invalid files exist
- [x] Test DslWorkload has initialized workflow
- [x] Test both DSL and YAML discovered together
- [x] Test correct workload type for each format

### 5.8 Update Package Exports

**File:** `src/streetrace/workloads/__init__.py`

- [x] Add import for `WorkloadNotFoundError`
- [x] Update `__all__` list

### 5.9 Update vulture_allow.txt

**File:** `vulture_allow.txt`

- [x] Add entries for new methods that will be used in Phase 6:
  - [x] `_.create_workload_from_definition`
  - [x] `_.discover_definitions`

### 5.10 Phase 5 Verification

- [x] Run `make test` on workloads tests - 255 tests pass
- [x] Run `make lint` - no errors
- [x] Run `make typed` - no type errors
- [x] Run `make unusedcode` - passes with allowlist entries
- [x] New methods work alongside existing ones
- [x] No breaking changes to existing API

---

## Phase 6: Cleanup and Migration [COMPLETED]

**Goal:** Remove deprecated types, add deprecation warnings, update vulture_allow.txt.

### 6.1 Delete Duplicate DslAgentLoader

**File:** `src/streetrace/dsl/loader.py`

- [x] Delete entire file
- [x] Update `src/streetrace/dsl/__init__.py`:
  - [x] Remove `DslAgentLoader` import
  - [x] Remove from `__all__`
  - [x] Add comment pointing to new location

### 6.2 Add Deprecation Warnings (Instead of Deleting)

**Note:** Rather than deleting the old types, we added deprecation warnings to maintain
backward compatibility for one release cycle. The classes will be removed in a future release.

**File:** `src/streetrace/agents/dsl_agent_loader.py`

- [x] Add deprecation warning to `DslAgentInfo.__init__()`
- [x] Add deprecation warning to `DslAgentLoader.__init__()`
- [x] Keep `DslStreetRaceAgent` (still used by WorkloadManager for agent creation)

### 6.3 Deprecate AgentInfo and AgentLoader

**File:** `src/streetrace/agents/base_agent_loader.py`

- [x] Add deprecation warning to `AgentInfo.__init__()`
- [x] Add deprecation warning to `AgentLoader.__init_subclass__()`
- [x] Keep for backward compatibility (one release cycle)

### 6.4 Update YAML Agent Loader

**File:** `src/streetrace/agents/yaml_agent_loader.py`

- [x] Add deprecation warning to `YamlAgentLoader.__init__()`
- [x] Keep as-is with deprecation notice (backward compatibility)

### 6.5 Update Python Agent Loader

**File:** `src/streetrace/agents/py_agent_loader.py`

- [x] Add deprecation warning to `PythonAgentLoader.__init__()`
- [x] Keep as-is with deprecation notice (backward compatibility)

### 6.6 Update vulture_allow.txt

**File:** `vulture_allow.txt`

- [x] Remove entries for deleted `dsl/loader.py` classes
- [x] Add entry for `DslDefinitionLoader.can_load` method
- [x] Run `make unusedcode` - passes

### 6.7 Update Tests

- [x] Update `tests/dsl/test_loader.py` to use new `DslDefinitionLoader`
  - Tests now use `streetrace.workloads.DslDefinitionLoader`
  - Tests verify definition properties (metadata, workflow_class)
- [x] All tests pass (1718 passed)

### 6.8 Phase 6 Verification

- [x] Run `make check` - all checks pass
  - [x] Tests: 1718 passed
  - [x] Linting: passes
  - [x] Type checking: passes
  - [x] Vulture: passes
- [x] No duplicate loader implementations (dsl/loader.py deleted)
- [x] Deprecation warnings added to all old types
- [x] Backward compatibility maintained

### 6.9 Documentation Updates (Deferred)

**Note:** Documentation updates are deferred to a separate task as they are not
blocking for the core functionality. The following can be addressed in a follow-up:

- [ ] Update `docs/dev/dsl/api-reference.md` to point to new workloads package
- [ ] Update `docs/user/dsl/getting-started.md` to remove old loader references
- [ ] Create migration guide for external users

---

## Final Verification Checklist

### Functional Requirements

- [x] All workload types (DSL, YAML, Python) load through unified pipeline
- [x] DSL files are compiled during discovery, not deferred
- [x] Invalid DSL files are rejected immediately with clear errors
- [x] WorkflowContext always has a workflow reference
- [x] No Optional parameters for semantically required fields
- [x] Single DslDefinitionLoader implementation (no duplicates)

### Non-Functional Requirements

- [x] No breaking changes to DSL syntax
- [x] No breaking changes to YAML agent format
- [x] No breaking changes to Python agent interface
- [x] All existing tests pass (1718 passed)
- [x] Test coverage maintained
- [x] `make check` passes

### Code Quality

- [x] Consistent "Workload" naming throughout
- [x] No runtime type checks that should be compile-time
- [x] Clear separation: Definition (compiled) vs Workload (running)
- [x] Immutable WorkloadMetadata and WorkloadDefinition

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
