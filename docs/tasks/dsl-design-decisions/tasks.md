# DSL Design Decisions Implementation

## Goal

Implement the DSL design changes described in [docs/research/dsl.md](../../research/dsl.md) plus support for array types in `expecting` (e.g., `expecting Finding[]`). Then refactor `agents/code-review/v2-parallel.sr` to follow all new rules.

## Design Reference

- **Design doc**: `docs/research/dsl.md`
- **Agent file**: `agents/code-review/v2-parallel.sr`

## Current State Analysis

The DSL compiler pipeline is:

1. **Grammar** (`src/streetrace/dsl/grammar/streetrace.lark`) — Lark EBNF, Earley parser
2. **Transformer** (`src/streetrace/dsl/ast/transformer.py`) — Lark tree → typed AST nodes
3. **AST Nodes** (`src/streetrace/dsl/ast/nodes.py`) — frozen dataclasses
4. **Semantic Analyzer** (`src/streetrace/dsl/semantic/analyzer.py`) — reference/scope validation
5. **Code Generator** (`src/streetrace/dsl/codegen/`) — AST → Python source
   - `visitors/workflow.py` — class structure, prompts, agents, schemas
   - `visitors/flows.py` — flow methods, control flow
   - `visitors/expressions.py` — expression code gen
6. **Runtime** (`src/streetrace/dsl/runtime/`) — execution context, agent/LLM calls
   - `context.py` — WorkflowContext with vars, run_agent, call_llm
   - `workflow.py` — DslAgentWorkflow base class

## Changes Required

### 1. Make `$` prefix optional in flow code variables

**Current**: `$var` required everywhere in flow code
**Target**: `$` is optional in flow code — both `$var` and `var` are accepted. Prompt templates keep `$var` for interpolation (unchanged).

**Rationale for optional instead of removed**: Removing `$` outright would break all existing `.sr` agent files and their corresponding tests. Making it optional allows a gradual migration: new files omit `$`, old files keep working until individually updated.

#### Affected components:

| Component | Change |
|-----------|--------|
| **Grammar** (`streetrace.lark:476-478`) | `variable` rule gains an alternate path accepting bare names (no `$`). Both `$name` and `name` match. |
| **Transformer** (`transformer.py`) | `var_ref` / `var_dotted` handlers always strip `$` if present, guaranteeing `VarRef.name` has no prefix. |
| **AST Nodes** (`nodes.py`) | No structural changes. `VarRef.name` consistently stores without `$`. |
| **Semantic Analyzer** (`analyzer.py:630,690,720,782,812`) | All `.lstrip("$")` calls become redundant (transformer already normalized). Remove them. |
| **Code Generator** (`flows.py:222,288,364,395,409`) | All `.lstrip("$")` calls removed — transformer guarantees clean names. |
| **Expressions** (`expressions.py:100`) | VarRef visitor already strips `$`. Works as-is once VarRef.name has no `$`. |

**Key design constraint**: The `$` prefix is **kept in prompt templates** for interpolation. This is already naturally separated — prompt bodies are `TRIPLE_QUOTED_STRING` terminals (opaque to the parser). The `$` replacement happens in `_process_prompt_body()` via regex on the raw string. No prompt-side changes needed.

**Grammar approach**: Make `$` optional in the existing `variable` rule:

```lark
// $ is optional in flow code — both $name and name accepted
variable: "$"? var_name -> var_ref
        | "$"? var_name ("." contextual_name)+ -> var_dotted
```

All flow-context rules (`assignment`, `run_stmt`, `call_stmt`, `for_loop`, `push_stmt`) already use `variable` — no per-rule changes needed. The transformer normalizes by stripping `$` if present.

### 2. `with` keyword for agent/LLM invocation input

**Current**: `$result = run agent reviewer $input $context` (positional args)
**Target**: `result = run agent reviewer with review_prompt` (single `with` input)

#### Grammar changes:

```lark
// Agent invocation with optional 'with' keyword
run_stmt: flow_variable "=" "run" "agent" identifier ("with" expression)? escalation_handler?
        | "run" "agent" identifier ("with" expression)? escalation_handler?
        | flow_variable "=" "run" identifier ("with" expression)? escalation_handler? -> run_flow_assign
        | "run" identifier ("with" expression)? escalation_handler? -> run_flow

// Call LLM with optional 'with' keyword
call_stmt: flow_variable "=" "call" "llm" identifier ("with" expression)? call_modifiers?
         | "call" "llm" identifier ("with" expression)? call_modifiers?
```

**AST changes**: `RunStmt.args` becomes a single optional `input: AstNode | None` field (the `with` expression). Same for `CallStmt`.

**Backward compat**: Keep supporting positional args during transition? **No** — the design doc explicitly replaces multi-arg with single `with`. This is a breaking change for existing `.sr` files. The v2-parallel.sr will be refactored.

### 3. `prompt` field on agents (default user message)

**Current**: Not implemented.
**Target**: `prompt` property specifying default `with` input.

#### Grammar:

```lark
agent_property: ...existing...
              | "prompt" NAME _NL -> agent_prompt
```

#### AST:

Add `prompt: str | None = None` to `AgentDef`.

#### Semantic validation:

Validate that agent's `prompt` references a defined prompt.

#### Code generation:

