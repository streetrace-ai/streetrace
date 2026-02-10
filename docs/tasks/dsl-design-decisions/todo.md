# Implementation Plan: DSL Design Decisions

TDD approach — write tests first for each change, then implement.

## Phase 1: Make `$` prefix optional in flow code

Make `$` optional (not removed) in flow-context variable references. Both `$var` and `var` are accepted. This avoids breaking existing `.sr` agent files and tests — old syntax keeps working, new files can omit `$`. Prompt templates always keep `$` for interpolation (unchanged, they're opaque strings).

**Strategy**: The `variable` grammar rule gains an alternate path that accepts bare names. The transformer strips `$` if present, producing a consistent `VarRef(name="foo")` regardless of whether the source wrote `$foo` or `foo`. All downstream layers (semantic, codegen, runtime) see the same node — no changes needed there beyond removing `lstrip("$")` calls that are now redundant since the transformer normalizes.

### 1.1 Tests for bare variable syntax

- [ ] **Test file**: `tests/dsl/test_bare_variables_grammar.py`
  - Parse `pr_context = run agent fetcher` (assignment with bare name)
  - Parse `$pr_context = run agent fetcher` (assignment with `$` — still works)
  - Parse `for chunk in chunks do` (for loop with bare name)
  - Parse `for $chunk in $chunks do` (for loop with `$` — still works)
  - Parse `push item to results` (push with bare names)
  - Parse `all_findings = all_findings + security_findings` (expression with bare names)
  - Parse `return final` (return with bare name)
  - Parse `if result.valid:` (if with bare property access)
  - Parse `high_confidence = filter findings where .confidence >= 80` (filter with bare name)
  - Verify prompt bodies still use `$var` for interpolation (unchanged)
  - Verify mixing `$` and bare in the same flow works (transitional)

- [ ] **Test file**: `tests/dsl/test_bare_variables_transformer.py`
  - Bare name in assignment target → `Assignment(target="pr_context")`
  - `$`-prefixed name in assignment target → `Assignment(target="pr_context")` (same output)
  - Bare name in for loop → `ForLoop(variable="chunk")`
  - Bare name in expression → `VarRef(name="pr_context")`
  - Bare name in property access → `PropertyAccess` with VarRef base

- [ ] **Test file**: `tests/dsl/test_bare_variables_semantic.py`
  - Bare names resolve from global scope
  - Assignment defines variable in scope (bare name)
  - Undefined bare name triggers error
  - Bare names work in all statement types

- [ ] **Test file**: `tests/dsl/test_bare_variables_codegen.py`
  - Assignment generates `ctx.vars['name'] = value`
  - VarRef generates `ctx.vars['name']`
  - For loop generates `for _item_name in ctx.vars['items']:`
  - Push generates `ctx.vars['target'].append(value)`

### 1.2 Grammar changes

- [ ] Make `$` optional in `variable` rule — accept both `$name` and `name` in flow context
- [ ] Add `"with"`, `"produces"`, and `"prompt"` to `contextual_keyword` (reserved for later phases)
- [ ] All flow-context rules (`assignment`, `run_stmt`, `call_stmt`, `for_loop`, `push_stmt`) accept the updated `variable` rule — no per-rule changes needed

### 1.3 Transformer changes

- [ ] Ensure `VarRef.name` is always stored without `$` prefix (strip in transformer)
- [ ] For loop variable, assignment target, push target — all normalize by stripping `$` if present

### 1.4 Semantic analyzer changes

- [ ] Remove all `.lstrip("$")` calls — transformer now guarantees no `$` prefix
- [ ] No other changes (scope resolution works the same)

### 1.5 Code generator changes

- [ ] Remove all `.lstrip("$")` calls in `flows.py` — transformer guarantees clean names
- [ ] Verify generated Python is valid for both old and new syntax inputs

### 1.6 Existing tests and agents

- [ ] All existing tests pass without modification (old `$` syntax still accepted)
- [ ] All existing `.sr` agent files compile without errors
- [ ] New tests cover the bare-name path

## Phase 2: `with` keyword for invocations

Replace multi-arg positional syntax with single `with` input.

### 2.1 Tests

- [ ] **Test file**: `tests/dsl/test_with_keyword.py`
  - Parse `result = run agent reviewer with review_prompt`
  - Parse `run agent fetcher with input_prompt`
  - Parse `result = call llm deduplicator with validated_findings`
  - Parse `run agent fetcher` (no with — uses agent default prompt)
  - Transformer produces `RunStmt(input=NameRef("review_prompt"))` or similar
  - Code gen produces `ctx.run_agent('reviewer', ctx.vars['review_prompt'])`
  - Semantic: `with` expression must reference defined name

### 2.2 Grammar changes

- [ ] Modify `run_stmt` rules to use `("with" expression)?` instead of `expression*`
- [ ] Modify `call_stmt` rules to use `("with" expression)?` instead of `expression*`

### 2.3 AST changes

- [ ] Change `RunStmt.args: list[AstNode]` to `RunStmt.input: AstNode | None`
- [ ] Change `CallStmt.args: list[AstNode]` to `CallStmt.input: AstNode | None`

### 2.4 Transformer changes

- [ ] Update `run_stmt` / `call_stmt` transform to extract single `with` expression

### 2.5 Code generator changes

- [ ] Update `_visit_run_stmt` in `flows.py` to use single input
- [ ] Update `_visit_call_stmt` in `flows.py` to use single input

### 2.6 Runtime changes

- [ ] `ctx.run_agent()` — single input argument instead of `*args`
- [ ] `DslAgentWorkflow.run_agent()` — single prompt text input

## Phase 3: Agent `prompt` and `produces` fields

### 3.1 Tests

- [ ] **Test file**: `tests/dsl/test_agent_prompt_produces.py`
  - Parse agent with `prompt` property
  - Parse agent with `produces` property
  - Parse agent with both
  - Transformer produces `AgentDef(prompt="my_prompt", produces="result_var")`
  - Semantic: validate `prompt` references defined prompt
  - Semantic: validate `produces` is a valid name
  - Code gen: emit `'prompt': 'my_prompt'` and `'produces': 'result_var'` in agent dict
  - Runtime: `run agent X` without `with` uses agent's prompt field
  - Runtime: `run agent X` without assignment uses agent's produces field

### 3.2 Grammar changes

- [ ] Add `"prompt" NAME _NL -> agent_prompt` to `agent_property`
- [ ] Add `"produces" NAME _NL -> agent_produces` to `agent_property`

### 3.3 AST changes

- [ ] Add `prompt: str | None = None` to `AgentDef`
- [ ] Add `produces: str | None = None` to `AgentDef`

### 3.4 Transformer changes

- [ ] Add `agent_prompt` transform method
- [ ] Add `agent_produces` transform method
- [ ] Include in agent_body assembly

### 3.5 Semantic analyzer changes

- [ ] Validate agent `prompt` reference points to a defined prompt
- [ ] Track `produces` as variable definition when agent invoked without assignment

### 3.6 Code generator changes

- [ ] Emit `'prompt'` and `'produces'` in agent dict
- [ ] When generating `run agent X` without target, check if agent has `produces` and auto-assign

### 3.7 Runtime changes

- [ ] When `run agent X` has no explicit input, resolve agent's `prompt` from context
- [ ] When result needs auto-assignment, use `produces` variable name

## Phase 4: Remove flow parameters

### 4.1 Tests

- [ ] **Test file**: `tests/dsl/test_no_flow_params.py`
  - Parse `flow validate_all:` (no params)
  - Reject `flow validate_all input:` with bare name params (params removed)
  - Semantic: flow body reads from global scope
  - Code gen: flow method has no param initialization
  - `run validate_all` without args works

### 4.2 Grammar changes

- [ ] Remove `flow_params` from `flow_def` rule
  ```lark
  flow_def: "flow" flow_name ":" _NL _INDENT flow_body _DEDENT
  ```

### 4.3 AST changes

- [ ] `FlowDef.params` always empty (or remove field — **keep for compat, default to `[]`**)

### 4.4 Semantic analyzer changes

- [ ] Remove flow parameter scope creation in `_validate_flow`

### 4.5 Code generator changes

- [ ] No changes needed — already generates `flow_name(self, ctx)` without params

### 4.6 Update existing tests

- [ ] Update `tests/dsl/test_flow_parameters.py` — tests now verify params are rejected

## Phase 5: Array `expecting` type

### 5.1 Tests

- [ ] **Test file**: `tests/dsl/test_expecting_array.py`
  - Parse `prompt reviewer expecting Finding[]`
  - Parse `prompt reviewer expecting Finding` (single, still works)
  - Transformer: `PromptDef(expecting="Finding[]")` for array
  - Semantic: validate schema name (strip `[]`) exists
  - Code gen: emit `schema='Finding[]'` in PromptSpec
  - Runtime: parse JSON array, validate each element, return list of dicts

### 5.2 Grammar changes

- [ ] Update `prompt_expecting` rule:
  ```lark
  prompt_modifier: ...
                 | "expecting" expecting_type -> prompt_expecting

  expecting_type: NAME -> expecting_single
               | NAME LSQB RSQB -> expecting_array
  ```

### 5.3 Transformer changes

- [ ] `prompt_expecting` → handle both single and array forms
- [ ] Store as `"Finding[]"` string for array, `"Finding"` for single

### 5.4 Semantic analyzer changes

- [ ] Strip `[]` suffix when validating schema reference

### 5.5 Runtime changes

- [ ] In `_execute_llm_with_validation`: detect `[]` suffix
- [ ] Parse as JSON array, validate each element against schema
- [ ] Return `list[dict]` instead of `dict`

## Phase 6: Prompt composition

### 6.1 Tests

- [ ] **Test file**: `tests/dsl/test_prompt_composition.py`
  - Prompt `$no_inference` in another prompt resolves to no_inference prompt body
  - Flow variable overrides prompt name (variable takes precedence)
  - `resolve()` method on WorkflowContext checks vars then prompts

### 6.2 Runtime changes

- [ ] Add `resolve(name: str) -> str` method to `WorkflowContext`
  - Check `ctx.vars[name]` first
  - Then check `ctx._prompts[name]` and evaluate body
  - Return stringified value

### 6.3 Code generator changes

- [ ] Change `_process_prompt_body` to generate `{ctx.resolve('name')}` instead of `{ctx.stringify(ctx.vars['name'])}`

## Phase 7: Refactor `v2-parallel.sr`

### 7.1 Apply all new syntax rules

- [ ] Remove all `$` prefixes from flow code
- [ ] Replace multi-arg `run agent X $a $b` with `run agent X with prompt_name`
- [ ] Add `prompt` field to agents that need default prompts
- [ ] Add `produces` field to agents that declare outputs
- [ ] Remove flow parameters from `validate_all`, `generate_all_patches`
- [ ] Use `expecting Finding[]` for array expectations
- [ ] Verify prompt composition works (e.g., `$no_inference` in prompts)
- [ ] Fix any existing syntax errors in the agent file

### 7.2 E2E verification

- [ ] Compile refactored `v2-parallel.sr` without errors
- [ ] Run the agent and verify log strings appear in `./streetrace.log`:
  - `V2 Parallel: Starting multi-agent review...`
  - `Phase 1: Fetch project description and PR Info`
  - `Phase 2: Get Diff Chunks`
  - `Phase 3: Fetch requirements`
  - `Phase 4 [CHUNK LOOP]: Build historical context`
  - `Phase 5 [CHUNK LOOP]: Run analyzers`
  - `Phase 6: Validate chunk findings`
  - `Phase 7: Deduplicating...`
  - `Phase 8: Generating patches...`
  - `Phase 9: Compiling final review...`
  - `Review complete!`
- [ ] Verify all sub-agents and flows execute properly

## Phase 8: Cleanup and validation

- [ ] Run `make check` — all tests pass, lint clean, types valid
- [ ] Run existing DSL tests — no regressions
- [ ] Update `test_flow_parameters.py` for new semantics
- [ ] Verify no `$` in generated flow code (except prompt template internals)

## Implementation Order

Phases 1-6 are ordered by dependency:
- **Phase 1** (bare vars) is foundational — most other changes depend on it
- **Phase 2** (`with` keyword) depends on Phase 1 (bare names in invocations)
- **Phase 3** (prompt/produces) depends on Phase 2 (with keyword semantics)
- **Phase 4** (no flow params) depends on Phase 1 (bare names replace params)
- **Phase 5** (array expecting) is independent — can be done anytime
- **Phase 6** (prompt composition) is independent — can be done anytime
- **Phase 7** (refactor SR file) depends on all above
- **Phase 8** (cleanup) is final

Recommended parallel tracks:
- **Track A**: Phase 1 → Phase 2 → Phase 3 → Phase 4
- **Track B**: Phase 5 + Phase 6 (independent)
- **Merge**: Phase 7 → Phase 8
