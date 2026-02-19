# Task: Make Code Review Agents Work End-to-End

## Overview

The three code review agents in `./agents/code-review/` are well-designed and optimized for review quality. **The goal is to make them work without changing their structure or logic.**

This requires implementing missing DSL features and ensuring proper ADK integration.

### Agent Files (DO NOT MODIFY)

| Agent | Path | Description |
|-------|------|-------------|
| V1 Monolithic | `agents/code-review/v1-monolithic.sr` | Single-pass baseline |
| V2 Parallel | `agents/code-review/v2-parallel.sr` | Multi-agent with parallel specialists |
| V3 Hierarchical | `agents/code-review/v3-hierarchical.sr` | LLM orchestration with `use` pattern |

### Related Documents

- **Design Document**: [`docs/design/code-review-agent.md`](../../../design/code-review-agent.md)
- **ADK Patterns**: [`docs/tasks/017-dsl/agent-patterns/agentic-patterns.md`](../../017-dsl/agent-patterns/agentic-patterns.md)
- **DSL Grammar**: [`src/streetrace/dsl/grammar/streetrace.lark`](../../../../src/streetrace/dsl/grammar/streetrace.lark)

---

## DSL Feature Gap Analysis

Analysis of what the agents use vs. what's implemented:

### V1 Monolithic (`v1-monolithic.sr`)

```streetrace
# Line 139-142: parallel do with run agent
parallel do
    $pr_info = run agent pr_fetcher $input
    $diff = run agent diff_fetcher $input
end

# Line 159: filter (NEEDS SYNTAX UPDATE)
# Current:  $filtered = filter($review.findings, $f -> $f.confidence >= 80)
# New:      $filtered = filter $review.findings where .confidence >= 80

# Line 160: property assignment
$review.findings = $filtered

# Line 149-152: object literal
$full_context = {
    pr: $pr_info,
    repo_and_history: $context
}
```

### V2 Parallel (`v2-parallel.sr`)

```streetrace
# Line 483-486: parallel do with run agent
parallel do
    $pr_info = run agent pr_fetcher $input
    $diff = run agent diff_fetcher $input
end

# Line 513-517: parallel do with call llm
# NOTE: Can be rewritten to use run agent with wrapper agents
parallel do
    $security_findings = call llm security_reviewer $full_context $chunk
    $bug_findings = call llm bug_reviewer $full_context $chunk
    $style_findings = call llm style_reviewer $full_context $chunk
end

# Line 520-522: concat (NEEDS SYNTAX UPDATE)
# Current:  $all_findings = concat($all_findings, $security_findings.findings)
# New:      $all_findings = $all_findings + $security_findings.findings

# Line 550, 578: filter (NEEDS SYNTAX UPDATE)
# Current:  $high_confidence = filter($findings, $f -> $f.confidence >= 80)
# New:      $high_confidence = filter $findings where .confidence >= 80

# Current:  $fixable = filter($findings, $f -> $f.suggested_fix != null)
# New:      $fixable = filter $findings where .suggested_fix != null
```

### V3 Hierarchical (`v3-hierarchical.sr`)

```streetrace
# Line 363: use keyword for sub-agents as tools
agent:
    tools github, fs
    instruction orchestrator_instruction
    use context_builder, chunk_context_builder, security_specialist, ...
```

**No syntax changes needed for V3.**

---

## Agent Syntax Updates Required

Once DSL features are implemented, the agent files need minor syntax updates:

### V1 (`v1-monolithic.sr`)
| Line | Current | New |
|------|---------|-----|
| 159 | `filter($review.findings, $f -> $f.confidence >= 80)` | `filter $review.findings where .confidence >= 80` |

### V2 (`v2-parallel.sr`)
| Line | Current | New |
|------|---------|-----|
| 520 | `concat($all_findings, $security_findings.findings)` | `$all_findings + $security_findings.findings` |
| 521 | `concat($all_findings, $bug_findings.findings)` | `$all_findings + $bug_findings.findings` |
| 522 | `concat($all_findings, $style_findings.findings)` | `$all_findings + $style_findings.findings` |
| 550 | `filter($findings, $f -> $f.confidence >= 80)` | `filter $findings where .confidence >= 80` |
| 564 | `concat($validated, [$finding])` | `$validated + [$finding]` |
| 578 | `filter($findings, $f -> $f.suggested_fix != null)` | `filter $findings where .suggested_fix != null` |
| 591 | `concat($patches, [$patch])` | `$patches + [$patch]` |

### V3 (`v3-hierarchical.sr`)
No changes needed.

---

## Feature Status Matrix

