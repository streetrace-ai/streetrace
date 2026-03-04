# Workload Protocol Testing Guide

Manual end-to-end testing guide for the Workload Protocol feature. This document covers
scenarios to validate that the unified workload execution system works correctly.

## Feature Scope

The Workload Protocol unifies agent execution in StreetRace. Key behaviors to test:

1. **Basic workload execution**: Agents execute via the Workload Protocol
2. **Tool access in flows**: Agents called via `run agent` have their tools
3. **Agentic patterns**: `delegate` and `use` work in flow-invoked agents
4. **Entry point selection**: Correct selection of main flow, default agent, or first agent
5. **Backward compatibility**: Existing Python/YAML agents continue to work

## Reference Documents

- `docs/tasks/017-dsl/agent-execution/tasks.md`: Primary design document, 2026-01-21
- `docs/tasks/017-dsl/agent-execution/todo.md`: Implementation plan, 2026-01-21
- `docs/tasks/017-dsl/agent-execution/task.md`: Task definition, 2026-01-21

## Environment Setup

### Prerequisites

1. StreetRace installed with development dependencies:
   ```bash
   poetry install
   ```

2. API key configured for your LLM provider:
   ```bash
   export ANTHROPIC_API_KEY="your-key"
   # or
   export OPENAI_API_KEY="your-key"
   ```

3. Working directory with test agents:
   ```bash
   mkdir -p ./agents
   ```

### Debug Logging

Enable debug logging to see workload execution details:

```bash
export STREETRACE_LOG_LEVEL=DEBUG
```

## Test Scenarios

### Scenario 1: Basic DSL Agent Execution

**Purpose**: Verify DSL agents execute through the Workload Protocol.

**Input File**: `agents/basic_agent.sr`
```streetrace
model main = anthropic/claude-sonnet

agent:
    instruction greeting_prompt

prompt greeting_prompt:
    You are a helpful assistant. Respond concisely.
```

**Test Command**:
```bash
poetry run streetrace --agent=basic_agent "Say hello"
```

**Expected Behavior**:
- Agent responds with a greeting
- Debug log shows: `Creating DslAgentWorkflow`
- Debug log shows: `Loading agent 'basic_agent' (dsl)`

**Verification**:
```bash
poetry run streetrace --agent=basic_agent "Say hello" 2>&1 | grep -E "(Creating|Loading)"
```

---

### Scenario 2: Tool Access in Flow-Invoked Agent

**Purpose**: Verify agents called via `run agent` in flows have their tools.

**Input File**: `agents/flow_tools.sr`
```streetrace
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

agent file_checker:
    tools fs
    instruction file_check_prompt

flow main:
    $result = run agent file_checker "List files in the current directory"
    return $result

prompt file_check_prompt:
    You have filesystem access. Use the tools available to answer questions
    about files. Be concise in your response.
```

**Test Command**:
```bash
poetry run streetrace agents/flow_tools.sr
```

**Expected Behavior**:
- Agent lists files in the current directory (uses `fs` tool)
- Response contains actual file names from the directory
- No errors about missing tools

**Verification**:
Look for tool calls in the output. The agent should actually read files, not apologize for
lacking access.

---

### Scenario 3: Agentic Pattern - Delegate

**Purpose**: Verify `delegate` pattern works for flow-invoked agents.

**Input File**: `agents/delegate_pattern.sr`
```streetrace
model main = anthropic/claude-sonnet

agent coordinator:
    delegate specialist
    instruction coordinator_prompt

agent specialist:
    instruction specialist_prompt

flow main:
    $result = run agent coordinator "I need help with a technical question about Python async"
    return $result

prompt coordinator_prompt:
    You are a coordinator. For technical questions, delegate to the specialist.

prompt specialist_prompt:
    You are a Python async specialist. Provide expert answers about async/await.
```

**Test Command**:
```bash
poetry run streetrace agents/delegate_pattern.sr
```

**Expected Behavior**:
- Coordinator delegates to specialist
- Debug log shows both agents being created
- Response contains specialized async knowledge

---

### Scenario 4: Agentic Pattern - Use

**Purpose**: Verify `use` pattern works for flow-invoked agents.

**Input File**: `agents/use_pattern.sr`
```streetrace
model main = anthropic/claude-sonnet

agent lead:
    use helper
    instruction lead_prompt

agent helper:
    instruction helper_prompt

flow main:
    $result = run agent lead "What's 2 + 2? Use your helper if needed."
    return $result

prompt lead_prompt:
    You are a lead agent. You can use the helper agent as a tool to get answers.
    Call helper when you need assistance.

prompt helper_prompt:
    You are a math helper. Answer math questions.
```

**Test Command**:
```bash
poetry run streetrace agents/use_pattern.sr
```

**Expected Behavior**:
- Lead agent can invoke helper as a tool
- Debug log shows AgentTool being created for helper
- Response comes from lead (possibly using helper)

---

### Scenario 5: Entry Point - Main Flow

**Purpose**: Verify `flow main:` is selected as entry point.

**Input File**: `agents/entry_main.sr`
```streetrace
model main = anthropic/claude-sonnet

flow main:
    log "Main flow executed"
    return "Flow completed"

agent other:
    instruction other_prompt

prompt other_prompt:
    You should not be called.
```

