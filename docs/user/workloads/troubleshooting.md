# Workload Troubleshooting

This guide helps you diagnose and resolve common issues when working with StreetRace
workloads.

## Agent Not Found

### Symptoms

```
Error: Agent 'my_agent' not found.
Details:
  - Agent 'my_agent' not found in locations: cwd, home, bundled
Try --list-agents to see available agents.
```

### Solutions

1. **Check the agent name**

   Verify the exact name of your agent:
   ```bash
   poetry run streetrace --list-agents | grep -i my_agent
   ```

2. **Check the file location**

   Ensure your agent file is in a search path:
   ```bash
   # DSL agent should be in one of these locations:
   ./agents/my_agent.sr
   ./.streetrace/agents/my_agent.sr
   ~/.streetrace/agents/my_agent.sr

   # YAML agent:
   ./agents/my_agent.yaml

   # Python agent:
   ./agents/my_agent/agent.py
   ```

3. **Check file permissions**

   ```bash
   ls -la ./agents/my_agent.sr
   # Should be readable
   ```

4. **Check for syntax errors**

   For DSL files, syntax errors prevent loading:
   ```bash
   # Try loading directly to see error messages
   poetry run streetrace ./agents/my_agent.sr "test"
   ```

5. **Enable debug logging**

   ```bash
   export STREETRACE_LOG_LEVEL=DEBUG
   poetry run streetrace --agent=my_agent "test" 2>&1 | head -50
   ```

## DSL Compilation Errors

### Syntax Error

**Symptoms**:
```
DslSyntaxError: Unexpected token 'foo' at line 5
```

**Solutions**:

1. Check the indicated line number for typos
2. Verify you have the `streetrace v1` header
3. Ensure proper indentation (spaces, not tabs)
4. Check for missing colons after block declarations

**Common syntax issues**:

```streetrace
# Wrong: Missing colon
prompt greeting
    Hello

# Correct: Colon after name
prompt greeting:
    Hello

# Wrong: Missing version header
model main = anthropic/claude-sonnet

# Correct: Version header required
streetrace v1

model main = anthropic/claude-sonnet
```

### Semantic Error

**Symptoms**:
```
DslSemanticError: Agent references undefined prompt 'missing_prompt'
```

**Solutions**:

1. Define all referenced prompts, models, and tools
2. Check for typos in reference names
3. Ensure definitions appear before usage

**Example fix**:

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

# Define the prompt BEFORE the agent uses it
prompt greeting:
    Hello, how can I help?

agent:
    instruction greeting  # References 'greeting' prompt
```

## YAML Agent Errors

### Validation Error

**Symptoms**:
```
AgentValidationError: Agent specification validation failed for ./agents/my_agent.yaml
```

**Solutions**:

1. Check required fields are present:
   ```yaml
   name: my_agent        # Required
   description: ...      # Required
   model: ...            # Required
   instruction: ...      # Required
   ```

2. Verify YAML syntax:
   ```bash
   # Check YAML is valid
   python -c "import yaml; yaml.safe_load(open('./agents/my_agent.yaml'))"
   ```

3. Check for indentation issues:
   ```yaml
   # Wrong: Inconsistent indentation
   name: my_agent
     description: test  # Shouldn't be indented

   # Correct: Consistent indentation
   name: my_agent
   description: test
   ```

### Reference Resolution Error

**Symptoms**:
```
Failed to resolve $ref: ./base_agent.yaml
```

**Solutions**:

1. Verify the referenced file exists
2. Use paths relative to the current file
3. Check file permissions

```yaml
# Correct: Relative path from current file
$ref: ./base_agent.yaml

# Also correct: Absolute path
$ref: /path/to/base_agent.yaml
```

## Python Agent Errors

### Module Import Error

**Symptoms**:
```
ValueError: Failed to import agent module from ./agents/my_agent: ModuleNotFoundError
```

**Solutions**:

1. Verify `agent.py` exists in the directory:
   ```bash
   ls ./agents/my_agent/agent.py
   ```

2. Check for syntax errors:
   ```bash
   python -m py_compile ./agents/my_agent/agent.py
   ```

3. Verify required imports are available:
   ```bash
   poetry run python -c "from streetrace.agents.street_race_agent import StreetRaceAgent"
   ```

### No StreetRaceAgent Found

**Symptoms**:
```
ValueError: No StreetRaceAgent implementation found in ./agents/my_agent
```

**Solutions**:

Your `agent.py` must contain a class that inherits from `StreetRaceAgent`:

```python
from streetrace.agents.street_race_agent import StreetRaceAgent

class MyAgent(StreetRaceAgent):  # Must inherit from StreetRaceAgent
    def get_agent_card(self):
        ...

    async def create_agent(self, model_factory, tool_provider, system_context):
        ...
