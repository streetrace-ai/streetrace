# Task Definition: DSL Agentic Patterns ADK Integration

| Field | Value |
|-------|-------|
| **Feature ID** | 017-dsl-adk-integration |
| **Feature Name** | ADK Integration for DSL Agentic Patterns |
| **Status** | Active |
| **Created** | 2026-01-21 |
| **Depends On** | 017-dsl-compiler-patterns (completed) |

## Overview

Integrate the DSL agentic patterns (`delegate`, `use`, `loop`) with StreetRace's ADK agent creation pipeline. The DSL compiler already generates the correct `sub_agents` and `agent_tools` fields in the `_agents` dict, but the `DslStreetRaceAgent.create_agent()` method does not use these fields when instantiating `LlmAgent`.

## Problem Statement

**Current State:**
The DSL code generator correctly produces:
```python
_agents = {
    'default': {
        'tools': ['fs'],
        'instruction': 'coordinator_prompt',
        'sub_agents': ['code_expert', 'research_expert'],  # From 'delegate' keyword
        'agent_tools': ['extractor', 'analyzer'],          # From 'use' keyword
    }
}
```

**Gap:**
`DslStreetRaceAgent.create_agent()` in `dsl_agent_loader.py:340-382` ignores `sub_agents` and `agent_tools` fields:

```python
return LlmAgent(
    name=self._source_file.stem,
    model=model,
    instruction=instruction,
    tools=tools,  # Only regular tools, no sub_agents or agent_tools
)
```

**Required:**
Create `LlmAgent` with:
- `sub_agents=[...]` for coordinator pattern (agents referenced via `delegate`)
- `tools=[..., AgentTool(agent), ...]` for hierarchical pattern (agents wrapped via `use`)

## Design Documents

- [Agentic Patterns Implementation](../agent-patterns/017-dsl-compiler-patterns-task.md) - Completed DSL compiler work
- [Agentic Patterns Documentation](../../dev/dsl/agentic-patterns.md) - Developer docs
- [YAML Agent Builder](../../../src/streetrace/agents/yaml_agent_builder.py) - Reference implementation

## Architecture Analysis

### Current Agent Creation Pipeline

```
DSL File (.sr)
    ↓ DslAgentLoader._load_dsl_file()
Compiled Bytecode
    ↓ exec in namespace
DslAgentWorkflow class with _agents dict
    ↓ DslStreetRaceAgent wrapper
StreetRaceAgent interface
    ↓ create_agent()
LlmAgent (ADK)   ← MISSING: sub_agents, agent_tools
```

### Key Code Locations

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Agent Creation | `src/streetrace/agents/dsl_agent_loader.py` | 340-382 | Creates LlmAgent from DSL |
| Agent Definition | `src/streetrace/agents/dsl_agent_loader.py` | 384-400 | Extracts agent def from _agents |
| Tool Resolution | `src/streetrace/agents/dsl_agent_loader.py` | 496-560 | Converts tool refs to ADK tools |
| YAML Reference | `src/streetrace/agents/yaml_agent_builder.py` | 112-163 | Handles sub_agents/agent_tools |
| Code Generator | `src/streetrace/dsl/codegen/visitors/workflow.py` | 319-357 | Emits _agents dict |

### YAML Agent Builder Reference

The YAML agent builder already implements both patterns correctly:

**Sub-agents (Coordinator Pattern):**
```python
# yaml_agent_builder.py:142-163
def _create_sub_agents(
    self,
    agents: list[AgentRef | InlineAgentSpec],
    model: "BaseLlm | None",
) -> list["BaseAgent"]:
    sub_agents = []
    for sub_spec in agents:
        sub_agent = self._create_agent_from_spec(spec=sub_spec.agent, model=model)
        sub_agents.append(sub_agent)
    return sub_agents
```

**Agent Tools (Hierarchical Pattern):**
```python
# yaml_agent_builder.py:112-140
def _create_agent_tools(self, tools, model) -> list["AdkTool"]:
    for tool_spec in tools:
        if isinstance(tool_spec, InlineAgentSpec):
            from google.adk.tools.agent_tool import AgentTool
            agent_tool = AgentTool(
                self._create_agent_from_spec(spec=tool_spec.agent, model=model)
            )
            tool_refs.append(agent_tool)
```

## Implementation Requirements

### 1. Modify DslStreetRaceAgent.create_agent()

Update `src/streetrace/agents/dsl_agent_loader.py:340-382`:

```python
async def create_agent(
    self,
    model_factory: "ModelFactory",
    tool_provider: "ToolProvider",
    system_context: "SystemContext",
) -> "BaseAgent":
    from google.adk.agents import LlmAgent

    self._workflow_instance = self._workflow_class()
    agent_def = self._get_default_agent_def()

    instruction = self._resolve_instruction(agent_def)
    model = self._resolve_model(model_factory, agent_def)
    tools = self._resolve_tools(tool_provider, agent_def)

    # NEW: Resolve sub_agents for delegate pattern
    sub_agents = await self._resolve_sub_agents(
        agent_def, model_factory, tool_provider, system_context
    )

    # NEW: Resolve agent_tools for use pattern (adds to tools list)
    agent_tools = await self._resolve_agent_tools(
        agent_def, model_factory, tool_provider, system_context
    )
    tools.extend(agent_tools)

    # Build LlmAgent with all components
    agent_kwargs = {
        "name": self._source_file.stem,
        "model": model,
        "instruction": instruction,
        "tools": tools,
    }
    if sub_agents:
        agent_kwargs["sub_agents"] = sub_agents

    return LlmAgent(**agent_kwargs)
```

### 2. Add _resolve_sub_agents() Method

Create method to recursively instantiate delegated agents:

```python
async def _resolve_sub_agents(
    self,
    agent_def: dict[str, object],
    model_factory: "ModelFactory",
    tool_provider: "ToolProvider",
    system_context: "SystemContext",
) -> list["BaseAgent"]:
    """Resolve sub_agents for the coordinator/dispatcher pattern.

    Creates LlmAgent instances for each agent listed in 'sub_agents'.

    Args:
        agent_def: Agent definition dict.
        model_factory: Factory for creating LLM models.
        tool_provider: Provider for tools.
        system_context: System context.

    Returns:
        List of created sub-agent instances.
    """
    sub_agent_names = agent_def.get("sub_agents", [])
    if not sub_agent_names:
        return []

    agents = self._workflow_class._agents
    sub_agents = []

    for agent_name in sub_agent_names:
        if agent_name not in agents:
            logger.warning("Sub-agent '%s' not found in workflow", agent_name)
            continue

        sub_agent_def = agents[agent_name]
        sub_agent = await self._create_agent_from_def(
            name=agent_name,
            agent_def=sub_agent_def,
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
        )
        sub_agents.append(sub_agent)

    return sub_agents
```

### 3. Add _resolve_agent_tools() Method

Create method to wrap agents as AgentTool:

```python
async def _resolve_agent_tools(
    self,
    agent_def: dict[str, object],
    model_factory: "ModelFactory",
    tool_provider: "ToolProvider",
    system_context: "SystemContext",
) -> list["AdkTool"]:
    """Resolve agent_tools for the hierarchical pattern.

    Creates AgentTool wrappers for each agent listed in 'agent_tools'.

    Args:
        agent_def: Agent definition dict.
        model_factory: Factory for creating LLM models.
        tool_provider: Provider for tools.
        system_context: System context.

    Returns:
        List of AgentTool instances.
    """
    from google.adk.tools.agent_tool import AgentTool

    agent_tool_names = agent_def.get("agent_tools", [])
    if not agent_tool_names:
        return []

    agents = self._workflow_class._agents
    agent_tools = []

    for agent_name in agent_tool_names:
        if agent_name not in agents:
            logger.warning("Agent tool '%s' not found in workflow", agent_name)
            continue

        sub_agent_def = agents[agent_name]
        sub_agent = await self._create_agent_from_def(
            name=agent_name,
            agent_def=sub_agent_def,
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
        )
        agent_tools.append(AgentTool(sub_agent))

    return agent_tools
```

### 4. Add _create_agent_from_def() Helper

Extract common agent creation logic:

```python
async def _create_agent_from_def(
    self,
    name: str,
    agent_def: dict[str, object],
    model_factory: "ModelFactory",
    tool_provider: "ToolProvider",
    system_context: "SystemContext",
) -> "BaseAgent":
    """Create an LlmAgent from an agent definition dict.

    This method is used for creating both the root agent and sub-agents.
    """
    from google.adk.agents import LlmAgent

    instruction = self._resolve_instruction(agent_def)
    model = self._resolve_model(model_factory, agent_def)
    tools = self._resolve_tools(tool_provider, agent_def)

    # Recursively resolve nested patterns
    sub_agents = await self._resolve_sub_agents(
        agent_def, model_factory, tool_provider, system_context
    )
    agent_tools = await self._resolve_agent_tools(
        agent_def, model_factory, tool_provider, system_context
    )
    tools.extend(agent_tools)

    # Get description from agent definition
    description = agent_def.get("description", f"Agent: {name}")

    agent_kwargs = {
        "name": name,
        "model": model,
        "instruction": instruction,
        "tools": tools,
        "description": description,
    }
    if sub_agents:
        agent_kwargs["sub_agents"] = sub_agents

    return LlmAgent(**agent_kwargs)
```

