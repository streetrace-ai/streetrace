# Implementation Plan: Code Review Agent DSL Support

## Overview

Make the three code review agents in `./agents/code-review/` work end-to-end by implementing missing DSL features.

**Constraint**: Do not modify the agent .sr files (except minor syntax adjustments like `call llm` → `run agent` in parallel blocks if needed).

---

## Phase 1: Parallel Block → ADK ParallelAgent

**Goal**: Implement `parallel do` using ADK's `ParallelAgent` for true concurrent execution.

### Task 1.1: Grammar Validation
- [ ] Verify `parallel_block` grammar accepts only `run agent` statements
- [ ] Add compile-time validation to reject other statement types
- [ ] Provide clear error message: "parallel do only supports 'run agent' statements"

**Acceptance**: Attempting `parallel do` with unsupported statements produces clear error.

### Task 1.2: Study ADK ParallelAgent API
- [ ] Review `google.adk.agents.ParallelAgent` documentation/source
- [ ] Understand how sub_agents are passed inputs
- [ ] Understand how results are collected from sub_agents
- [ ] Document the execution model

**Code to study**:
- ADK source for ParallelAgent
- `docs/tasks/017-dsl/agent-patterns/agentic-patterns.md:160-177`

### Task 1.3: Implement ParallelBlock Codegen
- [ ] Extract `run agent` statements from parallel block body
- [ ] Generate code to create sub-agent instances with bound inputs
- [ ] Generate ParallelAgent instantiation
- [ ] Generate code to execute ParallelAgent
- [ ] Generate code to unpack results into assigned variables

**File**: `src/streetrace/dsl/codegen/visitors/flows.py` (replace `_visit_parallel_block`)

**Generated pattern**:
```python
# Create bound agent instances
_agent_1 = self._create_agent('agent1')
_agent_2 = self._create_agent('agent2')

# Create ParallelAgent
_parallel = ParallelAgent(
    name="parallel_block_N",
    sub_agents=[_agent_1, _agent_2]
)

# Execute and collect results
_results = await self._execute_parallel(_parallel, [input1, input2])

# Unpack into variables
ctx.vars['a'] = _results[0]
ctx.vars['b'] = _results[1]
```

### Task 1.4: Runtime Support for ParallelAgent
- [ ] Add helper method to workflow base class for parallel execution
- [ ] Handle result collection from ParallelAgent
- [ ] Ensure proper error propagation from sub-agents

**File**: `src/streetrace/dsl/runtime/workflow.py`

### Task 1.5: Test Parallel Execution
- [ ] Test with `agents/examples/dsl/parallel.sr`
- [ ] Verify agents actually run concurrently (timing/logs)
- [ ] Verify results are correctly assigned to variables
- [ ] Test error handling when one agent fails

---

## Phase 2: Filter Expression and Concat Verification

**Goal**: Implement `filter $list where .property` syntax and verify `+` works for lists.

### Task 2.1: Add Implicit Property to Grammar
- [ ] Add `implicit_property: "." contextual_name ("." contextual_name)*` production
- [ ] Add `implicit_property` as new atom type in expression grammar

**File**: `src/streetrace/dsl/grammar/streetrace.lark`

**Grammar additions** (around line 428):
```lark
?atom: literal
     | variable
     | property_access
     | function_call
     | identifier                                     -> name_ref
     | LPAR expression RPAR                           -> paren_expr
     | implicit_property

# New production for implicit property access (leading dot)
implicit_property: "." contextual_name ("." contextual_name)*
```

### Task 2.2: Add Filter Expression to Grammar
- [ ] Add `filter_expr: "filter" expression "where" expression` production
- [ ] Integrate into expression grammar

**File**: `src/streetrace/dsl/grammar/streetrace.lark`

```lark
# Add near function_call (~line 492)
filter_expr: "filter" expression "where" expression
```

### Task 2.3: Add AST Nodes
- [ ] Add `ImplicitProperty` node (stores property path like `["confidence"]` or `["nested", "prop"]`)
- [ ] Add `FilterExpr` node (stores list expression and condition expression)

**File**: `src/streetrace/dsl/ast/nodes.py`

### Task 2.4: Add Transformer Rules
- [ ] Transform `implicit_property` → `ImplicitProperty`
- [ ] Transform `filter_expr` → `FilterExpr`

**File**: `src/streetrace/dsl/ast/transformer.py`

### Task 2.5: Implement ImplicitProperty Codegen
- [ ] Generate property access on implicit loop variable `_item`
- [ ] Handle nested properties: `.a.b` → `_item['a']['b']`

**Example**:
```streetrace
.confidence >= 80
```
→ (inside filter context)
```python
_item['confidence'] >= 80
```

**File**: `src/streetrace/dsl/codegen/visitors/expressions.py`

### Task 2.6: Implement FilterExpr Codegen
- [ ] Generate Python list comprehension
- [ ] Bind implicit `_item` variable for condition evaluation

**Example**:
```streetrace
$filtered = filter $findings where .confidence >= 80
```
→
```python
ctx.vars['filtered'] = [_item for _item in ctx.vars['findings'] if _item['confidence'] >= 80]
```

**File**: `src/streetrace/dsl/codegen/visitors/expressions.py`

### Task 2.7: Verify `+` Operator for Lists
- [ ] Test that `$a + $b` generates correct Python code
- [ ] Verify Python `list + list` concatenation works at runtime
- [ ] Test `$list + [$single_item]` pattern

**Example**:
```streetrace
$all = $all + $new_items
```
→
```python
ctx.vars['all'] = ctx.vars['all'] + ctx.vars['new_items']
```

**Note**: Grammar already supports `+`. Just need to verify codegen passes it through correctly.

