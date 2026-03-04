# Implementation Plan: DSL Agentic Patterns

| Field | Value |
|-------|-------|
| **Feature ID** | 017-dsl-compiler-patterns |
| **Status** | COMPLETED |
| **Last Updated** | 2026-01-21 |

---

## Phase 1: Grammar and AST Foundation (COMPLETED)

### 1.1 Grammar Changes
- [x] Add `agent_delegate` rule to grammar (`delegate` name_list)
- [x] Add `agent_use` rule to grammar (`use` name_list)
- [x] Add `loop_block` rule to grammar
- [x] Add `loop`, `max`, `delegate` to contextual keywords (`use` already present)
- [x] Run parser tests to verify grammar changes

### 1.2 AST Node Changes
- [x] Add `delegate: list[str] | None` field to `AgentDef`
- [x] Add `use: list[str] | None` field to `AgentDef`
- [x] Create `LoopBlock` dataclass with `max_iterations`, `body`, `meta`
- [x] `ContinueStmt` and `BreakStmt` already present in AST

### 1.3 AST Transformer Changes
- [x] Add `agent_delegate` transformer method
- [x] Add `agent_use` transformer method
- [x] Add `loop_block` transformer method
- [x] Update `agent_def` to collect delegate property
- [x] Update `agent_def` to collect use property
- [x] Update `flow_statement` to include loop_block
- [x] Update `handler_statement` to include loop_block (for event handlers)

### 1.4 Tests for Phase 1
- [x] Test: Grammar parses `delegate` syntax correctly (4 tests)
- [x] Test: Grammar parses `use` syntax correctly (4 tests)
- [x] Test: Grammar parses `loop max N do` syntax correctly (3 tests)
- [x] Test: Grammar parses `loop do` (infinite) syntax correctly (1 test)
- [x] Test: AST `AgentDef.delegate` populated correctly (3 tests)
- [x] Test: AST `AgentDef.use` populated correctly (3 tests)
- [x] Test: AST `LoopBlock` fields populated correctly (6 tests)
- [x] Run `make check` and ensure all checks pass (1290 tests passed)

---

## Phase 2: Semantic Analysis (COMPLETED)

### 2.1 Reference Validation
- [x] Validate `delegate` references exist as defined agents
- [x] Validate `use` references exist as defined agents
- [x] Add E0001 error for undefined delegate/use references
- [x] Add suggestion for similar agent names

### 2.2 Circular Reference Detection
- [x] Implement graph-based circular reference detection
- [x] Add E0011 error code for circular agent reference
- [x] Test: agent_a → delegate agent_b → delegate agent_a
- [x] Test: agent_a → use agent_b → use agent_a

### 2.3 Validation Rules
- [x] Warn if agent has both `delegate` and `use` (W0002)
- [x] Validate loop body statements
- [x] LoopBlock added to control flow validation

### 2.4 Tests for Phase 2
- [x] Test: Undefined delegate error (E0001)
- [x] Test: Undefined use error (E0001)
- [x] Test: Circular delegate error (E0011)
- [x] Test: Circular use error (E0011)
- [x] Test: Valid delegate passes
- [x] Test: Valid use passes
- [x] Test: Warning for both delegate and use (W0002)
- [x] Test: W0002 warning does not fail validation (is_valid=True)
- [x] Run `make check` and ensure all tests pass

---

## Phase 3: Code Generation (COMPLETED)

### 3.1 Delegate Code Generation
- [x] Update `_emit_agents()` to include `sub_agents` parameter
- [x] Generate `sub_agents=[agent_name, ...]` for delegates
- [x] Handle agent ordering (delegated agents defined first)

### 3.2 Use Code Generation
- [x] Generate `agent_tools=[...]` for use agents
- [x] Combine regular tools with agent tools in tools list
- [x] Handle agent ordering for dependencies

### 3.3 Loop Code Generation
- [x] Add `_visit_loop_block()` method to FlowVisitor
- [x] Generate while loop with counter for bounded loops
- [x] Generate `while True:` for unbounded loops
- [x] Add LoopBlock to flow statement dispatch

### 3.4 Tests for Phase 3
- [x] Test: `delegate` generates `sub_agents=[...]`
- [x] Test: `use` generates `agent_tools=[...]`
- [x] Test: `loop max 5 do` generates while loop with counter
- [x] Test: `loop do` generates `while True` loop
- [x] Test: Generated Python code compiles successfully
- [x] Run `make check` and ensure all tests pass

---

## Phase 4: Example Files (COMPLETED)

### 4.1 Create Examples
- [x] Create `agents/examples/dsl/coordinator.sr`
- [x] Create `agents/examples/dsl/hierarchical.sr`
- [x] Create `agents/examples/dsl/iterative.sr`
- [x] Create `agents/examples/dsl/combined.sr`

### 4.2 Validate Examples
- [x] All example files parse successfully
- [x] All example files pass semantic analysis
- [x] Code generation produces valid Python

---

## Phase 5: Documentation (COMPLETED)

### 5.1 Developer Documentation
- [x] Created `docs/dev/dsl/agentic-patterns.md`
- [x] Updated `docs/dev/dsl/architecture.md` with reference

### 5.2 User Documentation
- [x] Created `docs/user/dsl/multi-agent-patterns.md`
- [x] Updated `docs/user/dsl/getting-started.md`
- [x] Updated `docs/user/dsl/syntax-reference.md`
- [x] Updated `docs/user/dsl/troubleshooting.md`

### 5.3 Testing Documentation
- [x] Updated `docs/testing/dsl/017-dsl-compiler-testing.md`
- [x] Created E2E test report

---

## Phase 6: Quality Assurance (COMPLETED)

### 6.1 Run All Checks
- [x] Run `make check` (lint, type, test, security)
- [x] All linting issues fixed
- [x] All type errors fixed
- [x] All security warnings resolved
- [x] All 1346+ tests pass

### 6.2 Integration Testing
- [x] Test full pipeline: parse → analyze → generate → compile
- [x] Generated code compiles to valid Python
- [x] Run manual E2E tests from testing guide

### 6.3 Final Validation
- [x] All example files pass validation
- [x] All tests pass
- [x] Documentation is complete
- [x] No regressions in existing functionality

---

## Error Codes Reference

| Code | Message | Trigger |
|------|---------|---------|
| E0001 | undefined reference to agent 'X' | `delegate` or `use` references non-existent agent |
| E0011 | circular agent reference detected | Agent A delegates/uses B which delegates/uses A |
| W0002 | agent has both delegate and use | Unusual pattern, may indicate design issue |

---

## Changelog

| Date | Phase | Changes |
|------|-------|---------|
| 2026-01-21 | Setup | Created implementation plan |
| 2026-01-21 | Phase 1 | Completed grammar, AST, and transformer changes |
| 2026-01-21 | Phase 2 | Completed semantic analysis for delegate, use, and loop patterns |
| 2026-01-21 | Phase 3 | Completed code generation for delegate, use, and loop patterns |
| 2026-01-21 | Phase 4 | Created and validated example DSL files |
| 2026-01-21 | Phase 5 | Created developer, user, and testing documentation |
| 2026-01-21 | Phase 6 | All quality checks pass, E2E testing complete |
