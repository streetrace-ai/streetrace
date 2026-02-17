# Streetrace

**Open runtime and DSL for structured multi-agent systems**

Streetrace is an open-source runtime that lets you define and execute structured multi-agent systems anywhere Python runs — locally, in Docker, or in CI/CD workflows. It is designed for advanced agent workflows where agents behave as explicit systems, with guardrails and execution constraints.

## Why Streetrace Exists

Traditional AI agent tooling treats agents as informal prompt glue. Streetrace treats agents as systems. It enables:

* **Explicit agent definitions** via a simple DSL and Python abstractions
* **Multi-agent orchestration** with controlled interactions
* **Execution guardrails** via constraint handlers similar to structured safety tooling
* **Flexible execution environments**: local, cloud, CI/CD (e.g., GitHub Actions)

This makes Streetrace suitable for developers and platform engineers building structured agent systems, automation workflows, or CI-integrated agent tooling.

---

## Quick Start

### Install

```bash
pip install streetrace
```

> Optional: install via `pipx` for isolated CLI usage.

### Define and Run

**Run an interactive agent:**

```bash
streetrace --model=gpt-4o
```

**Run a named agent:**

```bash
streetrace --model=gpt-4o --agent=code_reviewer
```

---

## What It Does Today

### 📌 Core Features

* **Python-based runtime** that works locally or in CI/CD
* **DSL agent definitions** for structured workflows
* **Multi-agent orchestration** with explicit execution semantics
* **Constraint handling** for safe executions (work in progress but usable)
* **Tool integrations** for common tasks (filesystem, CLI, search, etc.)

### 🚫 Not Included (Yet)

This project does *not* yet provide:

* Built-in evaluation frameworks
* Versioned agent lifecycle management
* Centralized fleet or policy plane

(*These are future roadmap items.*)

---

## Example Agent Definition

```streetrace
model main = anthropic/claude-sonnet
model gpt = openai/gpt-5.2

tool fs = builtin streetrace.fs
tool github = mcp "https://api.githubcopilot.com/mcp/" with auth bearer "${GITHUB_PAT}"

retry default = 3 times, exponential backoff
timeout default = 2 minutes

on input do
    mask pii
    block if jailbreak
end

on output do
    mask pii
end

prompt analyze_code using model gpt: """You are a historical context analysis expert. Analyze the historical context for the provided codebase."""

prompt main_instruction: """You are a code analysis assistant. Help users analyze their codebase for quality issues. Available commands: Analyze a file or directory, Get recommendations for improvement, Explain specific issues."""

agent code_analyzer:
    tools fs, github
    instruction analyze_code
    description "Analyzes code quality"

agent:
    tools fs
    instruction main_instruction
    use code_analyzer
```

This file defines a structured agent with specific tool bindings.

---

## Usage Scenarios

### Server Deployment

Use Streetrace in server environments with session management:

```bash
# Create .env file with required environment variables
cat > .env << 'EOF'
${dockerEnvVars}${dockerEnvVars ? '\n' : ''}
# Configure Streetrace
STREETRACE_API_KEY=<optional-streetrace.ai-key>
STREETRACE_AGENT_ID=<agent-path-url-or-streetrace_id>
# Optional user prompt
STREETRACE_PROMPT=<your-value-here>
EOF

docker run --env-file .env streetrace/streetrace:latest
```

### CI/CD

Integrate agents into automated workflows such as GitHub Actions.

Run with Streetrace Cloud defined agent:

```yaml
name: Streetrace Agent
on: [push]
jobs:
  run-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - id: streetrace
        uses: streetrace-ai/github-action@main
        with:
          claims: |
            agent_name: "code_analyzer"
          prompt: YOUR PROMPT TO TRIGGER ANALYSIS.
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          STREETRACE_API_KEY: ${{ secrets.STREETRACE_API_KEY }}
```

Or run your own agent defined in your repo:

```yaml
name: Streetrace Agent
on: [push]
jobs:
  run-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'
      - name: streetrace
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          STREETRACE_API_KEY: ${{ secrets.STREETRACE_API_KEY }}
        run: |
          pip install streetrace
          streetrace --agent=./agents/code_analyzer.sr --prompt "Check new PR changes"
```

### Local Dev

Run agents interactively as part of your development workflow:

```bash
cd myproject
streetrace --model=gpt-4o
```

---

## Tools Included

| Tool                  | Description                           |
| --------------------- | ------------------------------------- |
| `read_file`           | Read files from working dir           |
| `write_file`          | Write/update files                    |
| `list_directory`      | List contents                         |
| `find_in_files`       | grep/glob file search                 |
| `execute_cli_command` | Run shell commands with safety checks |

All tools are sandboxed within the working directory.

---

## Docs and Next Steps

See the `docs/` folder for:

* Backend configuration
* Model provider setup
* Tool usage
* Redis caching setup

Link these pages so users can quickly go deeper.

---

## Contributing

We welcome contributions. Before submitting a PR:

1. Write or update tests
2. Include documentation for new features
3. Follow existing styling and patterns

Check the `CONTRIBUTING.md` file for details.

---

## License

Streetrace is released under the **MIT License**.