# Implementation Plan: Definition Loader Migration

## Phase 1: Extend DefinitionLoader Protocol

- [x] Understand the scope
- [x] Create unit tests for the extended DefinitionLoader protocol
- [x] Update `loader.py` protocol to support URL loading:
  - Add `load_from_url(url: str) -> WorkloadDefinition` method
  - Add `load_from_source(identifier: str, base_path: Path | None = None) -> WorkloadDefinition` unified method
- [x] Run tests and ensure they pass
- [x] Analyze test coverage gaps

## Phase 2: Add HTTP Support to YamlDefinitionLoader

- [x] Understand the scope - YamlAgentLoader's HTTP loading with recursive refs
- [x] Create unit tests for YAML HTTP loading
- [x] Update `YamlDefinitionLoader` to:
  - Accept `SourceResolver` as dependency (or create one internally)
  - Implement `load_from_url()` using `SourceResolver._resolve_http()`
  - Implement `load_from_source()` unified method
  - Preserve recursive `$ref` resolution
- [x] Run tests and ensure they pass
- [x] Analyze test coverage gaps
- [x] Add `load_from_url()` and `load_from_source()` to DslDefinitionLoader (rejects HTTP for security)
- [x] Add `load_from_url()` and `load_from_source()` to PythonDefinitionLoader (rejects HTTP for security)

## Phase 3: Move Agent Creation Logic to DslWorkload

- [x] Understand the scope - DslStreetRaceAgent's agent creation
- [x] Create unit tests for DSL agent creation in DslWorkload
- [x] Create `DslAgentFactory` helper class with the agent creation logic:
  - `_resolve_instruction()` - Get instruction from prompts
  - `_resolve_model()` - Get model from models dict
  - `_resolve_tools()` - Get tools from tool definitions
  - `_resolve_sub_agents()` - Create sub-agents for delegate pattern
  - `_resolve_agent_tools()` - Create agent tools for use pattern
  - `_create_agent_from_def()` - Main agent creation method
  - `close()` - Cleanup agent resources
- [x] Update `DslWorkload` to use `DslAgentFactory` instead of `DslStreetRaceAgent`
- [x] Update `DslAgentWorkflow` to use `DslAgentFactory` instead of `agent_definition`
- [x] Run tests and ensure they pass
- [x] Analyze test coverage gaps - 32 tests in `tests/workloads/test_dsl_agent_factory.py`

## Phase 4: Migrate WorkloadManager to Definition Loaders Only

- [x] Understand the scope - current WorkloadManager dual system
- [x] Create unit tests for unified WorkloadManager (52 tests in `tests/workloads/test_manager_unified.py`)
- [x] Update `WorkloadManager` to:
  - [x] Remove `format_loaders` dict (old AgentLoader instances)
  - [x] Remove `_discovery_cache` for AgentInfo
  - [x] Update `_definition_loaders` to include PythonDefinitionLoader
  - [x] Update `create_workload()` to use `_definition_loaders` only
  - [x] Replace `discover()` with `discover_definitions()` returning `list[WorkloadDefinition]`
  - [x] Implement new loading methods using definition loaders:
    - `_load_from_url()` - YAML only, rejects DSL/Python for security
    - `_load_from_path()` - uses appropriate loader by extension
    - `_load_by_name()` - discovers and loads by name
  - [x] Remove `_is_dsl_definition()`, `_create_dsl_workload()`, `_create_basic_workload()` routing
  - [x] Remove `create_agent()` context manager (backward compat method)
  - [x] Update `_set_workload_telemetry_attributes()` to use WorkloadDefinition
- [x] Run tests and ensure they pass (1743 tests pass)
- [x] Update dependent files:
  - [x] `src/streetrace/list_agents.py` - use WorkloadDefinitionList
  - [x] `src/streetrace/tools/definitions/list_agents.py` - use discover_definitions()
  - [x] `tests/unit/workflow/conftest.py` - use discover_definitions()
  - [x] `tests/unit/agents/test_system_context_agent.py` - use new API
  - [x] `tests/dsl/test_dsl_agent_loader.py` - use new API
