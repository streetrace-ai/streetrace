# Streetrace🚗💨🏁

Streetrace is an open-source AI agent framework that lives in your terminal and speaks your dev stack. Built by engineers who got tired of context-switching between AI chat windows and actual work.

**What it does:** Runs in your project directory, reads your code, executes commands, and maintains conversation context across sessions.

**What makes it different:** No proprietary APIs, no vendor lock-in. Just a CLI tool that integrates with your existing workflow and respects your local environment.

```bash
# Install and run in any project
pipx install streetrace
cd your-project
streetrace --model=gpt-4o

# Agent reads @files, runs commands, remembers context
You: @src/main.py review this and run the tests
```

## 🔧 Built for the Terminal

Streetrace integrates directly with your tools like the CLI and code editor (Dockerized environments). Agents can operate in the same terminal and shell as their human counterparts, enabling seamless, trusted collaboration. Your agent isn't a shadow coder, it’s a co-worker you can inspect, guide, and evolve.

## 🧩 Hackable by Design

Streetrace is powered by Google ADK, provides built-in A2A publishing, and integrates with any MCP tools. It comes with tools for building high-performing agents. Engineers can publish reusable agents to automate routine tasks like onboarding codebases, responding to CI failures, incident response automation, security analysis or generating service templates.

## 🛠 Model Agnostic

Model-agnostic and open-source, Streetrace supports local Ollama models and integrates with cloud providers like OpenAI, Azure, Anthropic, Amazon Bedrock etc. Agents run in the local environment, with controlled APIs (A2A endpoints), giving teams full control, observability, and security.

## Architecture

### 🏗️ Modular Agent Architecture
- **Agent Discovery System**: Automatic discovery of agents from `./agents/` directories
- **Structured Agent Framework**: Base `StreetRaceAgent` class with standardized lifecycle management
- **YAML Agent Configuration**: Declarative agent definitions with tools, instructions, and capabilities
- **Agent Manager**: Centralized agent creation, lifecycle management, and resource cleanup

### 🔧 Advanced Tool Integration
- **Multi-Protocol Tool Support**: Native Streetrace tools, MCP (Model Context Protocol) servers, and callable functions
- **Tool Provider System**: Unified interface for tool discovery, instantiation, and lifecycle management
- **MCP Transport Layer**: Support for STDIO, HTTP, and SSE transport protocols
- **CLI Safety Framework**: Intelligent command analysis with safe/ambiguous/risky categorization using `bashlex` parsing
- **Tool Reference System**: Structured tool references (`McpToolRef`, `StreetraceToolRef`, `CallableToolRef`)

### 💾 Session Management
- **Persistent Sessions**: JSON-based session storage with in-memory caching
- **Multi-User Support**: Session isolation by app name, user ID, and session ID
- **Event Streaming**: Real-time event processing with ADK Runner integration
- **Session Compaction**: Intelligent conversation history summarization to manage token limits

### 🎯 Interactive Experience
- **Rich Terminal UI**: Built on `rich` and `prompt-toolkit` with syntax highlighting and autocompletion
- **File Mention System**: `@file` and `@folder` syntax for context inclusion
- **Command System**: Built-in commands (`/help`, `/history`, `/compact`, `/reset`, `/exit`)
- **Real-time Status**: Live status updates during long-running operations

### 🔒 Security & Safety
- **CLI Command Analysis**: Bashlex-powered command parsing with security categorization
- **Path Traversal Protection**: Detection and prevention of directory escape attempts
- **Risky Command Blocking**: Configurable blocking of potentially dangerous operations
- **Working Directory Isolation**: All operations scoped to specified working directory

### 🌐 Model & Provider Support
- **LiteLLM Integration**: Support for 100+ LLM providers (OpenAI, Anthropic, Google, Ollama, etc.)
- **Model Factory Pattern**: Centralized model configuration and instantiation
- **Caching Support**: Optional Redis caching for LLM responses
- **Usage Tracking**: Built-in cost and token usage monitoring

