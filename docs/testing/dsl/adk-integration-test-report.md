# E2E Test Report: DSL Agentic Patterns ADK Integration

**Date**: 2026-01-21T13:57:11
**Tester**: manual-e2e-tester agent
**Model Used**: claude-opus-4-5 (for testing agent)

## Documentation Reviewed

- User documentation: `docs/user/dsl/multi-agent-patterns.md`
- Testing documentation: `docs/testing/dsl/017-dsl-compiler-testing.md` (Section 9.8 - ADK Integration Testing)
- Developer documentation: `docs/dev/dsl/agentic-patterns.md`
- Example DSL files: `agents/examples/dsl/coordinator.sr`, `hierarchical.sr`, `iterative.sr`, `combined.sr`

## Test Environment

- Working directory: `/home/data/repos/github.com/streetrace-ai/streetrace`
- Git branch: `feature/017-streetrace-dsl-2`
- Python version: 3.12.9
- ADK version: google-adk package installed

## Scenarios Tested

### Scenario 1: Unit Tests for DSL Agent ADK Integration

- **Source**: `tests/unit/agents/test_dsl_agent_adk_integration.py`
- **Commands Executed**:
  ```bash
  poetry run pytest tests/unit/agents/test_dsl_agent_adk_integration.py -v --no-header --timeout=60
  ```
- **Expected**: All 19 tests pass
- **Actual**: All 19 tests passed in 0.06s
- **Status**: PASS
- **Notes**: Tests cover `_resolve_sub_agents`, `_resolve_agent_tools`, `_create_agent_from_def`, `create_agent`, and `close` methods

### Scenario 2: Integration Tests for DSL Agentic Patterns

- **Source**: `tests/integration/agents/test_dsl_agentic_patterns.py`
- **Commands Executed**:
  ```bash
  poetry run pytest tests/integration/agents/test_dsl_agentic_patterns.py -v --no-header --timeout=60
  ```
- **Expected**: All integration tests pass
- **Actual**: All 21 tests passed in 5.32s
- **Status**: PASS
- **Notes**: Tests cover coordinator pattern, hierarchical pattern, combined patterns, full pipeline, agent close, and workflow attributes

### Scenario 3: Coordinator Pattern Code Generation (dump-python)

- **Source**: Testing documentation Section 9.5
- **Commands Executed**:
  ```bash
  poetry run streetrace dump-python agents/examples/dsl/coordinator.sr
  ```
- **Expected**: Generated Python includes `'sub_agents': ['code_expert', 'research_expert']` in the default agent
- **Actual**: Generated code correctly includes:
  ```python
  'default': {
      'tools': ['fs'],
      'instruction': 'coordinator_prompt',
      'sub_agents': ['code_expert', 'research_expert'],
      'description': 'Coordinates tasks across specialists',
  },
  ```
- **Status**: PASS
- **Notes**: The `delegate` keyword correctly generates `sub_agents` field

### Scenario 4: Hierarchical Pattern Code Generation (dump-python)

- **Source**: Testing documentation Section 9.5
- **Commands Executed**:
  ```bash
  poetry run streetrace dump-python agents/examples/dsl/hierarchical.sr
  ```
- **Expected**: Generated Python includes `'agent_tools': ['extractor', 'analyzer', 'documenter']`
- **Actual**: Generated code correctly includes:
  ```python
  'default': {
      'tools': ['fs'],
      'instruction': 'orchestrator_prompt',
      'agent_tools': ['extractor', 'analyzer', 'documenter'],
      'description': 'Orchestrates code documentation workflow',
  },
  ```
- **Status**: PASS
- **Notes**: The `use` keyword correctly generates `agent_tools` field

### Scenario 5: Combined Patterns Code Generation

- **Source**: Testing documentation Section 9.4
- **Commands Executed**:
  ```bash
  poetry run streetrace dump-python agents/examples/dsl/combined.sr
  ```
