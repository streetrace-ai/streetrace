StreetRace is an open-source platform for engineering-native AI agents that
integrate with your tools, automate your workflows, and evolve with your development
process.

StreetRace is a new kind of teammate: one that runs linters, generates modules,
monitors builds, or triages bugs the way you taught it.

We believe the future of development is peer-to-peer: engineer + agent. And we’re
building the rails.

If you want to help define that future - contribute code, build agents, or shape the
platform - GitHub’s open. Jump in, clone it, and make agents your own.

# StreetRace🚗💨

Unlike generic agent frameworks or black-box AI engineers, StreetRace is:

## 🔧 Built for Developers, by Developers

StreetRace integrates directly with your tools like the CLI and code editor
(Dockerized environments will follow). Agents can operate in the same terminal and shell
as their human counterparts, enabling seamless, trusted collaboration.

## 🤝 Engineering Peer, Not Replacement

Where Devin and other agents aim to replace engineers, StreetRace empowers
engineers. Your agent isn't a shadow coder, it’s a co-worker you can inspect, guide, and
evolve.

## 🧩 Opinionated, Yet Extensible

Unlike CrewAI’s generic orchestration layer, StreetRace comes powered by ADK,
provides built-in A2A publishing, and integrates with any MCP tools. It comes with
battle-tested patterns and tools for building high-performing agents. Developers can
publish reusable agents to automate routine tasks like onboarding codebases, responding
to CI failures, or generating service templates.

## 🛠 Open, Flexible, and Secure

Model-agnostic and open-source, StreetRace supports everything from local Ollama
models to cloud APIs. Agents run in the local environment, with controlled APIs (A2A
endpoints), giving teams full control, observability, and security.

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

### Installation and usage

### Install from PyPI

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
$ git clone git@github.com:krmrn42/street-race.git
$ cd street-race
$ poetry install
$ poetry run streetrace --model=$YOUR_FAVORITE_MODEL
```

Where `$YOUR_FAVORITE_MODEL` is the
[LiteLLM provider route](https://docs.litellm.ai/docs/providers) (`provider/model`).

### Environment Setup

Follow relevant LiteLLM guides to set up environment for a specific model. For example,
for commercial providers, set your regular API key in the environment
(`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, etc), or `OLLAMA_API_URL` for
local Ollama models.

### Usage

`streetrace` is a CLI, and it can be installed as your dev dependency. It runs in the
current directory, keeping all file reading and modifications in the current directory.

You can optionally supply a `--path` argument to provide a different working directory
path.

```bash
$ streetrace --model=$YOUR_FAVORITE_MODEL
You: Type your prompt
```

#### Try in your environment

Currently, StreetRace includes one coding agent with a model of your choise. This
agent is a capable software engineering agent that can work with your technology stack.

You can add more context to your prompts in two ways:

1. Use @-mentions, autocomplete will suggest local files that you can add to the
   prompt.
2. Add project context and instructions in the `.streetrace` folder in your project's
   directory:
   - `SYSTEM.md` is used as your system instruction.
   - Any other files under `.streetrace` are added as initial conversation messages.

### Command Line Arguments

#### Help Information

You can view all available command-line arguments and their descriptions:

```bash
$ streetrace --help
# or
$ streetrace -h
```

This displays the complete usage information, including all available options and their descriptions.

#### Version Information

You can check the installed version of StreetRace:

```bash
$ streetrace --version
StreetRace🚗💨 0.1.13
```

#### Session Management

StreetRace supports persistence of conversations through sessions. You can specify:

- `--app-name` - Application name for the session (defaults to the current working
  directory name)
- `--user-id` - User ID for the session (defaults to your GitHub username, Git username,
  or OS username)
- `--session-id` - Session ID to use or create (defaults to current timestamp)
- `--list-sessions` - List all available sessions for the current app and user

Examples:

```bash
# List all sessions for the current app and user
$ streetrace --list-sessions

# Create or continue a specific session
$ streetrace --session-id my-project-refactoring

# Work with a specific app name and user
$ streetrace --app-name my-project --user-id john.doe --session-id feature-x
```

If no session arguments are provided, StreetRace will:

1. Use the current working directory name as the app name
2. Use your detected user identity as the user ID
3. Create a new session with a timestamp-based ID

This allows you to maintain separate conversation contexts for different projects or
tasks.

If you want to work with the same agent/context across multiple runs, use the same
session ID.

#### Working with Files in Another Directory

The `--path` argument allows you to specify a different working directory for all file
operations:

```bash
$ streetrace --path /path/to/your/project
```

This path will be used as the working directory (work_dir) for all tools that interact
with the file system, including:

- `list_directory`
- `read_file`
- `write_file`
- `find_in_files`
- as a cwd in cli commands.

This feature makes it easier to work with files in another location without changing
your current directory.

### Interactive Mode

When run without `--prompt`, StreetRace enters interactive mode.

#### Autocompletion

- Type `@` followed by characters to autocomplete file or directory paths relative to
  the working directory.
- Type `/` at the beginning of the line to autocomplete available internal commands.

#### Internal Commands

These commands can be typed directly into the prompt (with autocompletion support):

