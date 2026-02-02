# Phase 4: Remove Flow Parameters -- Implementation Plan

## Status Legend
- `[ ]` Pending
- `[x]` Completed
- `[-]` Blocked (include reason)

## Tasks

### 1. Write Tests
- [ ] Create `tests/dsl/test_no_flow_params.py` with comprehensive test coverage (dependency: none)

### 2. Grammar Changes
- [ ] Remove `flow_params?` from `flow_def` rule in `streetrace.lark` (dependency: 1)
- [ ] Delete `flow_params: variable+` rule (dependency: 1)

### 3. AST Changes
- [ ] Reorder `FlowDef` fields: move `params` after `body` with `field(default_factory=list)` (dependency: 2)
- [ ] Update ALL code constructing `FlowDef` positionally across codebase (dependency: 3)

### 4. Transformer Changes
- [ ] Remove `flow_params` transformer method (dependency: 2)
- [ ] Simplify `flow_def` / `_extract_flow_components` to not look for params (dependency: 2)

### 5. Semantic Analyzer Changes
- [ ] Remove parameter definition loop in `_validate_flow` (dependency: 3)

### 6. Update Existing Tests
- [ ] Update `tests/dsl/test_flow_parameters.py` -- verify params are rejected (dependency: 2-5)
- [ ] Update all FlowDef constructions across test files (dependency: 3)

### 7. Cleanup
- [ ] Remove `flow_params` entry from `vulture_allow.txt` (dependency: 4)
- [ ] Run `make check` and fix all issues (dependency: 1-6)