- **Expected**: `code_reviewer` has `agent_tools`, `default` has `sub_agents`
- **Actual**: Correctly generates:
  - `code_reviewer` with `agent_tools: ['formatter', 'linter', 'security_scanner']`
  - `default` with `sub_agents: ['code_reviewer', 'doc_writer']`
- **Status**: PASS

### Scenario 6: Validation of Example Files (streetrace check)

- **Source**: Testing documentation Section 9.6
- **Commands Executed**:
  ```bash
  poetry run streetrace check agents/examples/dsl/coordinator.sr
  poetry run streetrace check agents/examples/dsl/hierarchical.sr
  poetry run streetrace check agents/examples/dsl/iterative.sr
  poetry run streetrace check agents/examples/dsl/combined.sr
  ```
- **Expected**: All files validate successfully
- **Actual**:
  - coordinator.sr: `valid (2 models, 3 agents)`
  - hierarchical.sr: `valid (2 models, 4 agents)`
  - iterative.sr: `valid (2 models, 1 agent, 1 flow)`
  - combined.sr: `valid (2 models, 6 agents, 1 flow)`
- **Status**: PASS

### Scenario 7: Undefined Agent Reference Error (delegate)

- **Source**: Testing documentation Section 9.1
- **Commands Executed**:
  ```bash
  poetry run streetrace check /tmp/delegate_undefined.sr
  ```
- **Expected**: Error E0001 for undefined agent reference
- **Actual**:
  ```
  error[E0001]: undefined reference to agent 'nonexistent_agent'
    --> /tmp/delegate_undefined.sr:7:2
  ```
- **Status**: PASS

### Scenario 8: Undefined Agent Reference Error (use)

- **Source**: Testing documentation Section 9.2
- **Commands Executed**:
  ```bash
  poetry run streetrace check /tmp/use_undefined.sr
  ```
- **Expected**: Error E0001 for undefined agent reference
- **Actual**:
  ```
  error[E0001]: undefined reference to agent 'nonexistent_agent'
    --> /tmp/use_undefined.sr:7:2
  ```
- **Status**: PASS

### Scenario 9: Circular Reference Detection

- **Source**: Testing documentation Section 9.2
- **Commands Executed**:
  ```bash
  poetry run streetrace check /tmp/circular_use.sr
  ```
- **Expected**: Error E0011 for circular agent reference
- **Actual**:
  ```
  error[E0011]: circular agent reference detected: agent_a -> agent_b -> agent_a
    --> /tmp/circular_use.sr:7:2
  ```
- **Status**: PASS

### Scenario 10: Both delegate and use Warning

- **Source**: Testing documentation Section 9.2
- **Commands Executed**:
  ```bash
  poetry run streetrace check /tmp/both_delegate_use.sr
  ```
- **Expected**: Warning W0002, exit code 0
- **Actual**:
  ```
  error[W0002]: agent 'mixed' has both delegate and use - this is unusual
  ```
  Exit code: 1
- **Status**: FAIL
- **Notes**: Warning is treated as error and causes non-zero exit code

### Scenario 11: Direct Python Agent Loading

- **Source**: Testing documentation Section 9.8
- **Commands Executed**: Python script testing DslAgentLoader
- **Expected**: Workflow class loads with correct `_agents` dict containing `sub_agents` and `agent_tools`
- **Actual**:
  - Coordinator: `Default agent sub_agents: ['code_expert', 'research_expert']`
  - Hierarchical: `Default agent agent_tools: ['extractor', 'analyzer', 'documenter']`
- **Status**: PASS

### Scenario 12: ADK Agent Creation (Combined Pattern)

- **Source**: Testing documentation Section 9.8
- **Commands Executed**: Python script testing `create_agent()` method
- **Expected**: Root agent has sub_agents with LlmAgent instances, sub-agents have AgentTools
- **Actual**:
  - Root agent: 2 sub_agents (`code_reviewer`, `doc_writer`)
  - `code_reviewer`: 3 AgentTools (`formatter`, `linter`, `security_scanner`)
  - `doc_writer`: 0 AgentTools (correct)
