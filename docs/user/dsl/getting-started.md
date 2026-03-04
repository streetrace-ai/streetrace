# Getting Started with Streetrace DSL

The Streetrace DSL (Domain-Specific Language) enables you to define AI agents declaratively
in `.sr` files. This guide walks you through creating your first agent and running it.

## Overview

Streetrace DSL provides a clean, readable syntax for defining:

- **Models**: LLM configurations (provider, temperature, limits)
- **Tools**: External capabilities (MCP servers, built-in tools)
- **Agents**: AI agents with instructions and tool access
- **Prompts**: Reusable prompt templates
- **Flows**: Multi-step workflows
- **Guardrails**: Input/output validation and safety controls

## Prerequisites

- Streetrace installed (`pip install streetrace` or `poetry install`)
- API keys configured for your LLM provider (e.g., `ANTHROPIC_API_KEY`)

## Your First Agent

Create a file named `hello.sr`:

```streetrace
model main = anthropic/claude-sonnet

agent:
    tools streetrace.fs
    instruction greeting_prompt

prompt greeting_prompt:
    You are a friendly assistant. Greet the user and offer to help
    with their questions.
```

### Understanding the Components

**Model definition**: Specifies which LLM to use.

```streetrace
model main = anthropic/claude-sonnet
```

The model named `main` is the default for all prompts.

**Agent definition**: Defines the agent's capabilities.

```streetrace
agent:
    tools streetrace.fs
    instruction greeting_prompt
```

An unnamed agent is the default agent. It has access to the filesystem tool and uses
`greeting_prompt` for its system instruction.

**Prompt definition**: The agent's system prompt.

```streetrace
prompt greeting_prompt:
    You are a friendly assistant. Greet the user and offer to help
    with their questions.
```

Prompt bodies use indentation (no quotes needed).

## Validating Your Agent

Before running, validate the syntax:

```bash
streetrace check hello.sr
```

If valid, you'll see:

```
hello.sr: valid (1 model, 1 agent, 1 prompt)
```

## Running Your Agent

Run the agent:

```bash
streetrace --model=main hello.sr
```

Or, if you have a default model configured:

```bash
streetrace hello.sr
```

### Entry Point Selection

When you run a `.sr` file, StreetRace determines what to execute in this order:

1. **Main flow**: If your DSL defines `flow main:`, that flow runs first
2. **Default agent**: If no main flow exists, but there is an unnamed `agent:`, that agent runs
3. **First agent**: Otherwise, the first defined agent runs

This means you can control your entry point by either:
- Defining a `flow main:` for explicit orchestration
- Using an unnamed `agent:` as your default entry point
- Relying on definition order (less recommended)

## Adding Tools

Agents become more useful with tools. Here's an agent with GitHub access:

```streetrace
model main = anthropic/claude-sonnet

tool github = mcp "https://api.github.com/mcp/" with auth bearer ${env:GITHUB_PAT}

agent:
    tools github, streetrace.fs
    instruction dev_assistant_prompt

prompt dev_assistant_prompt:
    You are a developer assistant. Help the user with their
    GitHub repositories and local files.
```

### Tool Types

**MCP servers** (Model Context Protocol):

```streetrace
tool github = mcp "https://api.github.com/mcp/" with auth bearer ${env:GITHUB_PAT}
```

**Built-in tools**:

```streetrace
tool fs = builtin streetrace.fs
```

## Adding Guardrails

Guardrails protect your agent with input/output validation:

```streetrace
model main = anthropic/claude-sonnet

agent:
    tools streetrace.fs
    instruction assistant_prompt

on input do
    mask pii
    block if jailbreak
end

on output do
    mask pii
end

prompt assistant_prompt:
    You are a helpful assistant.
```

### Guardrail Actions

- `mask pii` - Replace sensitive data with placeholders
- `block if <condition>` - Block processing if condition is true
- `warn if <condition>` - Log a warning but continue
- `retry with <message>` - Ask the model to try again

## Using Structured Outputs

