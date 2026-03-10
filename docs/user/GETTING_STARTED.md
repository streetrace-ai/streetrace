# Getting Started

Get up and running with StreetRace in 5 minutes. By the end of this guide you will have
installed StreetRace, created a custom AI agent using natural language, and run it on a
real task.

## Prerequisites

- Python 3.12 or later
- An API key for at least one LLM provider (Anthropic, OpenAI, Google, etc.)

## Quick Start

### 1. Install StreetRace

```bash
pip install streetrace
```

### 2. Create a project directory

```bash
mkdir my_project
cd my_project
```

### 3. Configure your environment

Create a `.env` file with your model and API keys:

```bash
cat > .env << 'EOF'
STREETRACE_MODEL=anthropic/claude-sonnet-4-20250514
ANTHROPIC_API_KEY=your_anthropic_api_key
EOF
```

StreetRace uses [LiteLLM](https://docs.litellm.ai/docs/set_keys) for model routing. You
can use any supported provider. Here are common configurations:

| Provider | STREETRACE_MODEL | API Key Variable |
|----------|-----------------|------------------|
| Anthropic | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Google | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |

> **Tip**: You can also pass the model on the command line with `--model` instead of
> setting `STREETRACE_MODEL` in `.env`.

### 4. See available agents

```bash
streetrace --list-agents
```

Output:

```
Name                                Type    Description                                Location
Streetrace_Coding_Agent             yaml    A peer engineer agent...                   Built-in
StreetRace_Code_Reviewer_Agent      python  Specialized code reviewer...               Built-in
generic                             python  A helpful assistant...                     Built-in
```

These are the bundled agents. You can override them or add your own.

### 5. Create a custom agent

Use the default coding agent to generate a new agent definition. The coding agent knows
the StreetRace DSL and will create a validated `.sr` file:

```bash
streetrace "Create an agent called spec_writer that writes change request specs based \
  on user requests. It should explore the codebase, find relevant docs and code, then \
  research the web for the latest relevant whitepapers, community discussions, and \
  articles. Store specs in ./docs/spec/ with a new spec ID. The spec should contain \
  only findings and the spec itself, not actual code."
```

The coding agent creates `./agents/spec_writer.sr`, validates it with `streetrace check`,
and confirms it passes.

Verify it was created:

```bash
streetrace --list-agents
```

You should now see `spec_writer` in the list alongside the bundled agents.

### 6. Run your custom agent

```bash
streetrace --agent spec_writer "We need to add task planning tools to the built-in tools"
```

The `spec_writer` agent explores the codebase, researches the topic, and creates a spec
file in `./docs/spec/`.

## Understanding the Agent Definition

Open `./agents/spec_writer.sr` to see what was created:

```streetrace
model main = anthropic/claude-sonnet-4-20250514

tool fs = builtin streetrace.fs
tool cli = builtin streetrace.cli
tool context7 = mcp "https://mcp.context7.com/mcp"

prompt spec_writer_prompt: """You are a spec writer agent. When given a feature request:
1. Explore the codebase to understand the current architecture
2. Research the web for relevant whitepapers and discussions
3. Write a detailed change request spec
4. Save the spec to ./docs/spec/ with a unique ID"""

agent:
    tools fs, cli, context7
    instruction spec_writer_prompt
    description "Writes change request specs based on user requests"
```

Key elements:
- **model**: LLM to use. The name `main` is the default model.
- **tool**: Capabilities available to the agent (`builtin` for StreetRace tools,
  `mcp` for external MCP servers)
- **prompt**: The system instruction that defines agent behavior (triple-quoted strings)
- **agent**: The agent definition referencing tools and prompts
- **description**: How the agent appears in `--list-agents`

You can validate any `.sr` file with `streetrace check ./agents/spec_writer.sr`.

For the full DSL reference, see [DSL Syntax Reference](dsl/syntax-reference.md).
Agents can also be defined in [YAML or Python](workloads/getting-started.md).

## Running in GitHub Actions

StreetRace agents can run as part of your CI/CD pipeline. Here is a workflow that
triggers on issue comments and runs the `spec_writer` agent:

```yaml
name: Spec Writer

on:
  issue_comment:
    types: [created]

jobs:
  write-spec:
    runs-on: ubuntu-latest
    if: contains(github.event.comment.body, '/spec')
    permissions:
      contents: write
      issues: write

    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install StreetRace
        run: pip install streetrace

      - name: Run spec_writer agent
        env:
          STREETRACE_MODEL: ${{ vars.STREETRACE_MODEL || 'anthropic/claude-sonnet-4-20250514' }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          streetrace \
            --agent=./agents/spec_writer.yaml \
            --prompt="${{ github.event.comment.body }}" \
            --out=spec-result.md

      - name: Post spec as comment
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          number: ${{ github.event.issue.number }}
          header: streetrace-spec
          path: spec-result.md
```

Add your `ANTHROPIC_API_KEY` to your repository secrets and optionally set
`STREETRACE_MODEL` as a repository variable.

## Running in Docker

For isolated execution, run StreetRace in a container:

```bash
docker run --rm \
  -e STREETRACE_MODEL=anthropic/claude-sonnet-4-20250514 \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v $(pwd):/workspace \
  -w /workspace \
  ghcr.io/streetrace-ai/streetrace:latest \
  streetrace --agent=./agents/spec_writer.yaml \
    --prompt="We need to add task planning tools"
```

## Agent Discovery

StreetRace finds agents in these locations (highest priority first):

1. **`STREETRACE_AGENT_PATHS`** env var (colon-separated directories)
2. **`./agents`** and **`.streetrace/agents`** in the current directory
3. **`~/.streetrace/agents`** in your home directory
4. **Built-in agents** shipped with StreetRace

When multiple agents share a name, the higher-priority location wins. This lets you
override bundled agents with your own implementations.

## Next Steps

- [Workloads Guide](workloads/getting-started.md) - YAML, DSL, and Python agent formats
- [DSL Syntax Reference](dsl/syntax-reference.md) - Full DSL language documentation
- [Using Tools](using_tools.md) - Configure file system, CLI, and MCP tools
- [Backend Configuration](backend-configuration.md) - Set up LLM providers
