# Streetrace

Run autonomous AI agents anywhere Python runs.

Streetrace is an open-source agent runner that executes AI agents on workstations, servers, CI/CD pipelines, and cloud infrastructure. Define agents once, run them everywhere.

```bash
pip install streetrace
streetrace --model=gpt-4o --agent=coder
```

## Why Streetrace

**Infrastructure agnostic.** The same agent definition runs in your terminal during development, in GitHub Actions for automated code review, or on Kubernetes for production workloads.

**Model agnostic.** Use any LLM provider through LiteLLM: OpenAI, Anthropic, Google, AWS Bedrock, Azure, Ollama, or any OpenAI-compatible endpoint.

**Protocol native.** Built on Google ADK with first-class support for MCP (Model Context Protocol) tools and A2A (Agent-to-Agent) communication.

## Quick Start

### Install

```bash
# Recommended
pipx install streetrace

# Or with pip
pip install streetrace
```

### Configure

Set your model provider credentials:

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Google
export GEMINI_API_KEY="..."

# Local models (Ollama)
export OLLAMA_API_URL="http://localhost:11434"
```

### Run

```bash
# Interactive mode
streetrace --model=gpt-4o

# Single prompt
streetrace --model=claude-3-5-sonnet --prompt "Review the authentication module"

# Specific agent
streetrace --model=gpt-4o --agent=code_reviewer
```

## Deployment Scenarios

### Local Development

Run agents interactively with file completion and session persistence:

```bash
cd your-project
streetrace --model=gpt-4o
> @src/main.py refactor this module
```

### CI/CD Pipelines

Integrate agents into automated workflows:

```yaml
# GitHub Actions example
- name: Code Review
  run: |
    pip install streetrace
    streetrace --model=gpt-4o --agent=code_reviewer --prompt "Review changes in this PR"
```

### Server Deployment

Run as a service with session management:

```bash
streetrace --model=gpt-4o \
  --app-name=review-bot \
  --session-id=$PR_NUMBER \
  --prompt "$REVIEW_PROMPT" \
  --out=review.md
```

## Creating Agents

### YAML Definition

Create `agents/my_agent.yml`:

```yaml
version: 1
kind: agent
name: MyAgent
description: A specialized agent for your workflow

instruction: |
  You are a specialized agent that...

tools:
  - streetrace:
      module: fs_tool
      function: read_file
  - streetrace:
      module: cli_tool
      function: execute_cli_command
  - mcp:
      name: github
      server:
        type: stdio
        command: npx
        args: ["-y", "@modelcontextprotocol/server-github"]
```

### Python Definition

Create `agents/my_agent/agent.py`:

```python
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.tools.tool_refs import StreetraceToolRef

class MyAgent(StreetRaceAgent):
    async def get_required_tools(self):
        return [
            StreetraceToolRef(module="fs_tool", function="read_file"),
            StreetraceToolRef(module="cli_tool", function="execute_cli_command"),
        ]

    async def create_agent(self, model_factory, tool_provider, system_context):
        return Agent(
            name="My Agent",
            model=model_factory.get_default_model(),
            instruction="Your agent instructions...",
            tools=tool_provider.get_tools(await self.get_required_tools()),
        )
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read files from the working directory |
| `write_file` | Create or update files |
| `list_directory` | List directory contents |
| `find_in_files` | Search for patterns across files |
| `execute_cli_command` | Run shell commands with safety analysis |

All tools are sandboxed to the working directory with path traversal prevention.

## MCP Integration

Connect to any MCP-compatible tool server:

```yaml
tools:
  - mcp:
      name: filesystem
      server:
        type: stdio
        command: npx
        args: ["-y", "@modelcontextprotocol/server-filesystem"]
      tools: ["edit_file", "move_file"]
```

Supported transports: STDIO, HTTP, SSE.

## Project Context

Add project-specific instructions in `.streetrace/`:

```
.streetrace/
├── SYSTEM.md          # System instructions for the agent
├── coding_guide.md    # Project coding standards
└── architecture.md    # Architecture documentation
```

Files are automatically loaded as conversation context.

## CLI Reference

```
streetrace [OPTIONS]

Options:
  --model TEXT          LiteLLM model identifier (required)
  --agent TEXT          Agent to use (default: coder)
  --path PATH           Working directory
  --prompt TEXT         Non-interactive single prompt
  --out PATH            Output file for response
  --session-id TEXT     Session identifier for persistence
  --cache               Enable Redis response caching
  --verbose             Enable debug logging
  --list-agents         List available agents
  --list-sessions       List saved sessions
  --help                Show help message
```

## Documentation

- [Backend Configuration](docs/user/backend-configuration.md) - Model provider setup
- [Using Tools](docs/user/using_tools.md) - Tool configuration and usage
- [Redis Caching](docs/user/redis_caching.md) - Response caching setup

## Development

```bash
git clone https://github.com/streetrace-ai/streetrace.git
cd streetrace
poetry install
poetry run streetrace --model=gpt-4o
```

Run checks:

```bash
make check  # Runs tests, linting, type checking, security scans
```

## License

[MIT License](LICENSE)
