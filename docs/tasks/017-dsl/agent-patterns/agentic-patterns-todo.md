# Agentic Patterns Implementation Plan

| Field | Value |
|-------|-------|
| **Feature ID** | 017-dsl-compiler-patterns |
| **Feature Name** | Multi-Agent Patterns for DSL |
| **Status** | Planning |
| **Created** | 2026-01-21 |
| **Depends On** | 017-dsl-compiler (base implementation) |

## Overview

This document outlines the implementation plan for adding multi-agent pattern support to the Streetrace DSL, enabling full compatibility with Google ADK's multi-agent capabilities.

---

## Implementation Summary

| Pattern | Priority | Effort | Status |
|---------|----------|--------|--------|
| Coordinator/Dispatcher (`delegate`) | P1 | Medium | Planned |
| Hierarchical (`use`) | P1 | Medium | Planned |
| Iterative Refinement (`loop`) | P2 | Medium | Planned |
| Human-in-the-Loop (enhanced) | P3 | High | Future |

---

## Phase 1: `delegate` Keyword (Coordinator/Dispatcher Pattern)

### 1.1 Grammar Changes

**File:** `src/streetrace/dsl/grammar/streetrace.lark`

```lark
# Add to agent_property rule
agent_property: "tools" name_list _NL                 -> agent_tools
              | "instruction" NAME _NL                -> agent_instruction
              | "retry" NAME _NL                      -> agent_retry
              | "timeout" timeout_value _NL           -> agent_timeout
              | "description" STRING _NL              -> agent_description
              | "delegate" name_list _NL              -> agent_delegate  # NEW
```

**Tasks:**
- [ ] Add `agent_delegate` rule to grammar
- [ ] Add `delegate` to `contextual_keyword` list
- [ ] Test grammar parses `delegate` syntax correctly

### 1.2 AST Node Changes

**File:** `src/streetrace/dsl/ast/nodes.py`

```python
@dataclass
class AgentDef:
    name: str | None
    tools: list[str]
    instruction: str
    retry: str | None = None
    timeout_ref: str | None = None
    timeout_value: int | None = None
    timeout_unit: str | None = None
    description: str | None = None
    delegate: list[str] | None = None  # NEW
    meta: SourcePosition | None = None
```

**Tasks:**
- [ ] Add `delegate` field to `AgentDef` dataclass
- [ ] Update `__init__` if needed

### 1.3 AST Transformer Changes

**File:** `src/streetrace/dsl/ast/transformer.py`

**Tasks:**
- [ ] Add `agent_delegate` transformer method
- [ ] Update `agent_def` to collect delegate property
- [ ] Parse `name_list` for delegate agents

### 1.4 Semantic Analysis

**File:** `src/streetrace/dsl/semantic/analyzer.py`

**Tasks:**
- [ ] Validate delegate references exist as defined agents
- [ ] Add E0001 error for undefined delegate reference
- [ ] Detect circular delegate chains (E0011)
- [ ] Collect delegate relationships in symbol table

### 1.5 Code Generation

**File:** `src/streetrace/dsl/codegen/visitors/workflow.py`

**Tasks:**
- [ ] Update `_emit_agents()` to include `sub_agents` for delegates
- [ ] Generate correct ADK `LlmAgent` with `sub_agents=[...]`
- [ ] Handle agent ordering (delegated agents must be defined first)

### 1.6 Runtime Integration

**File:** `src/streetrace/agents/dsl_agent_loader.py`

**Tasks:**
- [ ] Update `_create_adk_agent()` to handle `sub_agents`
- [ ] Resolve delegate agent references to ADK agent instances
- [ ] Add agent ordering logic for dependency resolution

### 1.7 Tests

**File:** `tests/dsl/test_delegate.py`

**Tasks:**
- [ ] Parser test: Valid delegate syntax
- [ ] Parser test: Multiple delegates
- [ ] AST test: Delegate field populated correctly
- [ ] Semantic test: Undefined delegate error
- [ ] Semantic test: Circular delegate error
- [ ] Codegen test: sub_agents generated
- [ ] Integration test: End-to-end with mocked ADK

---

## Phase 2: `use` Keyword (Hierarchical Pattern)

### 2.1 Grammar Changes

**File:** `src/streetrace/dsl/grammar/streetrace.lark`

```lark
# Add to agent_property rule
agent_property: "tools" name_list _NL                 -> agent_tools
              | "instruction" NAME _NL                -> agent_instruction
              | "retry" NAME _NL                      -> agent_retry
              | "timeout" timeout_value _NL           -> agent_timeout
              | "description" STRING _NL              -> agent_description
              | "delegate" name_list _NL              -> agent_delegate
              | "use" name_list _NL                   -> agent_use  # NEW
```

