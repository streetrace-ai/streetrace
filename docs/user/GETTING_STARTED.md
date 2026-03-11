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
DEFAULT_MODEL_NAME=anthropic/claude-sonnet-4-20250514
ANTHROPIC_API_KEY=your_anthropic_api_key
EOF
```

StreetRace uses [LiteLLM](https://docs.litellm.ai/docs/set_keys) for model routing. You
can use any supported provider. Here are common configurations:

| Provider | DEFAULT_MODEL_NAME | API Key Variable |
|----------|-----------------|------------------|
| Anthropic | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Google | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |

> **Tip**: You can also pass the model on the command line with `--model` instead of
> setting `DEFAULT_MODEL_NAME` in `.env`.

### 4. See available agents

```bash
streetrace --list-agents
```

Example Output:

```
Name             Type  Description                                                                Location
researcher       dsl   Explores and analyzes codebases with read-only access                      Built-in
spec_writer      dsl   Creates detailed change request specifications from codebase analysis ...   Built-in
planner          dsl   Designs step-by-step implementation plans for coding tasks                  Built-in
coder            dsl   General-purpose coding assistant that implements features, fixes bugs ...   Built-in
agent_manager    dsl   Creates and manages Streetrace agent definitions                            Built-in
```

### 5. Create a custom agent

Use the default agent to generate a new agent definition. The coding agent knows
the StreetRace DSL and will create a validated `.sr` file:

```bash
streetrace "Create an agent called test_writer that analyzes code and writes pytest \
  tests. It should have read-write filesystem access and CLI access. When the user \
  doesn't specify a scope, the agent should: first check for uncommitted or staged \
  changes and write tests for those; if no uncommitted changes exist, diff the current \
  branch against main and test the diff; if there is no diff, run coverage analysis \
  and suggest ways to improve coverage, asking the user what to focus on."
```

The coding agent creates `./agents/test_writer.sr`, validates it with `streetrace check`,
and confirms it passes.

Verify it was created:

```bash
streetrace --list-agents
```

You should now see `test_writer` in the list alongside the bundled agents.

### 6. Run your custom agent

```bash
streetrace --agent test_writer "Write tests for the new validation module"
```

Or let it figure out what needs testing based on your recent changes:

```bash
streetrace --agent test_writer "Implement tests"
```

The `test_writer` agent examines your workspace, identifies what changed, and generates
targeted tests with good coverage.

## Understanding the Agent Definition

Open `./agents/test_writer.sr` to see what was created:

```streetrace
model main = anthropic/claude-sonnet-4-20250514

tool fs = builtin streetrace.fs
tool cli = builtin streetrace.cli

prompt test_writer_prompt: """You are a test writer agent. You analyze code and write
comprehensive pytest tests.

When the user specifies files or modules, write tests for those directly.

When no specific scope is given:
1. Check for uncommitted or staged changes (git status / git diff). Write tests
   covering those changes.
2. If the worktree is clean, diff the current branch against main. Identify changed
   files and ensure test coverage for the diff.
3. If there is no diff (e.g. on main with a clean worktree), run the existing test
   suite with coverage, identify the largest coverage gaps, and suggest areas to
   improve — then ask the user what to focus on.

Always follow the project's existing test conventions and patterns."""

agent:
    tools fs, cli
    instruction test_writer_prompt
    description "Analyzes code changes and writes targeted pytest tests"
```

Key elements:
- **model**: LLM to use. The name `main` is the default model.
- **tool**: Capabilities available to the agent (`builtin` for StreetRace tools,
  `mcp` for external MCP servers)
- **prompt**: The system instruction that defines agent behavior (triple-quoted strings)
- **agent**: The agent definition referencing tools and prompts
- **description**: How the agent appears in `--list-agents`

You can validate any `.sr` file with `streetrace check ./agents/test_writer.sr`.

For the full DSL reference, see [DSL Syntax Reference](dsl/syntax-reference.md).
Agents can also be defined in [YAML or Python](workloads/getting-started.md).

## Running in GitHub Actions

StreetRace agents can run as part of your CI/CD pipeline. Here is a workflow that
runs the `test_writer` agent on every pull request, commits the generated tests to a
new branch, and opens a PR:

```yaml
name: Test Writer

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  write-tests:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v6
        with:
          ref: ${{ github.head_ref }}
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install StreetRace
        run: pip install streetrace

      - name: Run test_writer agent
        env:
          DEFAULT_MODEL_NAME: ${{ vars.DEFAULT_MODEL_NAME || 'anthropic/claude-sonnet-4-20250514' }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          streetrace \
            --agent=./agents/test_writer.sr \
            --prompt="Implement tests" \
            --out=test-report.md

      - name: Create PR with generated tests
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          if git diff --quiet; then
            echo "No test files generated."
            exit 0
          fi

          BRANCH="streetrace/tests/pr-${{ github.event.pull_request.number }}"
          git checkout -b "$BRANCH"
          git add -A
          git commit -m "Add tests generated by StreetRace test_writer"
          git push -u origin "$BRANCH"

          gh pr create \
            --base "${{ github.head_ref }}" \
            --head "$BRANCH" \
            --title "Tests for #${{ github.event.pull_request.number }}" \
            --body "$(cat test-report.md)"

      - name: Post summary on triggering PR
        if: hashFiles('test-report.md') != ''
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          number: ${{ github.event.pull_request.number }}
          header: streetrace-tests
          path: test-report.md
```

Add your `ANTHROPIC_API_KEY` to your repository secrets and optionally set
`DEFAULT_MODEL_NAME` as a repository variable.

## Running in Docker

Run StreetRace in a container with your project mounted. Generated files (tests,
reports) are written to the mounted volume and persist on the host:

```bash
docker run --rm \
  -e DEFAULT_MODEL_NAME=anthropic/claude-sonnet-4-20250514 \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v $(pwd):/workspace \
  -w /workspace \
  ghcr.io/streetrace-ai/streetrace:latest \
  streetrace --agent=./agents/test_writer.sr \
    --prompt="Implement tests"
```

Any test files the agent creates will appear in your local working directory after
the container exits.

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
