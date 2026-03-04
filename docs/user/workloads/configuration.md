# Workload Configuration

This guide covers how to configure workload discovery, search paths, naming conventions,
and environment variables.

## Search Paths

StreetRace searches for agents in multiple locations. The search order determines priority
when agents with the same name exist in multiple locations.

### Default Search Order

1. **Custom paths** - Directories in `STREETRACE_AGENT_PATHS` (highest priority)
2. **Current directory** - `./agents`, `.`, `.streetrace/agents`
3. **Home directory** - `~/.streetrace/agents`
4. **Bundled agents** - Built-in agents shipped with StreetRace (lowest priority)

### How Priority Works

When you request an agent by name, StreetRace searches each location in order. The first
match wins. This allows you to:

- Override bundled agents with project-specific versions
- Share agents across projects via the home directory
- Use custom paths for team-shared agent libraries

**Example**: If `my_agent` exists in both `~/.streetrace/agents/` and `./agents/`:

```bash
poetry run streetrace --agent=my_agent "Hello"
# Uses ./agents/my_agent (cwd has higher priority than home)
```

## Environment Variables

### STREETRACE_AGENT_PATHS

Add custom search paths for agent discovery.

**Format**: Colon-separated list of directory paths

```bash
export STREETRACE_AGENT_PATHS="/path/to/team/agents:/path/to/personal/agents"
```

Custom paths have the **highest priority**, searched before any default locations.

**Example**:
```bash
# Add a shared team agents directory
export STREETRACE_AGENT_PATHS="/shared/team/agents"

# Multiple custom paths
export STREETRACE_AGENT_PATHS="/org/agents:/team/agents:/personal/agents"
```

### STREETRACE_AGENT_URI_AUTH

Authorization header for loading agents from HTTP URLs.

```bash
export STREETRACE_AGENT_URI_AUTH="Bearer your-token-here"
```

Used when loading YAML agents from remote URLs:

```bash
poetry run streetrace --agent=https://example.com/agents/my_agent.yaml "Hello"
```

### STREETRACE_LOG_LEVEL

Control logging verbosity to debug agent discovery issues.

```bash
# See detailed discovery and loading information
export STREETRACE_LOG_LEVEL=DEBUG

# Normal operation (default)
export STREETRACE_LOG_LEVEL=INFO

# Errors only
export STREETRACE_LOG_LEVEL=ERROR
```

With `DEBUG` logging, you'll see:

```
DEBUG Loading DSL file: ./agents/my_agent.sr
DEBUG Loaded DSL definition 'my_agent' from ./agents/my_agent.sr
DEBUG Discovered agent 'my_agent' (dsl) in cwd
```

## Naming Conventions

### Agent Names

Agent names are derived from:

- **DSL**: Filename stem (e.g., `my_agent.sr` -> `my_agent`)
- **YAML**: The `name` field in the YAML file
- **Python**: The `name` from `get_agent_card()` return value

**Best Practices**:

```
Good names:
  code_reviewer
  project_helper
  git_assistant

Avoid:
  my agent (spaces)
  agent#1 (special characters)
  Agent (capitalization inconsistency)
```

### Name Resolution

Names are matched case-insensitively:

```bash
# These all find the same agent if it exists
poetry run streetrace --agent=My_Agent "Hello"
poetry run streetrace --agent=my_agent "Hello"
poetry run streetrace --agent=MY_AGENT "Hello"
```

### Special Names

- **default** - Alias for the default agent (`Streetrace_Coding_Agent`)

```bash
# These are equivalent
poetry run streetrace --agent=default "Hello"
poetry run streetrace "Hello"
```

## Directory Structure

### Recommended Project Structure

Organize agents in your project:

```
my_project/
  agents/
    code_review.sr       # DSL agent
    documentation.yaml   # YAML agent
    custom_tool/         # Python agent
      agent.py
  .streetrace/
    agents/              # Alternative location
      helper.yaml
  src/
    ...
```

### User-Level Agents

Agents available across all projects:

```
~/.streetrace/
  agents/
    personal_helper.yaml
    team_tools.sr
    my_custom_agent/
      agent.py
```