**Test Command**:
```bash
poetry run streetrace agents/entry_main.sr 2>&1
```

**Expected Behavior**:
- Log shows "Main flow executed"
- Agent `other` is NOT invoked
- Output is "Flow completed"

---

### Scenario 6: Entry Point - Default Agent

**Purpose**: Verify unnamed agent is selected when no main flow exists.

**Input File**: `agents/entry_default.sr`
```streetrace
model main = anthropic/claude-sonnet

agent:
    instruction default_prompt

agent named_agent:
    instruction named_prompt

prompt default_prompt:
    You are the default agent. Say "Default agent responding."

prompt named_prompt:
    You are a named agent. Say "Named agent responding."
```

**Test Command**:
```bash
poetry run streetrace agents/entry_default.sr "Hello"
```

**Expected Behavior**:
- Response indicates default agent was used
- Named agent is NOT invoked

---

### Scenario 7: Entry Point - First Agent

**Purpose**: Verify first defined agent is selected when no main flow or default agent.

**Input File**: `agents/entry_first.sr`
```streetrace
model main = anthropic/claude-sonnet

agent first_agent:
    instruction first_prompt

agent second_agent:
    instruction second_prompt

prompt first_prompt:
    You are the first agent. Say "First agent responding."

prompt second_prompt:
    You are the second agent. Say "Second agent responding."
```

**Test Command**:
```bash
poetry run streetrace agents/entry_first.sr "Hello"
```

**Expected Behavior**:
- Response indicates first agent was used
- Second agent is NOT invoked

---

### Scenario 8: Backward Compatibility - YAML Agent

**Purpose**: Verify YAML agents still work through BasicAgentWorkload.

**Input File**: `agents/yaml_agent.yaml`
```yaml
name: yaml_test_agent
model: anthropic/claude-sonnet
instruction: |
  You are a YAML-defined agent. Say "YAML agent responding."
```

**Test Command**:
```bash
poetry run streetrace --agent=yaml_test_agent "Hello"
```

**Expected Behavior**:
- Agent responds correctly
- Debug log shows: `Creating BasicAgentWorkload`

---

### Scenario 9: WorkloadManager Discovery

**Purpose**: Verify WorkloadManager discovers agents correctly.

**Test Command**:
```bash
poetry run streetrace --list-agents
```

**Expected Behavior**:
- Lists all discovered agents from all locations
- Shows agent type (dsl, yaml, python)
- Shows agent location (cwd, home, bundled)

---

### Scenario 10: Error Handling - Agent Not Found

**Purpose**: Verify helpful error messages for missing agents.

**Test Command**:
```bash
poetry run streetrace --agent=nonexistent_agent "Hello" 2>&1
```

**Expected Behavior**:
- Error message includes agent name
- Error message lists searched locations
- Suggests `--list-agents` to see available agents

**Expected Output Pattern**:
```
Error: Agent 'nonexistent_agent' not found.
Details:
  - Agent 'nonexistent_agent' not found in locations: cwd, home, bundled
Try --list-agents to see available agents.
```

## Validation Checklist

Use this checklist to track test completion:

- [ ] Scenario 1: Basic DSL agent executes
- [ ] Scenario 2: Flow-invoked agent has tools
- [ ] Scenario 3: Delegate pattern works
- [ ] Scenario 4: Use pattern works
- [ ] Scenario 5: Main flow entry point
- [ ] Scenario 6: Default agent entry point
- [ ] Scenario 7: First agent entry point
- [ ] Scenario 8: YAML agent backward compatibility
- [ ] Scenario 9: WorkloadManager discovery
- [ ] Scenario 10: Error handling

## Debugging Tips

### Check Workload Type

Enable debug logging and look for these patterns:

```
# DSL Workload
Creating DslAgentWorkflow

# Basic Workload (YAML/Python)
Creating BasicAgentWorkload
```

### Verify Tool Resolution

Look for tool resolution in debug logs:

```
# Tools being resolved
Resolving tools for agent 'my_agent'

# Tool creation
Created tool: fs_tool
```

### Check Entry Point Selection

Look for entry point determination:

```
# Entry point selected
Entry point: flow/main
# or
Entry point: agent/default
# or
Entry point: agent/first_agent
```

### Verify Agent Creation via DslAgentFactory

For DSL agents, verify DslAgentFactory is used:

```
# Creating root agent via DslAgentFactory
Created DslAgentFactory for workflow from source.sr
Creating root agent with DslAgentFactory
```

## Common Issues

### Issue: Tools Not Working in Flow

**Symptom**: Agent says it cannot access tools when called from flow.

**Likely Cause**: Workflow not properly initialized.

**Debug**: Check that `agent_factory` is passed to DslAgentWorkflow constructor.

### Issue: Entry Point Not Selected Correctly

**Symptom**: Wrong agent or flow runs.

**Debug**: Add `log "Entry: xyz"` statements to verify which flow/agent runs.

### Issue: Session Errors

**Symptom**: Session-related errors during execution.

**Likely Cause**: `session_service` not passed to WorkloadManager.

**Debug**: Verify session_service is set before calling `create_workload()`.

## See Also

- `docs/dev/workloads/architecture.md`: Architecture documentation
- `docs/dev/workloads/api-reference.md`: API documentation
- `docs/user/workloads/index.md`: User-facing workload documentation