```

### Agent Card Error

**Symptoms**:
```
ValueError: Failed to get agent card from ./agents/my_agent
```

**Solutions**:

1. Ensure `get_agent_card()` returns a valid `StreetRaceAgentCard`:
   ```python
   from streetrace.agents.street_race_agent_card import StreetRaceAgentCard

   def get_agent_card(self) -> StreetRaceAgentCard:
       return StreetRaceAgentCard(
           name="my_agent",
           description="My agent description",
       )
   ```

2. Check for exceptions in `get_agent_card()`:
   ```python
   # Don't do this - will cause errors
   def get_agent_card(self):
       raise NotImplementedError()  # Will fail during loading
   ```

## Tools Not Working

### Agent Cannot Access Tools

**Symptoms**:
- Agent says it cannot access files or run commands
- Tool calls fail silently
- Agent apologizes for lacking capabilities

**Solutions**:

1. **DSL**: Ensure tools are declared:
   ```streetrace
   tool fs = builtin streetrace.filesystem

   agent:
       tools fs  # Must list tools to use
       instruction my_prompt
   ```

2. **YAML**: Ensure tools are listed:
   ```yaml
   tools:
     - streetrace.filesystem
     - streetrace.cli
   ```

3. **Python**: Get tools from provider:
   ```python
   async def create_agent(self, model_factory, tool_provider, system_context):
       tools = await tool_provider.get_tools(["streetrace.filesystem"])
       return LlmAgent(
           name="my_agent",
           model=model.model_id,
           instruction="...",
           tools=tools,
       )
   ```

### Flow-Invoked Agent Missing Tools

**Symptoms**:
- Agent works when run directly but not when called from a flow
- `run agent` in flows produces "no tools available" responses

**Solutions**:

Ensure the agent has tools declared in its definition, not just passed at runtime:

```streetrace
tool fs = builtin streetrace.filesystem

agent file_helper:
    tools fs                    # Tools must be declared here
    instruction file_prompt

flow main:
    $result = run agent file_helper "List files"
    return $result
```

## Session Errors

### Session Service Not Set

**Symptoms**:
```
ValueError: session_service is required to create workloads
```

**Solutions**:

This is usually an internal error. If you see it:

1. Ensure you're using the latest version of StreetRace
2. Check if you're calling internal APIs directly without proper initialization

### Session Persistence Issues

**Symptoms**:
- Agent doesn't remember previous messages
- Context is lost between turns

**Solutions**:

1. Ensure you're using the same session:
   ```bash
   # Use --continue to resume a session
   poetry run streetrace --continue "Follow up question"
   ```

2. Check session storage permissions:
   ```bash
   ls -la ~/.streetrace/sessions/
   ```

## Performance Issues

### Slow Agent Discovery

**Symptoms**:
- Long startup time before agent responds
- `--list-agents` takes many seconds

**Solutions**:

1. Reduce the number of files in search paths
2. Remove invalid DSL files (they're compiled during discovery)
3. Use specific agent paths instead of broad directories:
   ```bash
   # Instead of searching entire home directory
   # Set specific path
   export STREETRACE_AGENT_PATHS="~/.streetrace/agents"
   ```

### Memory Issues

**Symptoms**:
- StreetRace uses excessive memory
- Crashes with out-of-memory errors

**Solutions**:

1. Reduce the number of concurrent agents
2. Close unused sessions
3. Check for large files being read into agent context

## Debug Logging

Enable detailed logging to diagnose issues:

```bash
# Maximum verbosity
export STREETRACE_LOG_LEVEL=DEBUG

# Run your command
poetry run streetrace --agent=my_agent "test" 2>&1 | tee debug.log

# Search for specific issues
grep -i "error\|fail\|warn" debug.log
```

### Key Log Patterns

| Pattern | Meaning |
|---------|---------|
| `Loading DSL file` | DSL compilation starting |
| `Loaded DSL definition` | DSL compiled successfully |
| `Discovered agent` | Agent found during discovery |
| `Failed to load` | Loading error (check details) |
| `Creating DslAgentWorkflow` | DSL workload being created |
| `Creating BasicAgentWorkload` | YAML/Python workload being created |

## Getting Help

If you can't resolve an issue:

1. **Check existing issues**: Search the GitHub issues for similar problems
2. **Enable debug logging**: Capture the full debug output
3. **Create a minimal reproduction**: Isolate the problem to a small example
4. **Report the issue**: Include:
   - StreetRace version (`poetry run streetrace --version`)
   - Python version (`python --version`)
   - Operating system
   - Full error message and stack trace
   - Minimal reproduction case

## See Also

- [Getting Started](getting-started.md) - Introduction to workloads
- [Configuration](configuration.md) - Search paths and environment variables
- [Examples](examples.md) - Working example workloads
- [DSL Troubleshooting](../dsl/troubleshooting.md) - DSL-specific issues