**Tasks:**
- [ ] Add `agent_use` rule to grammar
- [ ] Add `use` to `contextual_keyword` list if not already present
- [ ] Test grammar parses `use` syntax correctly

### 2.2 AST Node Changes

**File:** `src/streetrace/dsl/ast/nodes.py`

```python
@dataclass
class AgentDef:
    name: str | None
    tools: list[str]
    instruction: str
    retry: str | None = None
    timeout_ref: str | None = None
    timeout_value: int | None = None
    timeout_unit: str | None = None
    description: str | None = None
    delegate: list[str] | None = None
    use: list[str] | None = None  # NEW
    meta: SourcePosition | None = None
```

**Tasks:**
- [ ] Add `use` field to `AgentDef` dataclass

### 2.3 AST Transformer Changes

**File:** `src/streetrace/dsl/ast/transformer.py`

**Tasks:**
- [ ] Add `agent_use` transformer method
- [ ] Update `agent_def` to collect use property
- [ ] Parse `name_list` for use agents

### 2.4 Semantic Analysis

**File:** `src/streetrace/dsl/semantic/analyzer.py`

**Tasks:**
- [ ] Validate use references exist as defined agents
- [ ] Add E0001 error for undefined use reference
- [ ] Detect circular use chains (E0011)
- [ ] Warn if agent has both delegate and use (unusual pattern)

### 2.5 Code Generation

**File:** `src/streetrace/dsl/codegen/visitors/workflow.py`

**Tasks:**
- [ ] Update imports to include `from google.adk.tools import agent_tool`
- [ ] Update `_emit_agents()` to wrap use agents as `AgentTool`
- [ ] Generate `tools=[agent_tool.AgentTool(agent=...)]` for use
- [ ] Handle combined tools list (regular tools + agent tools)

### 2.6 Runtime Integration

**File:** `src/streetrace/agents/dsl_agent_loader.py`

**Tasks:**
- [ ] Update `_resolve_tools()` to handle agent references
- [ ] Create `AgentTool` instances for use references
- [ ] Integrate with existing tool resolution logic

### 2.7 Tests

**File:** `tests/dsl/test_use.py`

**Tasks:**
- [ ] Parser test: Valid use syntax
- [ ] Parser test: Multiple use agents
- [ ] AST test: Use field populated correctly
- [ ] Semantic test: Undefined use error
- [ ] Semantic test: Circular use error
- [ ] Codegen test: AgentTool generated
- [ ] Integration test: End-to-end with mocked ADK

---

## Phase 3: `loop` Block (Iterative Refinement Pattern)

### 3.1 Grammar Changes

**File:** `src/streetrace/dsl/grammar/streetrace.lark`

```lark
# Add to flow_statement
flow_statement: assignment _NL
              | run_stmt _NL
              | call_stmt _NL
              | return_stmt _NL
              | for_loop
              | parallel_block
              | match_block
              | if_block
              | if_stmt _NL
              | push_stmt _NL
              | escalate_stmt _NL
              | log_stmt _NL
              | notify_stmt _NL
              | expression_stmt _NL
              | failure_block
              | flow_control _NL
              | loop_block  # NEW

# New loop block rule
loop_block: "loop" "max" INT "do" _NL _INDENT flow_body _DEDENT "end" _NL?
          | "loop" "do" _NL _INDENT flow_body _DEDENT "end" _NL?
```

**Tasks:**
- [ ] Add `loop_block` rule to grammar
- [ ] Add `loop` and `max` to `contextual_keyword` list
- [ ] Add to `flow_statement` alternatives
- [ ] Test grammar parses loop syntax correctly

### 3.2 AST Node Changes

**File:** `src/streetrace/dsl/ast/nodes.py`

```python
@dataclass
class LoopBlock:
    """Loop block for iterative refinement."""
    max_iterations: int | None  # None for unlimited
    body: list[AstNode]
    meta: SourcePosition | None = None
```

**Tasks:**
- [ ] Add `LoopBlock` dataclass
- [ ] Add to AstNode type union if applicable

### 3.3 AST Transformer Changes

**File:** `src/streetrace/dsl/ast/transformer.py`

**Tasks:**
- [ ] Add `loop_block` transformer method
- [ ] Extract max_iterations from tree (if present)
- [ ] Transform body statements

### 3.4 Semantic Analysis

**File:** `src/streetrace/dsl/semantic/analyzer.py`

**Tasks:**
- [ ] Validate loop body statements
- [ ] Validate max_iterations is positive
- [ ] Warn if loop has no exit condition and no max_iterations
- [ ] Track loop nesting depth (warn on deep nesting)

### 3.5 Code Generation

**File:** `src/streetrace/dsl/codegen/visitors/flows.py`

**Tasks:**
- [ ] Add `_emit_loop_block()` method
- [ ] Generate `LoopAgent` wrapper
- [ ] Handle exit conditions via escalation
- [ ] Update imports for `LoopAgent`

