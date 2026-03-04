# Flow Event Yielding Test Environment Setup

This document describes how to set up your environment for manual end-to-end testing of the
Flow Event Yielding feature.

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
# Anthropic (recommended for testing)
export ANTHROPIC_API_KEY="your-api-key"

# OR OpenAI
export OPENAI_API_KEY="your-api-key"

# OR Gemini
export GOOGLE_API_KEY="your-api-key"
```

## Environment Variables

### Required for Testing

```bash
# Enable debug logging to see event details
export STREETRACE_LOG_LEVEL=DEBUG

# API key for your LLM provider
export ANTHROPIC_API_KEY="your-key"
```

### Optional Configuration

```bash
# Custom agent search paths (for isolated testing)
export STREETRACE_AGENT_PATHS="/path/to/test/agents"
```

## Test Directory Structure

Create a dedicated test directory:

```bash
mkdir -p ~/streetrace-flow-event-tests/agents
cd ~/streetrace-flow-event-tests
```

The recommended structure:

```
~/streetrace-flow-event-tests/
  agents/
    single_agent_flow.sr      # Flow with one agent
    multi_agent_flow.sr       # Flow with multiple agents
    call_llm_flow.sr          # Flow with call llm
    mixed_flow.sr             # Mixed agents and LLM calls
    nested_flow.sr            # Nested flow calls
```

## Creating Test Artifacts

### Single Agent Flow

**File**: `agents/single_agent_flow.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt analyze:
    List the files in the current directory and describe what you find.
    Be concise.

agent analyzer:
    tools fs
    instruction analyze

flow main:
    $result = run agent analyzer $input_prompt
    return $result
```

### Multi-Agent Flow

**File**: `agents/multi_agent_flow.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt analyze:
    List the files in the current directory.

prompt summarize:
    Summarize the following analysis in one sentence:
    ${analysis}

agent analyzer:
    tools fs
    instruction analyze

agent summarizer:
    instruction summarize

flow main:
    $analysis = run agent analyzer $input_prompt
    $summary = run agent summarizer $analysis
    return $summary
```

### Call LLM Flow

**File**: `agents/call_llm_flow.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet
model fast = anthropic/claude-haiku

prompt greet:
    Say hello to the user in a friendly way.
    User message: ${input_prompt}

prompt farewell using model "fast":
    Say goodbye briefly.

flow main:
    $greeting = call llm greet
    $goodbye = call llm farewell
    return $goodbye
```

### Mixed Flow

**File**: `agents/mixed_flow.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt analyze:
    Analyze the project structure.

prompt quick_summary:
    Provide a one-line summary of: ${data}

agent researcher:
    tools fs
    instruction analyze

flow main:
    $data = run agent researcher $input_prompt
    $summary = call llm quick_summary
    return $summary
```

### Nested Flow

**File**: `agents/nested_flow.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt greet:
    Say hello.

prompt process:
    Process this: ${input_prompt}

flow inner:
    $result = call llm process
    return $result

flow main:
    $greeting = call llm greet
    run flow inner
    return $greeting
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
cd ~/streetrace-flow-event-tests
poetry run streetrace --list-agents
# Should show your test agents
```

### Verify Event Rendering

```bash
cd ~/streetrace-flow-event-tests
poetry run streetrace agents/single_agent_flow.sr "List files" 2>&1 | head -30
# Should show [Function Call] and [Function Result] events
```

## Cleanup

After testing, remove the test directory:

```bash
rm -rf ~/streetrace-flow-event-tests
```

Reset environment variables:

```bash
unset STREETRACE_LOG_LEVEL
unset STREETRACE_AGENT_PATHS
```

## Reference Documents

- `docs/tasks/017-dsl/flow-event-yielding/tasks.md`: Task definition, 2026-01-27
- `docs/tasks/017-dsl/flow-event-yielding/todo.md`: Implementation progress, 2026-01-27
- `docs/dev/dsl/flow-events/overview.md`: Developer architecture documentation

## See Also

- [Test Scenarios](scenarios.md) - Test scenarios to execute
- [Workload Testing Guide](../../workloads/testing-guide.md) - General workload testing