| Feature | Used By | Grammar | AST | Codegen | Runtime | Status |
|---------|---------|---------|-----|---------|---------|--------|
| `parallel do` → **ADK ParallelAgent** | V1, V2 | ✅ | ✅ | ❌ Sequential | ❌ | **BLOCKING** |
| `filter $list where .prop` | V1, V2 | ❌ | ❌ | ❌ | ❌ | **BLOCKING** |
| `$list + $list` (concat) | V2 | ✅ | ✅ | ? | ? | Needs verification |
| `$obj.property = value` | V1 | ❌ | ❌ | ❌ | ❌ | **BLOCKING** |
| Object literals `{ k: v }` | V1, V2 | ✅ | ✅ | ? | ? | Needs verification |
| `$obj.property` read access | V1, V2 | ✅ | ✅ | ? | ? | Needs verification |
| `use` keyword | V3 | ✅ | ✅ | ✅ | ✅ | Working |
| Multiple flows | V2 | ✅ | ✅ | ✅ | ✅ | Working |
| `if ... end` blocks | V2 | ✅ | ✅ | ✅ | ✅ | Working |
| `for ... in` loops | V1, V2 | ✅ | ✅ | ✅ | ✅ | Working |
| Schema with `expecting` | V1, V2, V3 | ✅ | ✅ | ✅ | ✅ | Working |
| Prompt interpolation `$var` | All | ✅ | ✅ | ✅ | ✅ | Working |

---

## Implementation Requirements

### 1. `parallel do` → ADK ParallelAgent (CRITICAL)

**Current State**: `parallel do` generates sequential code (see `flows.py:423`).

**Required**: Use Google ADK's `ParallelAgent` for true parallel execution.

**Design Constraint**: We can limit `parallel do` to **only allow `run agent` statements**. Any `call llm` inside `parallel do` can be rewritten to use an agent wrapper. This significantly simplifies implementation.

**Expected Behavior**:
```streetrace
parallel do
    $a = run agent agent1 $input
    $b = run agent agent2 $input
end
```

Should generate code using ADK `ParallelAgent`:
```python
from google.adk.agents import ParallelAgent

parallel_agent = ParallelAgent(
    name="parallel_block_1",
    sub_agents=[agent1, agent2]
)
# Execute and collect results into $a, $b
```

**Code Pointers**:
- Current impl: `src/streetrace/dsl/codegen/visitors/flows.py:398-427`
- ADK ParallelAgent: See `docs/tasks/017-dsl/agent-patterns/agentic-patterns.md:160-177`

### 2. `filter $list where .property` Expression

**Current State**: Not implemented in grammar or runtime.

**Required**: List filtering with implicit property access.

**Decided Syntax**:
```streetrace
$filtered = filter $findings where .confidence >= 80
$high_confidence = filter $findings where .confidence >= $threshold
$fixable = filter $findings where .suggested_fix != null
```

The leading dot (`.property`) indicates property access on the implicit iterated item. This is:
- Unambiguous in the grammar
- No semantic analysis needed to resolve meaning
- Supports nested properties: `.finding.severity`

**Grammar Addition**:
```lark
# Add to expression atoms (around line 428)
?atom: literal
     | variable
     | property_access
     | function_call
     | identifier                                     -> name_ref
     | LPAR expression RPAR                           -> paren_expr
     | implicit_property

# New production for implicit property access
implicit_property: "." contextual_name ("." contextual_name)*

# Filter expression (add near function_call)
filter_expr: "filter" expression "where" expression
```

**Codegen**:
```streetrace
$filtered = filter $findings where .confidence >= 80
```
Generates:
```python
ctx.vars['filtered'] = [_item for _item in ctx.vars['findings'] if _item['confidence'] >= 80]
```

**Code Pointers**:
- Grammar: `src/streetrace/dsl/grammar/streetrace.lark` (add near line 428 for atom, ~492 for filter_expr)
- AST: `src/streetrace/dsl/ast/nodes.py` (add ImplicitProperty, FilterExpr nodes)
- Expression visitor: `src/streetrace/dsl/codegen/visitors/expressions.py`

### 3. List Concatenation with `+` Operator

**Current State**: Grammar already supports `+` in expressions. Need to verify codegen works for lists.

**Syntax** (already valid grammar):
```streetrace
$all_findings = $all_findings + $security_findings.findings
$validated = $validated + [$finding]
```

**Grammar**: Already supported via:
```lark
?additive: multiplicative (("+"|"-") multiplicative)*
```

**Verification Needed**:
Confirm expression codegen produces Python `+` that works with lists:
```python
ctx.vars['all_findings'] = ctx.vars['all_findings'] + ctx.vars['security_findings']['findings']
```