- **Status**: PASS
- **Notes**: Initial test appeared to show a bug where AgentTools were shared, but this was due to mock configuration returning the same list object. Using `side_effect=lambda x: []` instead of `return_value=[]` correctly isolates each call.

### Scenario 13: Resource Cleanup (close method)

- **Source**: Testing documentation Section 9.8
- **Commands Executed**: Python script testing `close()` method
- **Expected**: `close()` clears `_workflow_instance` and closes nested agents
- **Actual**: After close, `_workflow_instance` is `None`
- **Status**: PASS

## Issues Found

### Issue 1: W0002 Warning Causes Non-Zero Exit Code

- **Type**: Documentation Mismatch
- **Severity**: Low
- **Steps to Reproduce**:
  ```bash
  cat > /tmp/both_delegate_use.sr << 'EOF'
  streetrace v1
  model main = anthropic/claude-sonnet
  prompt helper_instruction: """Helper agent."""
  agent helper:
      instruction helper_instruction
      description "Helper"
  prompt specialist_instruction: """Specialist agent."""
  agent specialist:
      instruction specialist_instruction
      description "Specialist"
  prompt mixed_instruction: """Mixed pattern agent."""
  agent mixed:
      instruction mixed_instruction
      delegate helper
      use specialist
  EOF
  poetry run streetrace check /tmp/both_delegate_use.sr; echo "Exit code: $?"
  ```
- **Expected Behavior**: Documentation states "warnings do not cause failure" (exit code 0)
- **Actual Behavior**: Exit code is 1, warning is displayed as "error[W0002]"
- **Evidence**: The error prefix shows `error[W0002]` instead of `warning[W0002]`
- **Recommendation**: Either update the documentation to clarify that W0002 causes failure, or fix the implementation to treat warnings as non-fatal (exit code 0) unless `--strict` is used

## Summary

| Metric | Count |
|--------|-------|
| Total Scenarios | 13 |
| Passed | 12 |
| Failed | 1 |
| Issues Found | 1 |
| Documentation Gaps | 1 |

## Detailed Results by Feature Area

### Coordinator Pattern (delegate keyword)
- Code generation: PASS
- Semantic validation: PASS
- ADK agent creation (sub_agents): PASS
- Error handling (undefined reference): PASS

### Hierarchical Pattern (use keyword)
- Code generation: PASS
- Semantic validation: PASS
- ADK agent creation (AgentTool wrappers): PASS
- Error handling (undefined reference): PASS
- Circular reference detection: PASS

### Combined Patterns
- Code generation: PASS
- ADK agent creation: PASS
- Pattern isolation (no cross-contamination): PASS

### Resource Cleanup
- close() method: PASS
- Workflow instance cleanup: PASS

## Recommendations

### Priority 1: Fix W0002 Warning Exit Code

The warning W0002 for "agent has both delegate and use" should not cause a non-zero exit code. The message prefix should be `warning[W0002]` not `error[W0002]`. Either:
1. Update the implementation to emit warnings without failing
2. Update the documentation to clarify that W0002 is treated as an error

### Priority 2: Test Infrastructure Note

When writing tests that mock `tool_provider.get_tools()`, use `side_effect=lambda x: []` instead of `return_value=[]` to ensure each call gets a fresh list and avoid mutation issues.

## Test Artifacts

Test files created in `/tmp/`:
- `delegate_undefined.sr` - Tests undefined agent in delegate
- `use_undefined.sr` - Tests undefined agent in use
- `circular_use.sr` - Tests circular reference detection
- `both_delegate_use.sr` - Tests W0002 warning

## References

- Design: `docs/tasks/017-dsl/adk-integration/task.md`
- Developer Guide: `docs/dev/dsl/agentic-patterns.md`
- User Guide: `docs/user/dsl/multi-agent-patterns.md`
- Testing Guide: `docs/testing/dsl/017-dsl-compiler-testing.md`
- Implementation: `src/streetrace/agents/dsl_agent_loader.py` (lines 341-843)
