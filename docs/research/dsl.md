# DSL Design Decisions

Design decisions for the StreetRace DSL, recorded from design discussions.

## Scope and Variable Model

### Single flat global context

All variables live in a single flat namespace (`ctx.vars`). There is no local scope,
no module scope, no block scope. Every variable assigned anywhere is visible everywhere
within the same workflow execution.

This works because:

- Single file, single author — no multi-team module boundaries to protect.
- No recursion or threads — flows are sequential with explicit `parallel do` blocks.
- Short variable lifetimes — an 800-line agent file has ~15-30 variables, not thousands.
- Prompts read variables but don't mutate them — data flows one direction: flow → context → prompt.

### No `$` prefix in flow code

Variables in flow code use bare names without a `$` prefix:

```
pr_context = run agent pr_context_fetcher
all_findings = all_findings + security_findings
for chunk in chunks do
```

The `$` prefix is reserved for **prompt templates only**, where it marks interpolation:

```
prompt reviewer: """Review $pr_context focusing on $changes."""
```

This mirrors shell, Terraform, and Kotlin: bare names in code, sigil in templates.
The `$` means "interpolate from context" in a string, not "this is a variable" in code.

**Rationale**: Double-clicking or Ctrl+Arrow in VS Code does not select the `$` symbol,
making editing tedious. The `$` prefix in code is syntactic noise — the parser can
disambiguate via position and keywords.

### `$` in templates is the safety boundary

A prompt template can only access a variable if the template author explicitly writes
`$var_name`. Adding a new variable in a flow does not affect any prompt unless a prompt
already references that name. The template IS the filter — it pulls specific named
variables, not the entire scope.

### Variable cascading

Variables set in one flow are visible in called flows. Since all variables share a single
flat context, calling a sub-flow does not create a new scope — the sub-flow reads and
writes the same `ctx.vars`.

### JSON stringification for objects

When a `$var` reference in a prompt template resolves to a dict or list, it is serialized
as JSON. Strings, ints, and floats use `str()`. This is handled by `ctx.stringify()`.

```
# In a prompt template:
# $findings resolves to JSON: [{"file": "main.py", "line": 42}]
# $count resolves to string: "5"
```

### Prompt composition

Prompts can reference other prompts by name using `$`. A prompt body is effectively a
string value in the global namespace:

```
prompt no_inference: """ONLY get factual information, do not analyze or infer."""

prompt reviewer_instruction: """You are a code reviewer.
$no_inference
"""
```

`$no_inference` in the second prompt resolves to the body of `prompt no_inference`.
Variable assignments in flows can override prompt names — flow variables take precedence
(more specific scope wins).

## Agent Model

### Agent = identity + capabilities

An agent definition contains:

- `instruction` — system prompt (permanent identity, always applies)
- `tools` — available tools
- `description` — routing metadata for delegation (other agents read this)
- `prompt` — default user message template (see below)
- `produces` — default output variable name (see below)
- `delegate` / `use` — agent composition

### `prompt` field on agents (default user message)

Agents can have a `prompt` field that defines the default user message template. This is
the "default `with`" — if you invoke the agent without `with`, this prompt is used.

```
agent patch_generator:
    tools github, fs
    instruction patch_generator_instruction
    prompt patch_generator_prompt

# Uses agent's default prompt (resolved from ambient context)
run agent patch_generator

# Overrides with a different prompt
run agent patch_generator with custom_prompt
```

**Why `prompt` on the agent**: Agent responses are fragments, not prompts. The agent needs
a template to convert raw data into a proper instruction. This template is tightly coupled
with the agent's identity — it defines HOW the agent wants to receive work. Placing it on
the agent keeps all relevant parts in one place.

**Delegation behavior**: When an agent is used via `delegate` or `use`, the parent agent
controls the input. The `prompt` field is not used. This is analogous to a default function
argument — irrelevant when the caller provides a value.

### `produces` field on agents (default output variable)

Agents can declare what context variable they write their result to:

```
agent pr_context_fetcher:
    instruction pr_context_fetcher_instruction
    produces pr_context

flow main:
    run agent pr_context_fetcher              # result → pr_context (from produces)
    security = run agent security_reviewer    # result → security (flow override)
```

The flow can override the output name with explicit assignment. `produces` is the default
— explicit assignment takes precedence.

This creates symmetry: agents declare inputs (via `$var` in prompt templates) and
outputs (via `produces`).

### Late-bound instruction evaluation