Python's `list + list` handles concatenation natively.

**Code Pointers**:
- Expression visitor: `src/streetrace/dsl/codegen/visitors/expressions.py` (verify additive handling)

### 4. Property Assignment `$obj.property = value`

**Current State**: Grammar supports property access for reading, but not assignment.

**Required**: Assign to nested object property.

**Usage in Agents**:
```streetrace
$review.findings = $filtered
```

**Implementation**:
Extend assignment to handle property targets:
```python
ctx.vars['review']['findings'] = ctx.vars['filtered']
```

**Code Pointers**:
- Grammar: `src/streetrace/dsl/grammar/streetrace.lark:350` (assignment)
- AST: `src/streetrace/dsl/ast/nodes.py` (Assignment node)

---

## Verification Items

### Object Literals `{ key: value }`

Need to verify these work correctly:
```streetrace
$full_context = {
    pr: $pr_info,
    repo_and_history: $context
}
```

**Test**: Create minimal .sr file with object literal, compile, run.

### Property Access `$obj.property`

Need to verify nested access works:
```streetrace
$security_findings.findings
$finding.confidence
$pr_info.description
```

**Test**: Access nested properties from schema results.

---

## Architecture Decision: ParallelAgent Implementation

### Constraints

1. **Only `run agent` and `call llm`** in `parallel do` blocks (per user)
2. Must work with ADK's `ParallelAgent`
3. Results must be accessible as assigned variables after block

### Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    PARALLEL BLOCK CODEGEN                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DSL:                                                            │
│  parallel do                                                     │
│      $a = run agent agent1 $input                                │
│      $b = run agent agent2 $input                                │
│  end                                                             │
│                                                                  │
│  ↓ Compile to:                                                   │
│                                                                  │
│  1. Create wrapper agents that capture input and store output    │
│  2. Create ParallelAgent with wrappers as sub_agents             │
│  3. Execute ParallelAgent                                        │
│  4. Extract results from wrappers into ctx.vars                  │
│                                                                  │
│  Generated Python:                                               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ # Create agents with bound inputs                         │  │
│  │ _parallel_agent1 = create_bound_agent(agent1, input)      │  │
│  │ _parallel_agent2 = create_bound_agent(agent2, input)      │  │
│  │                                                           │  │
│  │ # Execute in parallel                                     │  │
│  │ _parallel = ParallelAgent(                                │  │
│  │     name="parallel_1",                                    │  │
│  │     sub_agents=[_parallel_agent1, _parallel_agent2]       │  │
│  │ )                                                         │  │
│  │ _results = await execute_parallel(_parallel)              │  │
│  │                                                           │  │
│  │ # Unpack results                                          │  │
│  │ ctx.vars['a'] = _results[0]                               │  │
│  │ ctx.vars['b'] = _results[1]                               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Rejection Strategy

At compile time, reject `parallel do` blocks containing anything other than:
- `$var = run agent name $args...`
- `$var = call llm prompt $args...`

This provides clear error messages and simplifies implementation.

---

## Success Criteria

### Functional

1. `agents/code-review/v1-monolithic.sr` compiles and runs successfully
2. `agents/code-review/v2-parallel.sr` compiles and runs successfully
3. `agents/code-review/v3-hierarchical.sr` compiles and runs successfully
4. Parallel blocks execute concurrently (not sequentially)
5. All filter/concat operations work correctly
6. Property assignment works correctly

### Quality

1. No changes to agent .sr files required
2. Clear error messages for unsupported constructs in `parallel do`
3. Type-safe result handling from ParallelAgent

---

## Code Pointers Summary

| Component | Path | Relevant Lines |
|-----------|------|----------------|
| Grammar | `src/streetrace/dsl/grammar/streetrace.lark` | 325 (parallel_block), 350 (assignment), 492 (function_call) |
| AST Nodes | `src/streetrace/dsl/ast/nodes.py` | ParallelBlock, Assignment, FunctionCall |
| Transformer | `src/streetrace/dsl/ast/transformer.py` | Transform rules |
| Flow Codegen | `src/streetrace/dsl/codegen/visitors/flows.py` | 398-427 (_visit_parallel_block) |
| Expression Codegen | `src/streetrace/dsl/codegen/visitors/expressions.py` | Function call handling |
| Runtime Context | `src/streetrace/dsl/runtime/context.py` | Variable storage |
| ADK Integration | `src/streetrace/workloads/dsl_agent_factory.py` | Agent creation |
| ADK Patterns Doc | `docs/tasks/017-dsl/agent-patterns/agentic-patterns.md` | 160-177 (ParallelAgent) |