- `/help`: Display a list of all available commands with their descriptions.
- `/exit`: Exit the interactive session.
- `/quit`: Quit the interactive session.
- `/history`: Display the conversation history.
- `/compact`: Summarize conversation history to reduce token count.
- `/reset`: Reset the current session, clearing the conversation history.

For detailed information about the `/compact` command, see
[docs/commands/compact.md](docs/commands/compact.md).

### Non-interactive Mode

You can use the `--prompt` argument to run StreetRace in non-interactive mode:

```bash
$ streetrace --prompt "List all Python files in the current directory"
```

This will execute the prompt once and exit, which is useful for scripting or one-off
commands.

### CLI Command Safety

StreetRace includes an experimental safety mechanism for CLI command execution.
Each command requested by the AI is analyzed and categorized into one of three safety
levels:

- **Safe**: Commands from a pre-configured safe list with only relative paths
- **Ambiguous**: Commands not in the safe list but without obvious risks
- **Risky**: Commands with absolute paths, directory traversal attempts, or potentially
  dangerous operations

Risky commands are blocked by default to prevent unintended filesystem operations or
system changes. This adds a layer of protection when working with AI-suggested commands.

The safety checker uses `bashlex` to parse and analyze commands and arguments, checking
for:

- Command presence in a predefined safe list
- Use of absolute vs. relative paths
- Directory traversal attempts (using `..` to move outside the working directory)

This helps ensure that StreetRace operates within the intended working directory and
with known-safe commands.

### Agent System

StreetRace includes a modular agent system that allows for specialized agents to be
discovered and used.

#### Agent Discovery

The `list_agents` tool allows the assistant to discover available agents in the system.
Agents are searched for in the following locations:

- `./agents/` (relative to the current working directory)
- `../../agents/` (relative to the src/streetrace/app.py)

#### Creating Custom Agents

StreetRace supports two ways to create custom agents:

##### Option 1: Using the StreetRaceAgent Interface (Recommended)

1. Create a directory for your agent in the `./agents/` folder (e.g.,
   `./agents/my_agent/`)
2. Create an `agent.py` file with a class that inherits from `StreetRaceAgent` and
   implements:

   - `get_agent_card()` - Returns metadata about the agent (name, description,
     capabilities)
   - `get_required_tools()` - Returns a list of tools the agent needs
   - `create_agent()` - Creates the actual agent instance with the provided model and
     tools

3. Add a `README.md` file with documentation for your agent

Example agent class:

```python
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard

class MyAgent(StreetRaceAgent):
    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="My Agent",
            description="A specialized agent that does something useful",
            capabilities=["capability1", "capability2"],
        )

    async def get_required_tools(self) -> list[str]:
        return [
            "streetrace:fs_tool::read_file",
            "streetrace:fs_tool::write_file",
        ]

    async def create_agent(self, model_factory, tools) -> BaseAgent:
        model = model_factory.get_default_model()
        return Agent(
            name="My Agent",
            model=model,
            description="My specialized agent",
            instruction="You are a specialized agent that does X, Y, and Z...",
            tools=tools,
        )
```

##### Option 2: Legacy Approach (Basic Functions)

1. Create a directory for your agent in the `./agents/` folder (e.g.,
   `./agents/my_agent/`)
2. Create an `agent.py` file with these required functions:

   - `get_agent_metadata()` - Returns a dictionary with `name` and `description` keys
   - `run_agent(input_text: str)` - Implements the agent's functionality

3. Add a `README.md` file with documentation for your agent

#### Running Agents

The `run_agent` tool allows the primary assistant to execute specialized agents:

```python
run_agent(
    agent_name="Hello World",
    input_text="What files are in this directory?",
    model_name="default"  # Optional, defaults to the default model
)
```

This enables a hierarchical agent system where the primary StreetRace assistant can
delegate tasks to specialized agents.

#### Tool Configuration

Tools available to agents are defined in the `./tools/tools.yaml` configuration file.
This file specifies:

- Tool name and description
- Source type (e.g., 'local' for Python modules or 'mcp' for external services)
- Module and function name for local tools
- Whether the tool requires agent capabilities

The configuration makes it easy to add, modify, or disable tools without changing code.

#### Tool Discovery

The `list_tools` tool provides information about available tools that can be provided to
agents. This helps the assistant understand what capabilities are available in the
system.

The tool returns a list of available tools with:

- Tool name
- Description
- Whether the tool requires agent capabilities

## GitHub Workflow: Startup Profiling on PR

On every pull request, the project runs `scripts/profile_startup.py` on both the PR branch and the main branch and compares their startup performance. The results are posted as a comment on the PR for fast visibility and regression detection.

How it works:
- On each PR, the CI workflow:
  - Checks out the PR branch, installs dependencies, and runs `profile_startup.py --json --save=profile_pr.json`.
  - Checks out the main branch at HEAD, installs dependencies, and runs the profiler to `profile_main.json`.
  - Uses `scripts/compare_profiles.py` to generate a Markdown summary showing deltas for startup performance key metrics.
  - Posts the difference as a persistent, auto-updating PR comment.

This ensures that startup regressions are caught early and remediation advice is visible to contributors and reviewers.