### 🔄 Workflow Engine
- **Supervisor Pattern**: Orchestrated user-agent interaction loops
- **Event-Driven Architecture**: Reactive UI updates based on agent events
- **Pipeline Processing**: Modular input handling pipeline with configurable handlers
- **Error Recovery**: Graceful error handling with user feedback

## Getting Started

### Development Environment

**For the best development experience, use the VS Code Dev Container** which includes:

- **Enhanced terminal** with persistent bash history and autocompletion
- **Command shortcuts** like `gs` (git status), `pi` (poetry install), `check` (make check)

To get started:

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open the project in VS Code
3. Click "Reopen in Container" when prompted
4. Type `help` in the terminal to see all available commands and aliases

## Getting Started

### Prerequisites

- **Python 3.12+** (required)
- **Poetry** (for development) - [Installation Guide](https://python-poetry.org/docs/#installation)
- **Node.js** (optional, for MCP filesystem server)
- **Redis** (optional, for LLM response caching)

### Installation

#### Install from PyPI

Using pipx (follow [pipx installation instructions here](https://pipx.pypa.io/stable/installation/).)

```bash
$ pipx install streetrace
```

Or using pip to install as project dependency:

```bash
$ pip install streetrace
```

### Install from source

The code is managed by `poetry`. If it's not already installed, follow the [poetry
install guide](https://python-poetry.org/docs/#installation).

```bash
$ git clone git@github.com:streetrace-ai/streetrace.git
$ cd streetrace
$ poetry install
$ poetry run streetrace --model=$MODEL
```

Where `$MODEL` is the
[LiteLLM provider route](https://docs.litellm.ai/docs/providers) (`provider/model`).

### Environment Setup

#### Model Configuration

Streetrace uses [LiteLLM](https://docs.litellm.ai/docs/providers) for model access. Set up your environment based on your chosen provider:

For detailed backend configuration including Azure, Vertex AI, and other providers, see [Backend Configuration Guide](docs/user/backend-configuration.md).

**Cloud Model Providers:**
```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"

# Anthropic
export ANTHROPIC_API_KEY="your-api-key"

# Google
export GEMINI_API_KEY="your-api-key"

# AWS Bedrock
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
```

**Local Models:**
```bash
# Ollama
export OLLAMA_API_URL="http://localhost:11434"

# Local OpenAI-compatible server
export OPENAI_API_BASE="http://localhost:8000/v1"
```

#### Optional: Redis Caching

Enable LLM response caching with Redis:
```bash
# Install Redis
brew install redis  # macOS
sudo apt install redis-server  # Ubuntu

# Start Redis
redis-server

# Use caching
streetrace --cache --model=gpt-4o
```

For detailed Redis setup including Docker configuration and monitoring, see [Redis Caching Guide](docs/user/redis_caching.md).

### Usage

`streetrace` is a CLI, and it can be installed as your dev dependency. It runs in the
current directory, keeping all file reading and modifications in the current directory.

You can optionally supply a `--path` argument to provide a different working directory
path.

```bash
$ streetrace --model=$MODEL
You: Type your prompt
```

#### Try in your environment

Currently, Streetrace includes one coding agent with a model of your choise. This
agent is a capable software engineering agent that can work with your technology stack.

You can add more context to your prompts in two ways:

1. Use @-mentions, autocomplete will suggest local files that you can add to the
   prompt.
2. Add project context and instructions in the `.streetrace` folder in your project's
   directory:
   - `SYSTEM.md` is used as your system instruction.
   - Any other files under `.streetrace` are added as initial conversation messages.

## Command Line Reference

### Core Arguments

| Argument | Description | Default |
|----------|-------------|----------|
| `--model` | LiteLLM model identifier (required for prompts) | None |
| `--agent` | Specific agent to use | `default` |
| `--path` | Working directory for file operations | Current directory |
| `--prompt` | Non-interactive prompt mode | None |
| `--verbose` | Enable DEBUG logging | `false` |
| `--cache` | Enable Redis caching for LLM responses | `false` |
| `--out` | Output file path for final response | None |

### Session Management

| Argument | Description | Default |
|----------|-------------|----------|
| `--app-name` | Application name for session | Working directory name |
| `--user-id` | User ID for session | Detected from Git/GitHub/OS |
| `--session-id` | Session ID to use/create | Timestamp-based |
| `--list-sessions` | List available sessions | `false` |

### Information Commands

| Argument | Description |
|----------|-------------|
| `--help`, `-h` | Show help and exit |
| `--version` | Show version and exit |
| `--list-agents` | List available agents and exit |

### Usage Examples

```bash
# Basic usage
streetrace --model=gpt-4o

# Non-interactive mode
streetrace --model=claude-3-sonnet --prompt "Analyze this codebase"

# Specific working directory
streetrace --model=gpt-4o --path /path/to/project

# Session management
streetrace --model=gpt-4o --session-id my-feature-work
streetrace --list-sessions

# With caching and output file
streetrace --model=gpt-4o --cache --out response.md

# Using local models
streetrace --model=ollama/llama2
streetrace --model=openai/gpt-4o  # if using local OpenAI-compatible server
```



### Interactive Mode Features

#### Built-in Commands

| Command | Description |
|---------|-------------|
| `/help`, `/h` | Show all available commands |
| `/exit`, `/quit`, `/bye` | Exit the session |
| `/history` | Display conversation history |
| `/compact` | Summarize history to reduce tokens |
| `/reset` | Start a new conversation |

#### Autocompletion

- **File Paths**: `@` + TAB for file/directory completion
- **Commands**: `/` + TAB for command completion
- **Smart Context**: Contextual suggestions based on current directory

### Non-interactive Mode

Execute single prompts and exit:

```bash
# Direct prompt
streetrace --model=gpt-4o --prompt "Analyze this codebase structure"

# Positional arguments (with confirmation)
streetrace --model=gpt-4o "refactor the main.py file"

# Save output to file
streetrace --model=gpt-4o --prompt "Generate API docs" --out docs.md
```

## Agent System

### Agent Architecture

Streetrace features a modular agent system with automatic discovery and lifecycle management:

- **Agent Discovery**: Automatic scanning of `./agents/` directories
- **Lifecycle Management**: Proper resource allocation and cleanup
- **Tool Integration**: Seamless integration with Streetrace and MCP tools
- **YAML Configuration**: Declarative agent definitions

### Built-in Agents

| Agent | Description | Capabilities |
|-------|-------------|-------------|
| `GenericCodingAssistant` | Full-stack development partner | File operations, CLI execution, MCP tools |
| `coder` | Specialized coding agent | Code generation, refactoring, debugging |
| `code_reviewer` | Code review specialist | Static analysis, best practices, security |
| `config_inspector` | Configuration analysis | Config validation, optimization |

### Creating Custom Agents

#### YAML Agent (Recommended)

Create `./agents/my_agent.yml`:

```yaml
version: 1
kind: agent
name: MyCustomAgent
description: A specialized agent for specific tasks

instruction: |
  You are a specialized agent that helps with...
  
  Key principles:
  - Be precise and helpful
  - Follow best practices
  - Provide clear explanations

tools:
  - streetrace:
      module: fs_tool
      function: read_file
  - streetrace:
      module: fs_tool
      function: write_file
  - mcp:
      name: filesystem
      server:
        type: stdio
        command: npx
        args: ["-y", "@modelcontextprotocol/server-filesystem"]
      tools: ["edit_file", "move_file"]
```

#### Python Agent (Advanced)

Create `./agents/my_agent/agent.py`:

```python
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.tools.tool_refs import StreetraceToolRef

class MyAgent(StreetRaceAgent):
    def get_agent_card(self):
        return {
            "name": "My Agent",
            "description": "Specialized functionality",
            "capabilities": ["analysis", "generation"]
        }

    async def get_required_tools(self):
        return [
            StreetraceToolRef(module="fs_tool", function="read_file"),
            StreetraceToolRef(module="fs_tool", function="write_file"),
        ]

    async def create_agent(self, model_factory, tool_provider, system_context):
        model = model_factory.get_default_model()
        tools = tool_provider.get_tools(await self.get_required_tools())
        
        return Agent(
            name="My Agent",
            model=model,
            instruction="Your specialized instructions...",
            tools=tools,
        )
```

## Tool System

### Available Tool Types

#### Streetrace Native Tools
- **File System**: `read_file`, `write_file`, `list_directory`, `find_in_files`
- **CLI Execution**: `execute_cli_command` with safety analysis
- **Agent Management**: `list_agents`, `run_agent`

For comprehensive tool configuration and usage examples, see [Using Tools Guide](docs/user/using_tools.md).

#### MCP (Model Context Protocol) Integration

Streetrace supports [MCP](https://modelcontextprotocol.io/docs/getting-started/intro) servers for extended functionality:

**Filesystem Server:**
```yaml
mcp:
  name: filesystem
  server:
    type: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
  tools: ["edit_file", "move_file", "get_file_info"]
```

**GitHub Integration:**
```yaml
mcp:
  name: github
  server:
    type: http
    url: https://api.githubcopilot.com/mcp/
    headers:
      Authorization: "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"
```

**Context7 Documentation:**
```yaml
mcp:
  name: context7
  server:
    type: http
    url: https://mcp.context7.com/mcp
```

### MCP Transport Protocols

| Protocol | Use Case | Configuration |
|----------|----------|---------------|
| **STDIO** | Local executables | `command`, `args`, `cwd`, `env` |
| **HTTP** | REST APIs | `url`, `headers`, `timeout` |
| **SSE** | Server-Sent Events | `url`, `headers`, `timeout` |

### Tool Safety Framework

Streetrace includes intelligent CLI command analysis:

- **Safe Commands**: Pre-approved commands with relative paths
- **Ambiguous Commands**: Unknown commands without obvious risks  
- **Risky Commands**: Commands with absolute paths, sudo, system modification

**Safety Categories:**
```python
# Safe: Basic file operations with relative paths
ls src/
cat README.md
git status

# Ambiguous: Unknown commands or unclear intent
custom_script.py
unknown_command

# Risky: System modification or absolute paths
sudo rm -rf /
rm /etc/passwd
dd if=/dev/zero of=/dev/sda
```

## Project Context System

### Context Directory (`.streetrace/`)

Streetrace automatically loads project context from the `.streetrace/` directory:

- **`SYSTEM.md`**: System instructions for the agent
- **`project_overview.md`**: High-level project description
- **`coding_guide.md`**: Project-specific coding standards
- **Additional files**: Automatically included as conversation context

### File Mentions

Use `@` syntax to include files in your prompts:

```bash
# Include specific files
@src/main.py @tests/test_main.py review these files

# Include entire directories  
@src/ @docs/ analyze the codebase structure

# Autocomplete available
@<TAB>  # Shows available files and directories
```

## Development & CI

### Quality Assurance

- **Automated Testing**: Comprehensive test suite with pytest
- **Code Quality**: Ruff linting, MyPy type checking, Bandit security analysis
- **Performance Monitoring**: Startup profiling on every PR
- **Coverage Tracking**: Code coverage reporting

### GitHub Workflows

- **Quality Checks**: Automated linting, testing, and security scanning
- **Startup Profiling**: Performance regression detection on PRs
- **Release Automation**: Automated versioning and PyPI publishing
- **Code Review**: Automated code review suggestions

### Development Environment

Use the provided Dev Container for the best experience:

```bash
# VS Code with Dev Containers extension
# 1. Open project in VS Code
# 2. Click "Reopen in Container" when prompted
# 3. Use built-in shortcuts: gs, pi, check, help
```
