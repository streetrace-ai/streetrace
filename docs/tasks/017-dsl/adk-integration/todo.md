# Implementation Plan: DSL Agentic Patterns ADK Integration

| Field | Value |
|-------|-------|
| **Feature ID** | 017-dsl-adk-integration |
| **Status** | Not Started |
| **Last Updated** | 2026-01-21 |

---

## Phase 1: Core Agent Creation (Estimated: 3-4 code changes)

### 1.1 Add _create_agent_from_def() Helper Method
- [ ] Create helper method to build LlmAgent from agent definition dict
- [ ] Extract common logic from create_agent()
- [ ] Handle instruction, model, and tools resolution
- [ ] Support description field
- [ ] Location: `src/streetrace/agents/dsl_agent_loader.py`

### 1.2 Add _resolve_sub_agents() Method
- [ ] Create method to resolve `sub_agents` field from agent_def
- [ ] Look up agent names in `_agents` dict
- [ ] Recursively call `_create_agent_from_def()` for each
- [ ] Log warning for undefined agent references
- [ ] Location: `src/streetrace/agents/dsl_agent_loader.py`

### 1.3 Add _resolve_agent_tools() Method
- [ ] Create method to resolve `agent_tools` field from agent_def
- [ ] Import `AgentTool` from `google.adk.tools.agent_tool`
- [ ] Create sub-agent using `_create_agent_from_def()`
- [ ] Wrap each agent in `AgentTool()`
- [ ] Return list of AgentTool instances
- [ ] Location: `src/streetrace/agents/dsl_agent_loader.py`

### 1.4 Update create_agent() Method
- [ ] Call `_resolve_sub_agents()` after resolving tools
- [ ] Call `_resolve_agent_tools()` and extend tools list
- [ ] Pass `sub_agents` parameter to LlmAgent if not empty
- [ ] Refactor to use `_create_agent_from_def()` for root agent
- [ ] Location: `src/streetrace/agents/dsl_agent_loader.py:340-382`

### 1.5 Tests for Phase 1
- [ ] Test: sub_agents created for delegate pattern
- [ ] Test: agent_tools created for use pattern
- [ ] Test: recursive sub-agent creation works
- [ ] Test: undefined agent warning logged
- [ ] Run `make check` and ensure all checks pass

---

## Phase 2: Code Generator Enhancement (Estimated: 1-2 code changes)

### 2.1 Add Description Field to Agent Emission
- [ ] Update `_emit_agents()` to emit description field
- [ ] Get description from `AgentDef.description`
- [ ] Location: `src/streetrace/dsl/codegen/visitors/workflow.py:319-357`

### 2.2 Tests for Phase 2
- [ ] Test: description field emitted in generated code
- [ ] Test: existing agents without description still work
- [ ] Run `make check` and ensure all checks pass

---

## Phase 3: Resource Cleanup (Estimated: 2 code changes)

### 3.1 Add Recursive Close Method
- [ ] Create `_close_agent_recursive()` method
- [ ] Iterate over `agent.sub_agents` and close recursively
- [ ] Handle `AgentTool` in tools list specially
- [ ] Call close on tools that support it
- [ ] Location: `src/streetrace/agents/dsl_agent_loader.py`

### 3.2 Update close() Method
- [ ] Call `_close_agent_recursive()` for root agent
- [ ] Clear workflow instance after cleanup
- [ ] Add `import inspect` for awaitable check
- [ ] Location: `src/streetrace/agents/dsl_agent_loader.py:623-625`

### 3.3 Tests for Phase 3
- [ ] Test: close() cleans up sub-agents
- [ ] Test: close() cleans up agent tools
- [ ] Test: nested cleanup order correct (depth-first)
- [ ] Run `make check` and ensure all checks pass

---

## Phase 4: Unit Tests (Estimated: 1 new test file)

### 4.1 Create Test File
- [ ] Create `tests/unit/agents/test_dsl_agent_adk_integration.py`
- [ ] Set up fixtures for workflow class mocking
- [ ] Mock ADK LlmAgent and AgentTool

### 4.2 Sub-Agents Tests
- [ ] Test single sub-agent creation
- [ ] Test multiple sub-agents creation
- [ ] Test nested sub-agents (sub-agent with its own sub-agents)
- [ ] Test empty sub_agents list

### 4.3 Agent Tools Tests
- [ ] Test single agent tool creation
- [ ] Test multiple agent tools creation
- [ ] Test agent tool has correct agent wrapped
- [ ] Test empty agent_tools list

### 4.4 Combined Pattern Tests
- [ ] Test agent with both delegate and use
- [ ] Test mixed hierarchy (delegate uses agent with use)

### 4.5 Error Handling Tests
- [ ] Test undefined sub-agent logs warning
- [ ] Test undefined agent_tool logs warning

### 4.6 Run All Tests
- [ ] Run `pytest tests/unit/agents/test_dsl_agent_adk_integration.py -v`
- [ ] Verify >95% coverage for new code
- [ ] Run `make check` for full validation

---

## Phase 5: Integration Tests (Estimated: 1 new test file)

### 5.1 Create Integration Test File
- [ ] Create `tests/integration/agents/test_dsl_agentic_patterns.py`
- [ ] Set up test fixtures for full pipeline

### 5.2 Example File Tests
- [ ] Test coordinator.sr loads and creates sub_agents
- [ ] Test hierarchical.sr loads and creates AgentTools
- [ ] Test iterative.sr loads (loop pattern)
- [ ] Test combined.sr loads with all patterns

### 5.3 Full Pipeline Tests
- [ ] Test parse → analyze → generate → load → create_agent
- [ ] Verify agent hierarchy matches DSL definition
- [ ] Verify tools are resolved correctly

### 5.4 Run Integration Tests
- [ ] Run `pytest tests/integration/agents/test_dsl_agentic_patterns.py -v`
- [ ] Run `make check` for full validation

---

## Phase 6: Quality Assurance

### 6.1 Final Validation
- [ ] Run `make check` (lint, type, test, security, depcheck, unusedcode)
- [ ] Verify no new linting errors
- [ ] Verify no new type errors
- [ ] Verify all tests pass

### 6.2 Manual E2E Testing
- [ ] Test `poetry run streetrace --agent agents/examples/dsl/coordinator.sr`
- [ ] Test `poetry run streetrace --agent agents/examples/dsl/hierarchical.sr`
- [ ] Verify `streetrace dump-python` shows correct output

### 6.3 Documentation Review
- [ ] Verify task.md is accurate
- [ ] Update testing guide if needed
- [ ] Update CLAUDE.md if patterns needed

---

## Changelog

| Date | Phase | Changes |
|------|-------|---------|
| 2026-01-21 | Setup | Created implementation plan |

---

## Notes

### Key Implementation Details

1. **Agent Definition Access:**
   All agent definitions are in `self._workflow_class._agents` dict with structure:
   ```python
   {
       'name': {
           'tools': [...],
           'instruction': '...',
           'sub_agents': [...],    # From delegate keyword
           'agent_tools': [...],   # From use keyword
       }
   }
   ```

2. **Model Inheritance:**
   Sub-agents should inherit the parent model unless they specify their own via prompt's `using model` clause.

3. **Circular Reference Protection:**
   The semantic analyzer already detects circular references at compile time (E0011 error). No runtime protection needed.

4. **Reference Implementation:**
   The `YamlAgentBuilder` in `yaml_agent_builder.py:112-163` provides a working reference for both patterns.