### 3.6 Runtime Integration

**File:** `src/streetrace/dsl/runtime/context.py`

**Tasks:**
- [ ] Add loop iteration tracking to context
- [ ] Support break/continue within loops
- [ ] Handle max_iterations enforcement

### 3.7 Tests

**File:** `tests/dsl/test_loop.py`

**Tasks:**
- [ ] Parser test: Loop with max iterations
- [ ] Parser test: Loop without max iterations
- [ ] AST test: LoopBlock fields populated
- [ ] Semantic test: Warning for unbounded loop
- [ ] Codegen test: LoopAgent generated
- [ ] Integration test: Loop executes correct number of times

---

## Phase 4: Example Files

### 4.1 Create Example DSL Files

**Directory:** `agents/examples/dsl/`

**Tasks:**
- [ ] Create `coordinator.sr` - Coordinator/Dispatcher pattern
- [ ] Create `hierarchical.sr` - Hierarchical pattern
- [ ] Create `iterative.sr` - Iterative Refinement pattern
- [ ] Create `combined.sr` - Multiple patterns combined

### 4.2 Update Existing Examples

**Tasks:**
- [ ] Update `agents/examples/dsl/README.md` with new patterns
- [ ] Add pattern examples to documentation

---

## Phase 5: Documentation

### 5.1 User Documentation

**Tasks:**
- [ ] Update `docs/user/dsl/getting-started.md` with pattern syntax
- [ ] Add pattern tutorials to user docs
- [ ] Update CLI reference with new validation messages

### 5.2 Developer Documentation

**Tasks:**
- [ ] Update `docs/dev/dsl/architecture.md` with pattern implementation
- [ ] Update `docs/dev/dsl/grammar.md` with new rules
- [ ] Update `docs/dev/dsl/extending.md` with pattern extension guide

---

## Implementation Order

### Sprint 1: Foundation
1. Grammar changes for `delegate` and `use`
2. AST node changes
3. AST transformer changes

### Sprint 2: Validation
4. Semantic analysis for both keywords
5. Error codes and messages
6. Circular reference detection

### Sprint 3: Code Generation
7. Code generation for `delegate` (sub_agents)
8. Code generation for `use` (AgentTool)
9. Runtime integration

### Sprint 4: Loop Support
10. Grammar changes for `loop`
11. AST and transformer for `loop`
12. Semantic analysis for `loop`
13. Code generation for `loop` (LoopAgent)

### Sprint 5: Polish
14. Example files
15. Documentation updates
16. End-to-end testing
17. Performance testing

---

## Error Codes

| Code | Message | Trigger |
|------|---------|---------|
| E0001 | undefined reference to agent 'X' | `delegate` or `use` references non-existent agent |
| E0011 | circular agent reference detected | Agent A delegates/uses B which delegates/uses A |
| W0001 | unbounded loop without exit condition | `loop do` without break/return in body |
| W0002 | agent has both delegate and use | Unusual pattern, may indicate design issue |

---

## Testing Strategy

### Unit Tests
- Parser tests for each new syntax element
- AST tests for correct node construction
- Semantic tests for validation rules
- Codegen tests for correct output

### Integration Tests
- Full pipeline tests (parse -> compile -> load)
- Mock ADK for runtime tests
- Real ADK integration tests (manual/CI)

### Performance Tests
- Compilation time with complex agent hierarchies
- Runtime performance with nested agents
- Memory usage with large agent graphs

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| ADK API changes | High | Pin ADK version, abstract integration |
| Circular references hard to detect | Medium | Use graph algorithms, comprehensive tests |
| Performance degradation with deep hierarchies | Medium | Add depth limits, optimize resolution |
| Grammar ambiguity with new keywords | Low | Use contextual keywords, test thoroughly |

---

## Success Criteria

1. All example files in `agents/examples/dsl/` validate successfully
2. `streetrace check` catches all semantic errors for new patterns
3. `streetrace dump-python` generates correct ADK code
4. E2E tests pass with mock and real ADK
5. Documentation is complete and accurate
6. No regression in existing functionality

---

## Dependencies

### External
- Google ADK (specific version TBD)
- `google.adk.agents.LoopAgent` availability
- `google.adk.tools.agent_tool.AgentTool` availability

### Internal
- Base DSL compiler (017-dsl-compiler)
- Semantic analyzer infrastructure
- Code generator visitor pattern

---

## References

- [Agentic Patterns Documentation](./agentic-patterns.md)
- [DSL Grammar Specification](../../../rfc/design/017-dsl-grammar.md)
- [ADK Multi-Agent Documentation](https://google.github.io/adk-docs/agents/multi-agents/)
- [Testing Guide](../../testing/dsl/017-dsl-compiler-testing.md)

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 0.1 | Initial implementation plan |
