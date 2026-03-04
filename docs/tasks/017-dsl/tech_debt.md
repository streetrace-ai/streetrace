# Tech Debt: DSL Compiler Runtime Integration

## Open Issues

### SequentialAgent Not Used for Multi-Agent Flows

**Status**: Open
**Source**: Phase 3.1 Requirements

**Problem**: The design doc specifies that sequential agents in a flow should use ADK's `SequentialAgent` for better coordination. Currently each agent is run independently.

**Location**: `src/streetrace/dsl/codegen/visitors/flows.py`

**Desired Behavior**: Detect consecutive `run agent` statements and generate `SequentialAgent` wrapper.

**Required Changes**:
1. Add pattern detection in flow visitor for consecutive `RunStmt` nodes
2. Generate `SequentialAgent` wrapper for detected sequences
3. Update runtime context to support `SequentialAgent` execution

**Decision**: Let's skip this. Leveraging SequentalAgent is strongly beneficial to enable full ADK features, but it's more important to share state/context between the agents, while empowering the user with extra processing in-between agent executions. The critical part is that we should share state between all agents defined in the DSL (we'll work on that in the next phase).

---

## Escalate to human

This is not implemented, and the function seems to only output to the UI.

**Decision**: This is blocked by HITL implementation in general.

## Default flow and agent names

We should detect main flow and agent to execute in `_determine_entry_point` in src/streetrace/dsl/runtime/workflow.py:

- only one flow is defined - consider it main
- only one agent defined - consider it main
- a flow with no name (currently unsupported by the syntax, but we'll fix it)
- an agent with no name
- a flow or agent with names main or default

A flow always takes priority over agents when deciding what to run.

## Documentation Updates (Low Priority)

**Status**: Open
**Source**: Phase 6 - Workload Abstraction Refactoring

The following documentation updates are deferred:

1. **Update `docs/dev/dsl/api-reference.md`** - Point to new workloads package for loading
2. **Update `docs/user/dsl/getting-started.md`** - Remove references to old `DslAgentLoader` from `dsl/loader.py`
3. **Create migration guide** - Document old -> new type mappings:
   - `AgentInfo` -> `WorkloadDefinition` (or specific subclasses)
   - `AgentLoader` -> `DefinitionLoader`
   - `DslAgentLoader` -> `DslDefinitionLoader`
   - `YamlAgentLoader` -> `YamlDefinitionLoader`
   - `PythonAgentLoader` -> `PythonDefinitionLoader`

**Note**: These docs reference the old loader that was deleted in Phase 6.

---

## Resolved Issues

| Issue | Resolution Date | Notes |
|-------|-----------------|-------|
| Comma-separated tool lists in AST transformer | 2026-01-20 | `name_list` now filters COMMA tokens |
| Tool loading not passed to LlmAgent | 2026-01-20 | Implemented in `dsl_agent_loader.py:394-403` |
| Instruction resolution uses keyword matching | 2026-01-20 | Now uses direct field access |
| Model resolution falls back to first model | 2026-01-20 | Follows priority: prompt model → main → CLI |
| Semantic analyzer variable definition order | 2026-01-20 | Strips `$` prefix when defining variables |
| Tool Passing Inconsistency Between Loader and Runtime | 2026-01-21 | Implemented via Workload Protocol - DslAgentWorkflow uses composition with DslStreetRaceAgent |
| Duplicate DslAgentLoader implementations | 2026-01-22 | Phase 6 - Deleted `dsl/loader.py`, added deprecation warnings to old types |
| Tool Auth parameters not passed to transport | 2026-01-26 | Full chain implemented: grammar → AST → codegen → tool_factory with env var interpolation |
| Flow Execution Does Not Yield ADK Events | 2026-01-27 | Implemented via async generator pattern - flow methods yield events from run_agent and call_llm |
