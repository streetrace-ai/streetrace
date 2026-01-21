# Tech Debt: DSL Compiler Runtime Integration

## CRITICAL: Comma-separated Tool Lists in AST Transformer

**Status**: Fixed (Phase 6)
**Source**: Code Review Expectation E1 / Phase 1 Implementation
**Location**: `src/streetrace/dsl/ast/transformer.py`, `name_list` method

**Problem**: The `name_list` transformer did not filter out `COMMA` tokens, causing comma characters to be included as tool names in the agent's tool list.

**Fix Applied**: Updated `name_list` to use `_filter_children(items)` and filter Token objects.

**Resolution Date**: 2026-01-20

---

## Tool Loading Not Passed to LlmAgent

**Status**: In Progress (Phase 1.1)
**Source**: `dsl_agent_loader.py:395`
**Comment**: "Tool loading from DSL is not yet fully implemented"

**Problem**: Tools defined in DSL `_tools` dict are never passed to the `LlmAgent` constructor.

---

## Instruction Resolution Uses Keyword Matching

**Status**: In Progress (Phase 1.2)
**Source**: `dsl_agent_loader.py:376-393`

**Problem**: Instruction lookup uses `"instruction" in key.lower()` instead of reading `agent.instruction` field directly.

---

## Model Resolution Falls Back to First Model

**Status**: In Progress (Phase 1.3)
**Source**: `dsl_agent_loader.py:362-372`

**Problem**: Model selection falls back to first available model instead of following design spec:
1. Model from prompt's `using model` clause
2. Fall back to model named "main"
3. CLI override

---

## Phase 3 Items

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

---

### SequentialAgent Not Used for Multi-Agent Flows

**Status**: Open
**Source**: Phase 3.1 Requirements

**Problem**: The design doc specifies that sequential agents in a flow should use ADK's `SequentialAgent` for better coordination. Currently each agent is run independently.

**Location**: `src/streetrace/dsl/codegen/visitors/flows.py`

**Desired Behavior**: Detect consecutive `run agent` statements and generate `SequentialAgent` wrapper.

---

### Semantic Analyzer Variable Definition Order

**Status**: Fixed (Phase 3)
**Source**: Bug discovered during Phase 3
**Location**: `src/streetrace/dsl/semantic/analyzer.py`

**Problem**: Variables were defined with `$` prefix in scope but looked up without prefix, causing false "used before definition" errors.

**Fix Applied**: Strip `$` prefix when defining variables in scope to match VarRef name format.