### Task 2.8: Test Filter and Concat
- [ ] Test filter with simple condition: `.confidence >= 80`
- [ ] Test filter with null check: `.suggested_fix != null`
- [ ] Test filter with variable comparison: `.confidence >= $threshold`
- [ ] Test nested property: `.finding.severity == "error"`
- [ ] Test concat with `+`: `$all + $new`
- [ ] Test concat with single item: `$list + [$item]`

---

## Phase 3: Property Assignment

**Goal**: Implement `$obj.property = value` assignment.

### Task 3.1: Extend Assignment Grammar
- [ ] Allow property_access as assignment target

**Current**:
```lark
assignment: variable "=" expression
```

**Extended**:
```lark
assignment: variable "=" expression
          | property_access "=" expression  -> property_assignment
```

### Task 3.2: Add PropertyAssignment AST Node
- [ ] Add node type for property assignment
- [ ] Include target path and value

### Task 3.3: Implement PropertyAssignment Codegen
- [ ] Generate nested dictionary assignment

**Example**:
```streetrace
$review.findings = $filtered
```
→
```python
ctx.vars['review']['findings'] = ctx.vars['filtered']
```

### Task 3.4: Test Property Assignment
- [ ] Test single-level property assignment
- [ ] Test nested property assignment
- [ ] Test with schema objects

---

## Phase 4: Verification

**Goal**: Verify all agents compile and run correctly.

### Task 4.1: V1 Monolithic Verification
- [ ] Compile `agents/code-review/v1-monolithic.sr`
- [ ] Inspect generated Python code
- [ ] Run with test PR
- [ ] Verify output

### Task 4.2: V2 Parallel Verification
- [ ] If needed: Adjust v2-parallel.sr to use `run agent` instead of `call llm` in parallel blocks
- [ ] Compile `agents/code-review/v2-parallel.sr`
- [ ] Verify parallel execution happens
- [ ] Run with test PR
- [ ] Verify filter/concat operations work

### Task 4.3: V3 Hierarchical Verification
- [ ] Compile `agents/code-review/v3-hierarchical.sr`
- [ ] Verify `use` pattern works with specialists
- [ ] Run with test PR
- [ ] Verify orchestrator calls specialists correctly

---

## Completion Criteria

### Phase 1 Complete When:
- [ ] `parallel do` uses ADK ParallelAgent
- [ ] Agents run concurrently (verified via timing)
- [ ] Results correctly assigned to variables
- [ ] Clear error for unsupported statements in parallel blocks

### Phase 2 Complete When:
- [ ] `filter $list where .property` works
- [ ] `$list + $list` concatenation works
- [ ] Implicit property access (`.prop`) works in filter conditions
- [ ] Nested property access works: `.nested.prop`

### Phase 3 Complete When:
- [ ] `$obj.property = value` assignment works
- [ ] Nested property assignment works

### Project Complete When:
- [ ] V1 compiles and produces review output
- [ ] V2 compiles, runs parallel, produces review output
- [ ] V3 compiles and orchestrator uses specialists
- [ ] No modifications to agent logic required

---

## Implementation Notes

### ParallelAgent Integration

ADK ParallelAgent expects sub-agents and runs them concurrently. Key considerations:

1. **Input binding**: Each agent in parallel needs its input bound before execution
2. **Result collection**: ParallelAgent returns results in order of sub_agents
3. **Error handling**: If one agent fails, how do we handle others?

### Filter Expression Compilation

The filter expression `filter $list where .prop >= 80` compiles to a Python list comprehension:

```streetrace
$filtered = filter $findings where .confidence >= 80
```

Compilation steps:
1. `filter` keyword starts a filter expression
2. `$findings` is the list expression → `ctx.vars['findings']`
3. `where` separates list from condition
4. `.confidence >= 80` is the condition with implicit property
5. `.confidence` compiles to `_item['confidence']` (implicit loop variable)

Generated Python:
```python
ctx.vars['filtered'] = [_item for _item in ctx.vars['findings'] if _item['confidence'] >= 80]
```

**Nested properties**: `.nested.prop` → `_item['nested']['prop']`

**Comparison with variable**: `.confidence >= $threshold` → `_item['confidence'] >= ctx.vars['threshold']`

### Property Assignment Compilation

For `$review.findings = $filtered`:
1. Parse target as property access: `$review.findings`
2. Extract base variable: `review`
3. Extract property path: `['findings']`
4. Generate: `ctx.vars['review']['findings'] = ...`

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| ADK ParallelAgent API changes | Pin ADK version, add integration tests |
| Complex property paths fail | Start with single-level, add depth incrementally |
| Implicit property outside filter | Add semantic check - error if `.prop` used outside filter |
| `+` operator not working for lists | Verify early in Phase 2, fallback to explicit concat if needed |
| V2 `call llm` in parallel | Document minimal syntax change needed |

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/streetrace/dsl/grammar/streetrace.lark` | `implicit_property`, `filter_expr`, `property_assignment` |
| `src/streetrace/dsl/ast/nodes.py` | `ImplicitProperty`, `FilterExpr`, `PropertyAssignment` |
| `src/streetrace/dsl/ast/transformer.py` | Transform rules for new nodes |
| `src/streetrace/dsl/codegen/visitors/flows.py` | Rewrite `_visit_parallel_block` for ADK ParallelAgent |
| `src/streetrace/dsl/codegen/visitors/expressions.py` | `ImplicitProperty` and `FilterExpr` codegen |
| `src/streetrace/dsl/runtime/workflow.py` | Parallel execution helper |

## Agent Files to Update (after DSL implementation)

| File | Changes |
|------|---------|
| `agents/code-review/v1-monolithic.sr` | Update `filter()` syntax |
| `agents/code-review/v2-parallel.sr` | Update `filter()` and `concat()` syntax |
