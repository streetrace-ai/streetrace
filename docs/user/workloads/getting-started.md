# Getting Started with Workloads

Workloads are the unified execution model for StreetRace agents. This guide introduces
workloads and shows you how to create agents in DSL, YAML, and Python formats.

## What is a Workload?

A workload is any unit of work that StreetRace can execute. It could be:

- A DSL-defined agent (`.sr` files)
- A YAML-defined agent (`.yaml` or `.yml` files)
- A Python-defined agent (directories with `agent.py`)

The workload system provides a unified way to discover, load, and execute these different
agent types through a common interface.

## Quick Start

### Running Your First Agent

StreetRace comes with bundled agents. Run the default coding agent:

```bash
poetry run streetrace "Hello, what can you help me with?"
```

Or specify a different bundled agent:

```bash
poetry run streetrace --agent=Streetrace_Coding_Agent "Help me write a Python function"
```

### Listing Available Agents

See all discovered agents and their locations:

```bash
poetry run streetrace --list-agents
```

Output shows the agent name, type, and where it was found:

```
Available agents:
  Streetrace_Coding_Agent (yaml) [bundled]
  my_custom_agent (dsl) [cwd]
  project_helper (python) [cwd]
```

## Creating Agents

### DSL Agents

DSL (Domain-Specific Language) agents offer the most powerful and expressive way to
define agent behavior, including multi-agent patterns.

Create a file named `my_agent.sr`:

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting:
    You are a helpful assistant. Be concise and friendly.

agent:
    instruction greeting
```

Run it:

```bash
poetry run streetrace my_agent.sr "Hello!"
```

### YAML Agents

YAML agents provide a declarative way to define simple agents:

Create a file named `my_agent.yaml`:

```yaml
name: my_yaml_agent
description: A helpful YAML-defined assistant
model: anthropic/claude-sonnet
instruction: |
  You are a helpful assistant. Be concise and friendly.
```

Run it:

```bash
poetry run streetrace my_agent.yaml "Hello!"
```

Or by name (if in a search path):

```bash
poetry run streetrace --agent=my_yaml_agent "Hello!"
```

### Python Agents

Python agents offer full programmatic control. Create a directory structure:

```
my_python_agent/
  agent.py
```

In `agent.py`:

```python
from google.adk.agents import LlmAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


class MyPythonAgent(StreetRaceAgent):
    """A Python-defined assistant."""

    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="my_python_agent",
            description="A helpful Python-defined assistant",
        )

    async def create_agent(self, model_factory, tool_provider, system_context):
        return LlmAgent(
            name="my_python_agent",
            model=model_factory.get_current_model().model_id,
            instruction="You are a helpful assistant. Be concise and friendly.",
        )
```

Run it:

```bash
poetry run streetrace my_python_agent "Hello!"
```

## Agent Discovery

StreetRace automatically discovers agents in these locations (in priority order):

1. **Custom paths** - Directories in `STREETRACE_AGENT_PATHS` environment variable
2. **Current directory** - `./agents`, `.`, `.streetrace/agents`
3. **Home directory** - `~/.streetrace/agents`
4. **Bundled agents** - Built-in agents shipped with StreetRace

When multiple agents have the same name, the one in the higher-priority location wins.
This lets you override bundled agents with your own implementations.

### Search Path Priority Example

If you have:

```
~/.streetrace/agents/my_agent.yaml    # Home directory
./agents/my_agent.sr                   # Current directory
```

Running `--agent=my_agent` uses the DSL version from `./agents/` because the current
directory has higher priority than the home directory.

## Workload Formats Comparison

| Feature | DSL (`.sr`) | YAML (`.yaml`) | Python |
|---------|-------------|----------------|--------|
| Multi-agent patterns | Yes | No | Manual |
| Flow control | Yes | No | Manual |
| Tools | Declarative | Declarative | Programmatic |
| Custom logic | Limited | No | Full |
| Guardrails | Built-in | No | Manual |
| Learning curve | Medium | Low | High |

### When to Use Each Format

**DSL** - Best for:
- Complex workflows with multiple agents
- Declarative tool and model configuration
- Built-in guardrails (PII masking, jailbreak detection)
- Agentic patterns (delegate, use)

**YAML** - Best for:
- Simple, single-agent configurations
- Quick prototyping
- Configuration-driven agents
- Easy to edit without programming

**Python** - Best for:
- Full programmatic control
- Complex custom logic
- Integration with external systems
- Custom agent implementations

## Key Concepts

### Definitions vs Workloads

The workload system separates two concepts:

- **Definition**: A compiled artifact describing what to run (e.g., `DslWorkloadDefinition`)
- **Workload**: A running instance that processes messages (e.g., `DslWorkload`)

Definitions are loaded and validated once during discovery. Workloads are created from
definitions when execution begins.

### Compile-on-Load

DSL files are compiled immediately when loaded, not when executed. This means:

- Syntax errors are caught early during startup
- Invalid files are rejected before any agent runs
- You get clear error messages pointing to the problem

### Required Dependencies

When a workload runs, it receives these dependencies:

- **ModelFactory** - Creates and manages LLM model connections
- **ToolProvider** - Provides tools (filesystem, CLI, MCP servers)
- **SystemContext** - Contains project-level settings and instructions
- **SessionService** - Manages conversation persistence

## Next Steps

- [Examples](examples.md) - Complete example workloads for common use cases
- [Configuration](configuration.md) - Search paths, environment variables, and naming
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [DSL Syntax Reference](../dsl/syntax-reference.md) - Complete DSL language reference

## See Also

- [Multi-Agent Patterns](../dsl/multi-agent-patterns.md) - Using delegate and use patterns
- [Using Tools](../using_tools.md) - Configuring filesystem, CLI, and MCP tools
