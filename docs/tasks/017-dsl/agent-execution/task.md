# Task Definition: Unified Agent Execution

## Feature Information
- **Feature ID**: 017-dsl
- **Task ID**: agent-execution
- **Branch**: feature/017-streetrace-dsl-2

## Design Documents
- **Primary Design**: `docs/tasks/017-dsl/agent-execution/tasks.md`
- **Implementation Plan**: `docs/tasks/017-dsl/agent-execution/todo.md`
- **Tech Debt Reference**: `docs/tasks/017-dsl/tech_debt.md`

## Summary

Implement the Workload Protocol to unify agent execution in the DSL runtime. This addresses
the critical inconsistency where agents invoked via `run agent` in flows cannot access their
DSL-defined tools and agentic patterns.

### Problem Statement

There are two distinct code paths for executing agents:

1. **Root agent execution** (`Supervisor.handle()`) - properly resolves tools, sub-agents, and
   agent_tools using `AgentManager.create_agent()` which delegates to `DslStreetRaceAgent`

2. **Flow-invoked agent execution** (`WorkflowContext.run_agent()`) - creates bare `LlmAgent`
   with only name, model, and instruction, missing all tooling and agentic patterns

### Solution: Workload Protocol

Implement a unified `Workload` protocol that all executable units (agents, flows) implement.
Key components:

1. **Workload Protocol** (`src/streetrace/workloads/protocol.py`)
   - `run_async(session, message) -> AsyncGenerator[Event, None]`
   - `close() -> None`

2. **WorkloadManager** (renamed from `AgentManager`)
   - Discovers, loads, and creates runnable workloads
   - Routes to `DslAgentWorkflow` or `BasicAgentWorkload` based on definition type

3. **DslAgentWorkflow** (implement Workload)
   - Python representation of `.sr` files
   - Uses `DslStreetRaceAgent` via **composition** for agent creation (no code duplication)
   - Provides `run_agent()` and `run_flow()` for flow execution

4. **BasicAgentWorkload**
   - Wrapper for Python and YAML agents
   - Implements Workload protocol using existing `StreetRaceAgent.create_agent()`

## Success Criteria

- [ ] `Workload` protocol defined with `run_async()` signature
- [ ] `AgentManager` renamed to `WorkloadManager` with `create_workload()` method
- [ ] `DslAgentWorkflow` implements `Workload` protocol
- [ ] `DslAgentWorkflow` uses `DslStreetRaceAgent` via composition (no code duplication)
- [ ] `BasicAgentWorkload` wraps existing PY/YAML agents
- [ ] `Supervisor` uses `WorkloadManager` instead of direct Runner
- [ ] Agents invoked via `ctx.run_agent()` in flows have full tools
- [ ] All existing tests pass
- [ ] No breaking changes to DSL syntax
- [ ] No breaking changes to existing Python/YAML agent definitions
- [ ] `DslStreetRaceAgent` unchanged (reused via composition)

## Dependencies

### Existing Code (to be modified)
- `src/streetrace/workflow/supervisor.py` - Supervisor class
- `src/streetrace/agents/agent_manager.py` - AgentManager to be renamed
- `src/streetrace/dsl/runtime/workflow.py` - DslAgentWorkflow to implement Workload
- `src/streetrace/dsl/runtime/context.py` - WorkflowContext to delegate to workflow
- `src/streetrace/app.py` - Application initialization

### Existing Code (unchanged, reused via composition)
- `src/streetrace/agents/dsl_agent_loader.py` - DslStreetRaceAgent with all agent creation logic
- `src/streetrace/agents/yaml_agent_loader.py` - YAML agent loader
- `src/streetrace/agents/py_agent_loader.py` - Python agent loader

### New Files
- `src/streetrace/workloads/__init__.py` - Package exports
- `src/streetrace/workloads/protocol.py` - Workload protocol definition
- `src/streetrace/workloads/manager.py` - WorkloadManager (renamed AgentManager)
- `src/streetrace/workloads/basic_workload.py` - BasicAgentWorkload

## Key Design Decisions

1. **Composition over absorption**: `DslAgentWorkflow` holds reference to `DslStreetRaceAgent`
   and delegates agent creation via `_create_agent_from_def()`. No code duplication.

2. **Event forwarding (Option 1)**: For this task, nested runs return results only, no event
   streaming. Infrastructure supports enhancement later.

3. **WorkloadManager naming**: Reflects that we're managing "workloads" (the unified abstraction)
   rather than just "agents".

4. **Session flow unchanged**: Sessions are passed to `workload.run_async()`, maintaining
   existing session management patterns.

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking PY/YAML agents | High | BasicAgentWorkload wraps unchanged |
| Breaking existing flows | High | run_agent() signature unchanged |
| Breaking DslStreetRaceAgent | None | Used via composition, not modified |
| Session handling regression | Medium | Extensive session tests |
| Circular imports | Medium | Careful import structure, TYPE_CHECKING |
