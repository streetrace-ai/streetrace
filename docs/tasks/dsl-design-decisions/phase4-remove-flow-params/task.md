# Phase 4: Remove Flow Parameters

## Overview

Remove the `flow_params` grammar rule from flow definitions. Flows no longer accept explicit parameters -- they read from ambient context (`ctx.vars`). This is a breaking change for existing `.sr` files that use flow parameters.

## Design Reference

- [DSL Design Decisions Tasks](../tasks.md) -- Phase 5 (Remove flow parameters)
- [Implementation Plan](../todo.md) -- Phase 4

## Key Implementation Requirements

1. Remove `flow_params` from `flow_def` grammar rule
2. Delete the `flow_params: variable+` rule entirely
3. Reorder `FlowDef` dataclass fields so `params` (with default) comes after `body` (no default)
4. Update transformer to not extract flow params from children
5. Remove `flow_params` transformer method
6. Remove parameter scope creation in semantic analyzer `_validate_flow`
7. Update all code constructing `FlowDef` positionally across codebase
8. Remove `flow_params` entry from `vulture_allow.txt`

## Success Criteria

- `flow validate_all:` (no params) parses successfully
- `flow validate_all $input:` (with params) fails to parse
- `flow validate_all input:` (bare name params) fails to parse
- `FlowDef.params` always defaults to empty list
- Semantic analyzer validates flow body against global scope (no param scope)
- Code generator produces `async def flow_name(self, ctx: WorkflowContext)` without parameter initialization
- `run validate_all` without args works
- All existing tests pass after FlowDef field reordering
- `make check` passes clean

## Acceptance Tests

- Parsing a flow without params produces `FlowDef(name="...", body=[...], params=[])`
- Parsing a flow with `$`-prefixed params raises a parse error
- Parsing a flow with bare-name params raises a parse error
- Undefined variables in flow body still raise semantic errors
- Variables defined in `on start` handler are accessible in flow body
- Generated code has no parameter initialization logic
- End-to-end: compile a flow definition without params