Define schemas for structured LLM responses:

```streetrace
model main = anthropic/claude-sonnet

schema TaskAnalysis:
    priority: string
    estimated_hours: float
    dependencies: list[string]

prompt analyze_task expecting TaskAnalysis:
    Analyze the given task and provide:
    - Priority (high, medium, low)
    - Estimated hours to complete
    - List of dependencies

    Task: ${task_description}

agent:
    instruction analyze_task
```

## Creating Multi-Agent Workflows

Define flows that orchestrate multiple agents:

```streetrace
model main = anthropic/claude-sonnet

flow process_document:
    $extracted = run agent extractor $document
    $validated = run agent validator $extracted
    return $validated

agent extractor:
    instruction extract_prompt

agent validator:
    instruction validate_prompt

prompt extract_prompt:
    Extract key information from the document.

prompt validate_prompt:
    Validate the extracted information for accuracy.
```

## Using Variables

Variables use the `$` prefix:

```streetrace
on start do
    $goal = run get_agent_goal  # Call user-defined flow
    $history = []
end

on output do
    push $message to $history
end
```

**Note**: `get_agent_goal` in this example is a user-defined flow, not a built-in feature. You can define any flows with any names.

### Variable Scoping

- Variables defined in `on start do` are **global** to the agent run
- Variables defined in flows are **local** to that flow
- Built-in variables: `$input_prompt`, `$conversation`, `$current_agent`

## Debugging

Use the `dump-python` command to see generated Python code:

```bash
streetrace dump-python hello.sr
```

This helps understand what your DSL compiles to and can aid debugging.

## Programmatic Loading

To load and use DSL agents programmatically:

```python
from pathlib import Path
from streetrace.workloads import DslDefinitionLoader

# Load the DSL definition
loader = DslDefinitionLoader()
definition = loader.load(Path("my_agent.sr"))

# Access the compiled workflow class
workflow_class = definition.workflow_class
print(f"Loaded: {definition.name}")
print(f"Format: {definition.metadata.format}")
```

For full runtime integration with workload execution:

```python
from pathlib import Path
from streetrace.workloads import WorkloadManager

# WorkloadManager handles discovery and workload creation
async with manager.create_workload("my_agent") as workload:
    async for event in workload.run_async(session, message):
        process_event(event)
```

## Next Steps

- [Syntax Reference](syntax-reference.md) - Complete syntax documentation
- [Multi-Agent Patterns](multi-agent-patterns.md) - Build coordinator, hierarchical, and iterative workflows
- [Prompt Escalation](escalation.md) - Handle LLM output formatting and build iterative refinement loops
- [CLI Reference](cli-reference.md) - Command-line options
- [Troubleshooting](troubleshooting.md) - Common errors and solutions

## Example: Complete Agent

Here's a complete example combining multiple features:

```streetrace
model main = anthropic/claude-sonnet
model fast = anthropic/haiku

schema ReviewResult:
    approved: bool
    comments: list[string]
    severity: string

tool github = mcp "https://api.github.com/mcp/" with auth bearer ${env:GITHUB_PAT}

retry default = 3 times, exponential backoff
timeout default = 2 minutes

on input do
    mask pii
    block if jailbreak
end

on output do
    mask pii
end

agent code_reviewer:
    tools github
    instruction review_prompt
    retry default
    timeout default

prompt review_prompt expecting ReviewResult:
    You are an expert code reviewer. Analyze the pull request
    for bugs, security issues, and code quality.

    Focus on:
    - Logic errors
    - Security vulnerabilities
    - Performance issues
    - Code style violations
```

## See Also

- [Syntax Reference](syntax-reference.md) - Complete language reference
- [Multi-Agent Patterns](multi-agent-patterns.md) - Coordinator, hierarchical, and iterative patterns
- [Prompt Escalation](escalation.md) - Normalized comparison and escalation handling
- [CLI Reference](cli-reference.md) - Command-line tools
- [Troubleshooting](troubleshooting.md) - Error resolution