Agent instructions are evaluated at **invocation time** with the full workflow context,
not at agent creation time. This means `$var` references in instructions resolve to
current context values when the agent is actually called.

## Invocation Syntax

### `with` keyword for input

The `with` keyword provides the user message (single input) to an agent or LLM call:

```
run agent pr_context_fetcher with input_prompt
run agent patch_generator with custom_prompt
call llm deduplicator with validated_findings
```

For agents with a `prompt` field, `with` is optional (overrides the default).
For agents without a `prompt` field, `with` is required.

### Verbs are kept

Three distinct invocation verbs communicate behavioral intent:

- `run agent X` — spawns an agent (may use tools, multi-turn)
- `run flow_name` — calls a flow (deterministic orchestration)
- `call llm prompt_name` — single LLM call (one-shot)

These have different performance and behavioral characteristics. The verb tells the
reader what kind of operation is happening and helps the LSP offer contextual completions.

### No flow parameters

Flows do not take parameters. They read from the shared global context:

```
# Instead of: flow validate_all $pr_context $findings:
flow validate_all:
    # reads pr_context and findings from context
    high_confidence = filter findings where .confidence >= 80
```

This eliminates the ambiguity between multi-word flow names and parameter lists in the
grammar, and is consistent with the ambient context model.

## Prompt Templates

### Ambient context resolution

Prompt templates resolve `$var` references from the ambient context at evaluation time.
No explicit argument passing to templates is needed:

```
prompt reviewer_prompt: """Review $pr_context focusing on $changes."""

flow main:
    pr_context = run agent pr_context_fetcher
    changes = run agent diff_fetcher
    # reviewer_prompt auto-resolves $pr_context and $changes from context
    run agent reviewer with reviewer_prompt
```

### `format` keyword (optional, for eager snapshots)

With ambient context resolution, `format` is generally unnecessary — templates
auto-resolve when used. The `format` keyword is reserved for eager evaluation (freezing
a template's values at a specific point in the flow), but is not essential to the core
model.

### Prompt declarations with metadata

Prompts support declaration/definition separation for file organization:

```
# Declaration at top (metadata only)
prompt security_reviewer expecting Finding[] using model "main"

# Definition at bottom (body text)
prompt security_reviewer: """You are a SECURITY SPECIALIST..."""
```

## Grammar Changes (from current state)

### Removing `$` from flow code

The `$` prefix is removed from variable names in flow code. All cases are disambiguated
by surrounding keywords and operators:

| Context | Disambiguation |
|---|---|
| `foo = expr` (assignment) | `=` operator |
| `for foo in items do` | `for`, `in`, `do` keywords |
| `push expr to foo` | `to` keyword |
| `filter items where ...` | `filter`, `where` keywords |
| `return foo` | `return` keyword |
| `if result.valid:` | `if` keyword |
| `run agent X with foo` | `with` keyword |
| `foo.bar` in expressions | Treated as variable property access |

The `name_ref` and `var_ref` AST distinction is merged — every bare name in an
expression resolves from the global context.

### `with` keyword on invocations

Added to `run agent`, `run` (flow), and `call llm` to provide input:

```
result = run agent reviewer with review_prompt
run validate_all
call llm deduplicator with findings
```

### `prompt` field on agents

New agent property for the default user message template:

```
agent patch_generator:
    instruction patch_generator_instruction
    prompt patch_generator_prompt
```

### `produces` field on agents

New agent property for the default output variable name:

```
agent pr_context_fetcher:
    instruction pr_context_fetcher_instruction
    produces pr_context
```

### Flow parameters removed

The `flow_params` grammar rule is removed. Flows read from ambient context.

## Design Principles

1. **Flat global context**: One namespace, one scope. Simple to understand in single-file
   agent definitions.

2. **`$` means interpolation, not "variable"**: `$` only appears in prompt templates to
   mark context variable references.

3. **Templates are filters**: A prompt only accesses variables it explicitly names with
   `$`. No accidental leakage.

4. **Agents declare defaults**: `prompt` (default input) and `produces` (default output)
   are defaults that flows can override. Like default function arguments.

5. **Verbs communicate intent**: `run agent`, `run` (flow), `call llm` tell the reader
   and tooling what kind of operation is happening.

6. **Flows are imperative orchestration**: Sequencing, loops, branching, accumulation.
   Agents and prompts are declarative definitions. Flows wire them together.

7. **LSP-friendly**: Agent `produces` declarations and prompt `$var` references give the
   LSP a dependency graph for static analysis — warning when a flow invokes an agent
   before its required context variables are set.