## File Format Detection

StreetRace auto-detects the format based on file extension or directory structure:

| Pattern | Format | Example |
|---------|--------|---------|
| `*.sr` | DSL | `agent.sr` |
| `*.yaml`, `*.yml` | YAML | `agent.yaml` |
| Directory with `agent.py` | Python | `my_agent/agent.py` |

### Loading by Path

When you specify a file path, format is detected automatically:

```bash
# DSL (detected by .sr extension)
poetry run streetrace ./agents/helper.sr "Hello"

# YAML (detected by .yaml extension)
poetry run streetrace ./agents/helper.yaml "Hello"

# Python (detected by directory with agent.py)
poetry run streetrace ./agents/helper "Hello"
```

## Discovery Cache

Agent discovery results are cached for performance. The cache is cleared when:

- StreetRace starts a new session
- You modify the search paths
- You explicitly request rediscovery

To force rediscovery, restart StreetRace or use a new session.

## Configuration File Support

### Project-Level Configuration

Create `.streetrace/config.yaml` in your project root:

```yaml
# Default agent for this project
default_agent: project_helper

# Additional search paths (relative to project root)
agent_paths:
  - ./custom_agents
  - ./shared/agents
```

### User-Level Configuration

Create `~/.streetrace/config.yaml` for global settings:

```yaml
# Default model for all agents
default_model: anthropic/claude-sonnet

# Global search paths
agent_paths:
  - ~/my-agents
```

**Note**: Project-level settings override user-level settings.

## HTTP Agent Loading

Load agents directly from URLs:

```bash
# Load YAML agent from URL
poetry run streetrace --agent=https://example.com/agents/helper.yaml "Hello"

# With authentication
export STREETRACE_AGENT_URI_AUTH="Bearer token123"
poetry run streetrace --agent=https://api.example.com/agents/helper.yaml "Hello"
```

HTTP agents must be YAML format. DSL and Python agents require local files.

## Performance Considerations

### Compile-on-Load

DSL files are compiled during discovery, not at execution time. This means:

- Startup may be slightly slower if you have many DSL files
- Invalid DSL files are rejected immediately
- You get clear error messages pointing to syntax problems

### Lazy Loading

Python and YAML agents are loaded when first used, not during discovery. This improves
startup time when you have many agents but only use a few.

### Caching

- Discovery results are cached per session
- Compiled DSL definitions are cached in memory
- Model connections are pooled and reused

## Debugging Configuration

### List Discovered Agents

See what agents are available and where they came from:

```bash
poetry run streetrace --list-agents
```

Output:
```
Available agents:
  Streetrace_Coding_Agent (yaml) [bundled]
  code_reviewer (dsl) [cwd]
  helper (yaml) [home]
```

### Enable Debug Logging

See detailed discovery information:

```bash
export STREETRACE_LOG_LEVEL=DEBUG
poetry run streetrace --list-agents
```

### Check Search Paths

Verify which paths are being searched:

```bash
export STREETRACE_LOG_LEVEL=DEBUG
poetry run streetrace --agent=nonexistent "test" 2>&1 | grep -i "search\|path\|discover"
```

## Common Configuration Patterns

### Team Shared Agents

Share agents across a team via a network drive or git repository:

```bash
# Clone team agents
git clone https://github.com/team/agents.git ~/team-agents

# Add to search path
export STREETRACE_AGENT_PATHS="$HOME/team-agents"
```

### Project-Specific Override

Override a bundled agent for a specific project:

```bash
# Create local version
mkdir -p ./agents
cp $(streetrace --show-agent-path Streetrace_Coding_Agent) ./agents/
# Edit ./agents/Streetrace_Coding_Agent.yaml

# Local version now takes priority
poetry run streetrace "Hello"  # Uses ./agents/ version
```

### Multiple Environments

Use different agents for development vs production:

```bash
# Development
export STREETRACE_AGENT_PATHS="./agents/dev"

# Production
export STREETRACE_AGENT_PATHS="./agents/prod"
```

## See Also

- [Getting Started](getting-started.md) - Introduction to workloads
- [Examples](examples.md) - Complete example workloads
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
