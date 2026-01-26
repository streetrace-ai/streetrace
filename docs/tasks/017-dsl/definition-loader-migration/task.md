# Task: Definition Loader Migration

## Feature
017-dsl

## Summary
Complete the migration from deprecated `AgentLoader` implementations (`PythonAgentLoader`, `DslAgentLoader`, `YamlAgentLoader`) to the new `DefinitionLoader` implementations (`PythonDefinitionLoader`, `DslDefinitionLoader`, `YamlDefinitionLoader`).

## Background
The codebase is in a transitional state where:
1. New `DefinitionLoader` protocol and implementations exist in `streetrace.workloads`
2. Old `AgentLoader` implementations still exist in `streetrace.agents`
3. `WorkloadManager` still uses both systems, creating ambiguity
4. `DslAgentWorkflow` uses `DslStreetRaceAgent` for agent creation (via composition)

## Current State Analysis

### What Exists

**New Definition Loaders (in `streetrace.workloads`):**
- `DslDefinitionLoader`: Loads `.sr` files from path, compiles immediately
- `YamlDefinitionLoader`: Loads `.yaml/.yml` files from path, with reference resolution
- `PythonDefinitionLoader`: Loads Python agent directories with `agent.py`

**Old Agent Loaders (deprecated, in `streetrace.agents`):**
- `DslAgentLoader`: Also loads `.sr` files, creates `DslStreetRaceAgent`
- `YamlAgentLoader`: Loads YAML, supports HTTP URLs and recursive refs
- `PythonAgentLoader`: Loads Python directories

**Key Differences:**
1. **HTTP Loading**: `YamlAgentLoader` supports HTTP URLs; `YamlDefinitionLoader` only loads from paths
2. **Discovery**: Old loaders have `discover_in_paths()` that returns `AgentInfo`; new loaders have `discover()` that returns `list[Path]`
3. **Agent Creation**: `DslStreetRaceAgent.create_agent()` has rich agent resolution logic (tools, sub_agents, agent_tools)

### Files to Modify

1. `src/streetrace/workloads/manager.py` - Remove old loader usage, use only definition loaders
2. `src/streetrace/workloads/loader.py` - Add `load_from_url()` method to protocol
3. `src/streetrace/workloads/dsl_loader.py` - Already complete for path loading
4. `src/streetrace/workloads/yaml_loader.py` - Add HTTP loading support via SourceResolver
5. `src/streetrace/workloads/python_loader.py` - Already complete (no HTTP support needed)
6. `src/streetrace/workloads/dsl_workload.py` - May need to create agents without DslStreetRaceAgent

### Files to Remove After Migration
1. `src/streetrace/agents/base_agent_loader.py` - AgentInfo, AgentLoader
2. `src/streetrace/agents/dsl_agent_loader.py` - DslAgentInfo, DslAgentLoader, DslStreetRaceAgent
3. `src/streetrace/agents/yaml_agent_loader.py` - YamlAgentLoader
4. `src/streetrace/agents/py_agent_loader.py` - PythonAgentLoader

### Agent Files to Validate After Migration
- `agents/generic.yml` - YAML agent
- `src/streetrace/agents/coder/` - Python agent
- `agents/reviewer.sr` - DSL agent

## Success Criteria
1. `WorkloadManager` only uses `DefinitionLoader` implementations
2. All agent formats (DSL, YAML, Python) load correctly from paths
3. YAML agents can load from HTTP URLs
4. Recursive `$ref` resolution works in YAML agents
5. DSL agents can create ADK agents without `DslStreetRaceAgent`
6. All existing tests pass
7. Running `poetry run streetrace --agent=generic` works
8. Running `poetry run streetrace --agent=coder` works
9. Running `poetry run streetrace --agent=reviewer.sr` works
10. Old agent loader files can be removed without breaking the build

## Dependencies
- `SourceResolver` from `streetrace.agents.resolver` - provides HTTP and path resolution
- `YamlAgentSpec`, `YamlAgentDocument` models - used for YAML parsing
- `compile_dsl()` from DSL compiler - used for DSL compilation

## Design Decisions

### Pattern: Use SourceResolver as dependency
The `SourceResolver` already handles HTTP, path, and name resolution. The new definition loaders should use it as a dependency for loading from different sources.

### Agent Creation in DSL
The agent creation logic in `DslStreetRaceAgent._create_agent_from_def()` needs to be moved to `DslWorkload` or a new helper class. This logic includes:
- `_resolve_instruction()` - Get instruction from prompts
- `_resolve_model()` - Get model from models dict
- `_resolve_tools()` - Get tools from tool definitions
- `_resolve_sub_agents()` - Create sub-agents for delegate pattern
- `_resolve_agent_tools()` - Create agent tools for use pattern
