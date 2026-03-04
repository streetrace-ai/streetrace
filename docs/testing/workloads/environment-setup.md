# Workload Abstraction Test Environment Setup

This document describes how to set up your environment for manual end-to-end testing
of the Workload Abstraction feature.

## Prerequisites

### Software Requirements

1. **Python 3.10+**
   ```bash
   python --version
   # Python 3.10.x or higher
   ```

2. **Poetry** for dependency management
   ```bash
   poetry --version
   # Poetry 1.x
   ```

3. **StreetRace with development dependencies**
   ```bash
   cd /path/to/streetrace
   poetry install
   ```

### API Keys

Configure at least one LLM provider:

```bash
# Anthropic (recommended)
export ANTHROPIC_API_KEY="your-api-key"

# OR OpenAI
export OPENAI_API_KEY="your-api-key"

# OR Gemini
export GOOGLE_API_KEY="your-api-key"
```

## Environment Variables

### Required for Testing

```bash
# Enable debug logging to see workload creation details
export STREETRACE_LOG_LEVEL=DEBUG

# API key for your LLM provider
export ANTHROPIC_API_KEY="your-key"
```

### Optional Configuration

```bash
# Custom agent search paths (for isolated testing)
export STREETRACE_AGENT_PATHS="/path/to/test/agents"

# HTTP agent authorization (for URL loading tests)
export STREETRACE_AGENT_URI_AUTH="Bearer test-token"
```

## Test Directory Structure

Create a dedicated test directory:

```bash
mkdir -p ~/streetrace-workload-tests/agents
cd ~/streetrace-workload-tests
```

The recommended structure:

```
~/streetrace-workload-tests/
  agents/
    basic_dsl.sr           # DSL test agent
    basic_yaml.yaml        # YAML test agent
    basic_python/          # Python test agent
      agent.py
    flow_tools.sr          # DSL with tools
    delegate_pattern.sr    # Multi-agent delegation
    use_pattern.sr         # Agent-as-tool pattern
    entry_main.sr          # Entry point: main flow
    entry_default.sr       # Entry point: default agent
    entry_first.sr         # Entry point: first agent
    invalid_syntax.sr      # Invalid DSL for error testing
```

## Creating Test Artifacts

### Basic DSL Agent

**File**: `agents/basic_dsl.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting:
    You are a helpful test assistant. Respond with "DSL agent responding."

agent:
    instruction greeting
```

### Basic YAML Agent

**File**: `agents/basic_yaml.yaml`

```yaml
name: basic_yaml_agent
description: Basic YAML test agent
model: anthropic/claude-sonnet
instruction: |
  You are a helpful test assistant. Respond with "YAML agent responding."
```

### Basic Python Agent

**File**: `agents/basic_python/agent.py`

```python
from google.adk.agents import LlmAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


class BasicPythonAgent(StreetRaceAgent):
    """Basic Python test agent."""

    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="basic_python_agent",
            description="Basic Python test agent",
        )

    async def create_agent(self, model_factory, tool_provider, system_context):
        model = model_factory.get_current_model()
        return LlmAgent(
            name="basic_python_agent",
            model=model.model_id,
            instruction="You are a test assistant. Respond with 'Python agent responding.'",
        )
```

### DSL Agent with Tools

**File**: `agents/flow_tools.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.filesystem

prompt file_check:
    You have filesystem access. List the files in the current directory.
    Be concise.

agent file_checker:
    tools fs
    instruction file_check

flow main:
    $result = run agent file_checker $message
    return $result
```

### Delegation Pattern Agent

**File**: `agents/delegate_pattern.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt coordinator:
    You are a coordinator. For technical questions, delegate to specialist.
    Say "Delegating to specialist" before doing so.

prompt specialist:
    You are a Python specialist. Respond with "Specialist responding."

agent coordinator:
    delegate specialist
    instruction coordinator

agent specialist:
    instruction specialist

flow main:
    $result = run agent coordinator $message
    return $result
```

### Use Pattern Agent

**File**: `agents/use_pattern.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt lead:
    You are a lead agent. Use math_helper tool for calculations.
    Say "Using helper" when you call it.

prompt helper:
    You are a math helper. Calculate what's asked and return the result.

agent lead:
    use math_helper
    instruction lead

agent math_helper:
    instruction helper

flow main:
    $result = run agent lead $message
    return $result
```

### Entry Point Test Agents

**File**: `agents/entry_main.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

flow main:
    log "Main flow executed"
    return "Entry: main flow"

agent other:
    instruction other_prompt

prompt other_prompt:
    You should not be called.
```

**File**: `agents/entry_default.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

agent:
    instruction default_prompt

agent named_agent:
    instruction named_prompt

prompt default_prompt:
    Respond with "Entry: default agent"

prompt named_prompt:
    Respond with "Entry: named agent"
```

**File**: `agents/entry_first.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

agent first_agent:
    instruction first_prompt

agent second_agent:
    instruction second_prompt

prompt first_prompt:
    Respond with "Entry: first agent"

prompt second_prompt:
    Respond with "Entry: second agent"
```

### Invalid DSL for Error Testing

**File**: `agents/invalid_syntax.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

# Missing colon - intentional syntax error
prompt greeting
    Hello world
```

## Verification Commands

Run these commands to verify your environment is set up correctly:

### Check StreetRace Installation

```bash
poetry run streetrace --version
```

### Check Debug Logging

```bash
export STREETRACE_LOG_LEVEL=DEBUG
poetry run streetrace --list-agents 2>&1 | head -20
# Should show DEBUG log lines
```

### Check API Key Configuration

```bash
poetry run streetrace "Say hello" --model=anthropic/claude-sonnet
# Should get a response without API errors
```

### Check Test Agent Discovery

```bash
cd ~/streetrace-workload-tests
poetry run streetrace --list-agents
# Should show your test agents
```

## Cleanup

After testing, remove the test directory:

```bash
rm -rf ~/streetrace-workload-tests
```

Reset environment variables:

```bash
unset STREETRACE_LOG_LEVEL
unset STREETRACE_AGENT_PATHS
```

## Reference Documents

- `docs/tasks/017-dsl/workload-abstraction/task.md`: Task definition, 2026-01-21
- `docs/tasks/017-dsl/workload-abstraction/todo.md`: Implementation progress, 2026-01-21
- `src/streetrace/workloads/`: Implementation source files

## See Also

- [Scenarios](scenarios.md) - Test scenarios to execute
- [Testing Guide](testing-guide.md) - General workload testing guide