Emit `'prompt': 'prompt_name'` in agent dict.

#### Runtime:

When `run agent X` is called without `with`, use agent's `prompt` field to resolve the default user message. If agent has no `prompt` and no `with`, the agent receives no user message (current behavior).

### 4. `produces` field on agents (default output variable)

**Current**: Not implemented.
**Target**: `produces` declares default output variable.

#### Grammar:

```lark
agent_property: ...existing...
              | "produces" NAME _NL -> agent_produces
```

#### AST:

Add `produces: str | None = None` to `AgentDef`.

#### Code generation:

When `run agent X` without explicit assignment and agent has `produces`, auto-assign:
```python
ctx.vars['pr_context'] = ctx.get_last_result()
```

#### Semantic validation:

Track `produces` as variable definition in flow scope when agent is invoked without assignment.

### 5. Remove flow parameters

**Current**: `flow validate_all $pr_context $findings:` (explicit params)
**Target**: `flow validate_all:` (reads from ambient context)

#### Grammar:

Remove `flow_params` rule from `flow_def`.

```lark
flow_def: "flow" flow_name ":" _NL _INDENT flow_body _DEDENT
```

#### AST:

`FlowDef.params` becomes always-empty list (or removed).

#### Semantic analyzer:

No longer defines parameters in flow scope. All variables resolve from global scope (which is already how `ctx.vars` works at runtime).

#### Runtime:

`run_flow()` no longer needs to pass args to flow. The flow reads from `ctx.vars` directly. This is already how it works — the args parameter on `run_flow()` is unused (line 420: `_ = args`).

### 6. `expecting` with array types (e.g., `Finding[]`)

**Current**: `expecting Finding` — single schema name.
**Target**: `expecting Finding[]` — array of schema objects.

#### Grammar:

```lark
prompt_modifier: ...existing...
               | "expecting" expecting_type -> prompt_expecting

expecting_type: NAME -> expecting_single
              | NAME LSQB RSQB -> expecting_array
```

#### AST:

Change `PromptDef.expecting` from `str | None` to a structured type:
```python
@dataclass
class ExpectingType:
    schema_name: str
    is_array: bool = False
```

Or keep as string and use naming convention: `"Finding[]"` vs `"Finding"`.

**Decision**: Use naming convention (string with `[]` suffix) for minimal change. Parse it where needed.

#### Code generation:

In `_emit_prompts`, detect `[]` suffix and emit `schema='Finding[]'`.

#### Runtime:

In `call_llm` → `_execute_llm_with_validation`, when schema is `Name[]`:
- Parse response as JSON array
- Validate each element against the schema
- Return list of validated dicts

### 7. Prompt composition (`$prompt_name` in templates)

**Current**: `$var` in prompts resolves from `ctx.vars` only.
**Target**: `$prompt_name` in a prompt body resolves to that prompt's body text, with flow variables taking precedence.

#### Runtime change:

In `_evaluate_prompt_text` / `_process_prompt_body`, resolution order:
1. Check `ctx.vars[name]` — flow variable (takes precedence)
2. Check `ctx._prompts[name]` — prompt body (compose prompts)

This affects `_process_prompt_body` in `workflow.py` codegen. The generated f-string needs to try vars first, then prompts:

```python
# Instead of:
{ctx.stringify(ctx.vars['no_inference'])}
# Generate:
{ctx.resolve('no_inference')}
```

Add `resolve(name)` method to `WorkflowContext` that checks vars first, then prompts.

### 8. `format` keyword (eager snapshot)

**Current**: Not implemented.
**Target**: Reserved but not essential. **Skip for now** — the design doc says it's not essential to the core model.

## Impact Summary

| File | Estimated Changes |
|------|-------------------|
| `streetrace.lark` | Grammar rules for bare vars, with keyword, agent prompt/produces, no flow params, expecting array |
| `nodes.py` | AgentDef gets prompt/produces fields, ExpectingType or string convention |
| `transformer.py` | New transform rules for flow_variable, with keyword, agent prompt/produces |
| `analyzer.py` | Validate agent prompt/produces refs, remove flow param scope, with-keyword validation |
| `flows.py` | Remove `$` stripping, handle `with` keyword, `produces` auto-assign |
| `expressions.py` | Minor — VarRef already strips `$` |
| `workflow.py` (codegen) | Emit agent prompt/produces, prompt composition in body processing |
| `context.py` | Add `resolve()` method for prompt composition, handle array schemas |
| `workflow.py` (runtime) | Use agent `prompt` for default input |
| `v2-parallel.sr` | Full refactor to new syntax |

## Risk Assessment

**Low risk**: Making `$` optional in flow code — grammar accepts both forms, transformer normalizes. All existing tests and agents continue working. New bare-name path gets new tests.
**Low risk**: Adding `prompt`, `produces` to agents — additive changes.
**Medium risk**: Removing flow parameters — existing `.sr` files using params will break. Only affects `v2-parallel.sr` in our codebase.
**Low risk**: `with` keyword — replaces multi-arg with single input. Clear grammar change.
**Low risk**: Array `expecting` — isolated to schema validation path.

No significant re-design required. All changes are localized to the DSL compiler pipeline and can be implemented incrementally through the grammar → transformer → AST → semantic → codegen → runtime layers.
