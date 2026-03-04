# Task Definition: DSL Agentic Patterns Implementation

| Field | Value |
|-------|-------|
| **Feature ID** | 017-dsl-compiler-patterns |
| **Feature Name** | Multi-Agent Patterns for Streetrace DSL |
| **Status** | Active |
| **Created** | 2026-01-21 |
| **Depends On** | 017-dsl-compiler (base implementation) |

## Overview

Implement multi-agent pattern support in the Streetrace DSL compiler to enable full compatibility with Google ADK's multi-agent capabilities. This includes support for:
- Coordinator/Dispatcher pattern (`delegate` keyword)
- Hierarchical Task Decomposition pattern (`use` keyword)
- Iterative Refinement pattern (`loop` block)

## Design Documents

- [Agentic Patterns Documentation](./017-dsl-compiler/agentic-patterns.md)
- [Implementation Plan](./017-dsl-compiler/agentic-patterns-todo.md)
- [DSL Compiler Testing Guide](../testing/dsl/017-dsl-compiler-testing.md)

## Implementation Requirements

### 1. Grammar Changes

Add three new constructs to the DSL grammar (`src/streetrace/dsl/grammar/streetrace.lark`):

1. **`delegate` keyword**: Agent property for coordinator pattern
   ```lark
   agent_property: ... | "delegate" name_list _NL -> agent_delegate
   ```

2. **`use` keyword**: Agent property for hierarchical pattern
   ```lark
   agent_property: ... | "use" name_list _NL -> agent_use
   ```

3. **`loop` block**: Flow statement for iterative refinement
   ```lark
   loop_block: "loop" "max" INT "do" _NL _INDENT flow_body _DEDENT "end" _NL?
             | "loop" "do" _NL _INDENT flow_body _DEDENT "end" _NL?
   ```

### 2. AST Node Changes

Update `src/streetrace/dsl/ast/nodes.py`:

```python
@dataclass
class AgentDef:
    # ... existing fields ...
    delegate: list[str] | None = None  # NEW: sub_agents for coordinator
    use: list[str] | None = None       # NEW: AgentTool for hierarchical

@dataclass
class LoopBlock:
    """Loop block for iterative refinement."""
    max_iterations: int | None  # None for unlimited
    body: list[AstNode]
    meta: SourcePosition | None = None
```

### 3. AST Transformer Changes

Update `src/streetrace/dsl/ast/transformer.py`:

- Add `agent_delegate` transformer method
- Add `agent_use` transformer method
- Add `loop_block` transformer method
- Update `agent_def` to collect delegate and use properties

### 4. Semantic Analysis

Update `src/streetrace/dsl/semantic/analyzer.py`:

- Validate `delegate` references exist as defined agents
- Validate `use` references exist as defined agents
- Detect circular agent references (E0011)
- Warn if agent has both `delegate` and `use` (unusual pattern)
- Validate loop block body statements
- Warn if loop has no exit condition and no max_iterations

### 5. Code Generation

Update `src/streetrace/dsl/codegen/`:

- Generate `sub_agents=[...]` for `delegate` keyword
- Generate `tools=[AgentTool(...)]` for `use` keyword
- Generate `LoopAgent` wrapper for `loop` blocks
- Add imports for `agent_tool` and `LoopAgent`

### 6. Example Files

Create examples in `agents/examples/dsl/`:

- `coordinator.sr` - Coordinator/Dispatcher pattern
- `hierarchical.sr` - Hierarchical task decomposition
- `iterative.sr` - Iterative refinement with loop
- `combined.sr` - Multiple patterns combined

## Success Criteria

1. All example files validate successfully with `streetrace check`
2. `streetrace dump-python` generates correct ADK code:
   - `delegate` → `sub_agents=[...]`
   - `use` → `tools=[AgentTool(...)]`
   - `loop` → `LoopAgent` wrapper
3. Semantic analysis catches:
   - Undefined agent references (E0001)
   - Circular agent references (E0011)
4. All unit tests pass with >95% coverage
5. No regression in existing functionality
6. Documentation is complete and accurate

## Dependencies

### External
- Google ADK with support for:
  - `LlmAgent` with `sub_agents` parameter
  - `google.adk.tools.agent_tool.AgentTool`
  - `google.adk.agents.LoopAgent`

### Internal
- Base DSL compiler (017-dsl-compiler)
- Semantic analyzer infrastructure
- Code generator visitor pattern

## Testing Strategy

### Unit Tests
- Parser tests for each new syntax element
- AST tests for correct node construction
- Semantic tests for validation rules
- Codegen tests for correct output

### Integration Tests
- Full pipeline tests (parse → compile → load)
- Mock ADK for runtime tests

### Manual Tests
- Validate example files
- Inspect generated Python code
- Test with real ADK (if available)

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| ADK API changes | Pin ADK version, abstract integration |
| Circular references | Use graph algorithms, comprehensive tests |
| Grammar ambiguity | Use contextual keywords, test thoroughly |