- [x] Remove old test files:
  - [x] `tests/workloads/test_manager.py` (replaced by test_manager_unified.py)
  - [x] `tests/workloads/test_dsl_workload.py` (old API tests)
  - [x] `tests/unit/agents/test_workload_manager.py` (old API tests)
- [x] Run `make check` to ensure all quality checks pass

## Phase 5: Remove Deprecated Agent Loader Code

- [x] Understand the scope - files to remove
- [x] Update imports across codebase:
  - [x] Find all imports of deprecated types
  - [x] Update to use new types from `streetrace.workloads`
- [x] Refactor deprecated files:
  - [x] `src/streetrace/agents/base_agent_loader.py` - kept AgentValidationError and AgentCycleError only
  - [x] `src/streetrace/agents/dsl_agent_loader.py` - DELETED (moved compiled_exec to dsl_loader.py)
  - [x] `src/streetrace/agents/yaml_agent_loader.py` - kept helper functions, removed YamlAgentLoader class
  - [x] `src/streetrace/agents/py_agent_loader.py` - kept helper functions, removed PythonAgentLoader class
- [x] Update test files:
  - [x] `tests/dsl/test_agent_loader_instruction.py` - use DslDefinitionLoader
  - [x] `tests/dsl/test_agent_loader_model.py` - use DslDefinitionLoader
  - [x] `tests/dsl/test_agent_loader_tools.py` - use DslDefinitionLoader
  - [x] `tests/unit/agents/test_resolver.py` - use AgentInfoStub instead of AgentInfo
  - [x] `tests/unit/agents/test_yaml_loader.py` - use YamlDefinitionLoader
  - [x] `tests/unit/agents/test_dsl_agent_adk_integration.py` - use DslAgentFactory
  - [x] `tests/unit/agents/agent_loader/test_agent_loader_filesystem.py` - use PythonDefinitionLoader
  - [x] `tests/unit/agents/agent_loader/test_non_directory_item.py` - use YamlDefinitionLoader
- [x] Run tests and ensure they pass (1745 tests pass, 2 skipped)
- [x] Run `make check` to ensure all quality checks pass

## Phase 6: Integration Testing & Validation

- [x] Run integration tests for all agent types
- [x] Create integration test `tests/integration/test_definition_loader_migration.py`:
  - 20 tests verifying WorkloadManager discovery, path loading, name loading, and workload creation
  - Tests for YAML agents (generic.yml -> GenericCodingAssistant)
  - Tests for DSL agents (reviewer.sr -> reviewer)
  - Tests for Python agents (coder/ -> Streetrace_Coding_Agent)
  - Tests for metadata consistency across all formats
  - Tests for location-first priority (first location wins for duplicate names)
  - Tests for DefinitionLoader protocol compliance
- [x] Verify all agent formats work correctly (51 integration tests pass)
- [x] Run `make check` and fix all issues (1765 tests pass, 2 skipped)

## Phase 7: Documentation

- [x] Update developer docs in `docs/dev/workloads/`
  - Updated `architecture.md` with DslAgentFactory documentation and WorkloadManager details
  - Updated `api-reference.md` with DslAgentFactory API and DefinitionLoader new methods
  - Updated `extension-guide.md` to use DefinitionLoader instead of AgentLoader
- [x] Update user docs in `docs/user/workloads/`
  - User docs already use correct terminology (WorkloadDefinition, DefinitionLoader)
- [x] Update existing docs that reference deprecated types
  - Updated `docs/user/dsl/getting-started.md` to use DslDefinitionLoader
  - Updated `docs/testing/workloads/testing-guide.md` to use DslAgentFactory
- [x] Testing docs already exist in `docs/testing/workloads/`
  - `scenarios.md` and `environment-setup.md` are already up-to-date
