# Tech Debt: DSL Compiler Runtime Integration

## Open Issues

### Flow Execution Does Not Yield ADK Events

**Status**: Open
**Source**: Phase 3 Requirements
**Location**: `src/streetrace/dsl/runtime/context.py`, `WorkflowContext.run_agent()`

**Problem**: The current implementation collects the final response from agent execution but does not yield intermediate ADK events. The design doc specifies that flows should produce async generators yielding ADK events.

**Current Behavior**: `run_agent()` returns only the final text response.

**Desired Behavior**: Flow methods should yield ADK events as they occur:
```python
async for event in self.run_agent('main_agent', input_prompt):
    if event.is_final_response():
        ctx.vars['analysis'] = event.data
    yield event
```

**Workaround**: The current await-based approach works for basic flows but doesn't support event streaming or progress monitoring.

**Required Changes**:
1. Change `run_agent()` return type to `AsyncGenerator[Event, None]`
2. Update code generation in `flows.py` to handle async generators
3. Update flow method signatures to support yielding events

**Decision**: Let's keep this open for now. We need to figure out the use cases.

---

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

## Tool Auth parameters (CRITICAL)

In a tool DSL like this (snippet):

```
tool github = mcp "https://api.githubcopilot.com/mcp/" with auth bearer "${GITHUB_PERSONAL_ACCESS_TOKEN}"
```

The resulting generated `McpToolRef`'s Transport should include relevant headers, but it doesn't. As seen from example, we need to make sure we expand env variables.

## Excallate to human

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

## Resolved Issues

| Issue | Resolution Date | Notes |
|-------|-----------------|-------|
| Comma-separated tool lists in AST transformer | 2026-01-20 | `name_list` now filters COMMA tokens |
| Tool loading not passed to LlmAgent | 2026-01-20 | Implemented in `dsl_agent_loader.py:394-403` |
| Instruction resolution uses keyword matching | 2026-01-20 | Now uses direct field access |
| Model resolution falls back to first model | 2026-01-20 | Follows priority: prompt model → main → CLI |
| Semantic analyzer variable definition order | 2026-01-20 | Strips `$` prefix when defining variables |
| Tool Passing Inconsistency Between Loader and Runtime | 2026-01-21 | Implemented via Workload Protocol - DslAgentWorkflow uses composition with DslStreetRaceAgent |
