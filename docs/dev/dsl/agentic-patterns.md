# DSL Agentic Patterns

The Streetrace DSL supports multi-agent patterns that map to Google ADK's agent composition
mechanisms. This document describes how the `delegate`, `use`, and `loop` constructs work
at the compiler and runtime levels.

## Overview

The DSL implements three key multi-agent patterns from the
[ADK Multi-Agent documentation](https://google.github.io/adk-docs/agents/multi-agents/):

| Pattern | DSL Construct | ADK Mechanism | Description |
|---------|---------------|---------------|-------------|
| Coordinator/Dispatcher | `delegate` | `sub_agents` | LLM decides which sub-agent handles the request |
| Hierarchical Task Decomposition | `use` | `AgentTool` | Agent calls other agents as tools |
| Iterative Refinement | `loop` block | `LoopAgent` | Repeat until condition or max iterations |

## Grammar Rules

The grammar rules for agentic patterns are defined in `src/streetrace/dsl/grammar/streetrace.lark`.

### Agent Properties

```lark
agent_property: "tools" name_list _NL                 -> agent_tools
              | "instruction" NAME _NL                -> agent_instruction
              | "retry" NAME _NL                      -> agent_retry
              | "timeout" timeout_value _NL           -> agent_timeout
              | "description" STRING _NL              -> agent_description
              | "delegate" name_list _NL              -> agent_delegate
              | "use" name_list _NL                   -> agent_use

name_list: tool_name ("," tool_name)*
```

**Source**: `src/streetrace/dsl/grammar/streetrace.lark:270-282`

### Loop Block

```lark
loop_block: "loop" "max" INT "do" _NL _INDENT flow_body _DEDENT "end" _NL?
          | "loop" "do" _NL _INDENT flow_body _DEDENT "end" _NL?
```

**Source**: `src/streetrace/dsl/grammar/streetrace.lark:316-317`

The loop block appears in both `handler_statement` and `flow_statement` rules, allowing it
to be used in event handlers and flow definitions.

## AST Nodes

### AgentDef

The `AgentDef` node includes two optional lists for multi-agent patterns:

```python
@dataclass
class AgentDef:
    name: str | None  # None for unnamed/default agent
    tools: list[str]
    instruction: str
    retry: str | None = None
    timeout_ref: str | None = None
    timeout_value: int | None = None
    timeout_unit: str | None = None
    description: str | None = None
    delegate: list[str] | None = None  # Sub-agents for coordinator pattern
    use: list[str] | None = None  # AgentTool for hierarchical pattern
    meta: SourcePosition | None = None
```

**Source**: `src/streetrace/dsl/ast/nodes.py:420-433`

### LoopBlock

The `LoopBlock` node represents bounded or unbounded iteration:

```python
@dataclass
class LoopBlock:
    """Loop block for iterative refinement pattern."""

    max_iterations: int | None  # None means unbounded loop
    body: list[AstNode]
    meta: SourcePosition | None = None
```

**Source**: `src/streetrace/dsl/ast/nodes.py:248-257`

## AST Transformation

The transformer converts parse tree nodes to AST nodes. Relevant methods in
`src/streetrace/dsl/ast/transformer.py`:

### delegate and use Properties

```python
def agent_delegate(self, items: list[object]) -> tuple[str, list[str]]:
    """Transform delegate property."""
    agents = self._extract_name_list(items)
    return ("delegate", agents)

def agent_use(self, items: list[object]) -> tuple[str, list[str]]:
    """Transform use property."""
    agents = self._extract_name_list(items)
    return ("use", agents)
```

### Loop Block

```python
def loop_block(self, items: list[object]) -> LoopBlock:
    """Transform loop block."""
    max_iterations: int | None = None
    body: list[AstNode] = []
    meta = self._get_meta(items)

    for item in items:
        if isinstance(item, Token) and item.type == "INT":
            max_iterations = int(item.value)
        elif isinstance(item, list):
            body = item

    return LoopBlock(
        max_iterations=max_iterations,
        body=body,
        meta=meta,
    )
```

## Semantic Analysis

The semantic analyzer validates agentic pattern constructs and detects errors.

### Validation Rules

**Source**: `src/streetrace/dsl/semantic/analyzer.py:454-493`

1. **Reference validation**: All agent names in `delegate` and `use` must reference
   defined agents.

2. **Warning W0002**: If an agent has both `delegate` and `use`, a warning is issued
   because this is an unusual pattern that may indicate a design issue.

3. **Error E0011**: Circular agent references are detected and reported.

### Circular Reference Detection

The analyzer builds a directed graph of agent relationships and uses DFS to detect cycles:

```python
def _detect_circular_agent_refs(self) -> None:
    """Detect circular references in agent delegate/use relationships."""
    graph = self._build_agent_graph()
    cycle = self._find_cycle_in_graph(graph)
    if cycle is not None:
        self._add_error(
            SemanticError.circular_agent_reference(
                agents=cycle,
                position=first_agent.meta,
            ),
        )
```

**Source**: `src/streetrace/dsl/semantic/analyzer.py:699-715`

### Error Codes

| Code | Type | Description |
|------|------|-------------|
| E0001 | Error | Undefined reference to agent in `delegate` or `use` |
| E0011 | Error | Circular agent reference detected |
| W0002 | Warning | Agent has both `delegate` and `use` |

**Source**: `src/streetrace/dsl/semantic/errors.py:15-29`

## Code Generation

The code generator emits Python code that maps DSL constructs to the runtime.

### Agent Generation

When emitting agents, the workflow visitor includes `sub_agents` and `agent_tools`:

```python
def _emit_agents(self) -> None:
    for agent in self._agents:
        # ...
        # Optional: sub_agents for delegate pattern
        if agent.delegate:
            sub_agents_str = ", ".join(f"'{a}'" for a in agent.delegate)
            self._emitter.emit(f"'sub_agents': [{sub_agents_str}],")

        # Optional: agent_tools for use pattern
        if agent.use:
            agent_tools_str = ", ".join(f"'{a}'" for a in agent.use)
            self._emitter.emit(f"'agent_tools': [{agent_tools_str}],")
```

**Source**: `src/streetrace/dsl/codegen/visitors/workflow.py:319-357`

### Generated Output

For the coordinator pattern:

```python
_agents = {
    'coordinator': {
        'tools': ['fs'],
        'instruction': 'coordinator_prompt',
        'sub_agents': ['billing_agent', 'support_agent'],
    },
}
```

For the hierarchical pattern:

```python
_agents = {
    'researcher': {
        'tools': ['fs'],
        'instruction': 'researcher_prompt',
        'agent_tools': ['searcher', 'summarizer'],
    },
}
```

## Runtime Integration

The runtime interprets the generated code to create ADK agent instances.

### Sub-agents (delegate)

When `sub_agents` is present, the runtime creates an `LlmAgent` with sub-agents:

```python
coordinator = LlmAgent(
    name="coordinator",
    instruction="...",
    sub_agents=[billing_agent, support_agent]
)
```

The LLM decides when to delegate to sub-agents based on the instruction context.

### AgentTool (use)

When `agent_tools` is present, the runtime wraps referenced agents as tools:

```python
from google.adk.tools import agent_tool

researcher = LlmAgent(
    name="researcher",
    instruction="...",
    tools=[
        agent_tool.AgentTool(agent=searcher),
        agent_tool.AgentTool(agent=summarizer),
    ]
)
```

The agent explicitly calls these as tools within its workflow.

### Loop Execution

Loop blocks are executed by the runtime with iteration tracking:

```python
for iteration in range(max_iterations or float('inf')):
    result = await execute_body(body, ctx)
    if should_exit(result):
        break
```

## Pattern Semantics

### delegate vs use

| Aspect | `delegate` | `use` |
|--------|-----------|-------|
| Control transfer | LLM decides when to transfer | Explicit tool call |
| Return behavior | May not return to caller | Always returns |
| Conversation context | Shared | Isolated |
| ADK mechanism | `sub_agents=[...]` | `tools=[AgentTool(...)]` |
| Use case | Routing, handoff | Task delegation |

### When to Use delegate

- User requests need routing to specialized handlers
- Full conversation handoff to sub-agent
- Central coordinator with multiple specialists

### When to Use use

- Agent needs capabilities from other agents
- Higher-level agent orchestrates lower-level ones
- Results must be aggregated by caller

## Example Files

The repository includes example files demonstrating each pattern:

| File | Pattern |
|------|---------|
| `agents/examples/dsl/coordinator.sr` | Coordinator/Dispatcher |
| `agents/examples/dsl/hierarchical.sr` | Hierarchical Task Decomposition |
| `agents/examples/dsl/iterative.sr` | Iterative Refinement |
| `agents/examples/dsl/combined.sr` | Combined patterns |

## See Also

- [Grammar Development Guide](grammar.md) - How to modify the DSL grammar
- [API Reference](api-reference.md) - Complete API documentation
- [Architecture](architecture.md) - Compiler pipeline design
- [User Guide: Multi-Agent Patterns](../../user/dsl/multi-agent-patterns.md) - Usage guide