### 5. Update close() Method

Update resource cleanup to handle sub-agents and agent tools:

```python
async def close(self, agent_instance: "BaseAgent") -> None:
    """Clean up resources including sub-agents and agent tools."""
    await self._close_agent_recursive(agent_instance)
    self._workflow_instance = None

async def _close_agent_recursive(self, agent: "BaseAgent") -> None:
    """Recursively close agent, its sub-agents, and tools."""
    # Close sub-agents first
    for sub_agent in agent.sub_agents:
        await self._close_agent_recursive(sub_agent)

    # Close tools, handling AgentTool specially
    from google.adk.tools.agent_tool import AgentTool
    for tool in getattr(agent, "tools", []) or []:
        if isinstance(tool, AgentTool):
            await self._close_agent_recursive(tool.agent)
        close_fn = getattr(tool, "close", None)
        if callable(close_fn):
            ret = close_fn()
            if inspect.isawaitable(ret):
                await ret
```

### 6. Code Generator Enhancement (Optional)

Update `_emit_agents()` in `workflow.py` to include agent description:

```python
# Add description field to agent emission
if agent.description:
    self._emitter.emit(f"'description': '{agent.description}',")
```

## Testing Strategy

### Unit Tests

Create `tests/unit/agents/test_dsl_agent_adk_integration.py`:

1. **Test sub_agents creation:**
   - Single sub-agent
   - Multiple sub-agents
   - Nested sub-agents (coordinator with sub-coordinators)

2. **Test agent_tools creation:**
   - Single agent tool
   - Multiple agent tools
   - Agent tool with its own tools

3. **Test combined patterns:**
   - Agent with both delegate and use
   - Mixed hierarchy

4. **Test error handling:**
   - Reference to undefined agent
   - Circular references (should be caught by semantic analyzer)

### Integration Tests

Create `tests/integration/agents/test_dsl_agentic_patterns.py`:

1. **Test coordinator.sr example:**
   - Loads and compiles
   - Creates agent with sub_agents
   - Sub-agents have correct tools

2. **Test hierarchical.sr example:**
   - Loads and compiles
   - Creates agent with AgentTool wrappers
   - Agent tools callable

3. **Test combined.sr example:**
   - Multiple patterns working together

### Manual E2E Tests

From `docs/testing/dsl/017-dsl-compiler-testing.md`:

```bash
# Test coordinator pattern
poetry run streetrace --agent agents/examples/dsl/coordinator.sr

# Test hierarchical pattern
poetry run streetrace --agent agents/examples/dsl/hierarchical.sr

# Verify generated Python
poetry run streetrace dump-python agents/examples/dsl/coordinator.sr
```

## Success Criteria

1. **Functional Requirements:**
   - [ ] `delegate` keyword creates agents with `sub_agents` parameter
   - [ ] `use` keyword creates agents with `AgentTool` wrappers in tools
   - [ ] Recursive patterns work (sub-agents can have their own sub-agents)
   - [ ] Resource cleanup properly closes all nested agents/tools

2. **Code Quality:**
   - [ ] All unit tests pass with >95% coverage for new code
   - [ ] All integration tests pass
   - [ ] `make check` passes (lint, type, security)
   - [ ] No regression in existing functionality

3. **Documentation:**
   - [ ] Code is documented with docstrings
   - [ ] Testing guide updated if needed

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Circular dependencies at runtime | High | Semantic analyzer already catches these at compile time |
| Resource leaks from nested agents | Medium | Implement recursive close() following YAML builder pattern |
| Model inheritance for sub-agents | Low | Follow YAML builder pattern: inherit parent model if not specified |
| Performance with deep nesting | Low | ADK handles this; DSL examples are typically shallow |

## Dependencies

### External
- Google ADK with support for:
  - `LlmAgent` with `sub_agents` parameter
  - `google.adk.tools.agent_tool.AgentTool`

### Internal
- Completed DSL compiler agentic patterns (017-dsl-compiler-patterns)
- `DslAgentLoader` infrastructure
- `ToolProvider` for tool resolution
