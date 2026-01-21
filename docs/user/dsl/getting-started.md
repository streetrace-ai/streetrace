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

To use DSL agents programmatically:

```python
from pathlib import Path
from streetrace.dsl.loader import DslAgentLoader

loader = DslAgentLoader()
workflow_class = loader.load(Path("my_agent.sr"))
workflow = workflow_class()
ctx = workflow.create_context()
```

The `DslStreetRaceAgent` wrapper provides full runtime integration with the AgentManager:

```python
from pathlib import Path
from streetrace.agents.dsl_agent_loader import DslAgentLoader

loader = DslAgentLoader()
agent = loader.load_from_path(Path("my_agent.sr"))
# Use with AgentManager...
```

## Next Steps

- [Syntax Reference](syntax-reference.md) - Complete syntax documentation
- [Multi-Agent Patterns](multi-agent-patterns.md) - Build coordinator, hierarchical, and iterative workflows
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
- [CLI Reference](cli-reference.md) - Command-line tools
- [Troubleshooting](troubleshooting.md) - Error resolution
