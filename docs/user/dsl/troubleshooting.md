# Troubleshooting

This guide covers common errors when working with Streetrace DSL files and how to resolve
them.

## Error Code Reference

### E0001: Undefined Reference

**Error message:**

```
error[E0001]: undefined reference to model 'fast'
  --> my_agent.sr:15:18
     |
  15 |     using model "fast"
     |                  ^^^^
     |
     = help: defined models are: main, compact
```

**Cause:** You referenced a model, tool, agent, or prompt that doesn't exist.

**Solutions:**

1. Check for typos in the name
2. Ensure the definition appears before its use
3. Add the missing definition

```streetrace
# Fix: Define the model before using it
model fast = anthropic/haiku

prompt my_prompt using model "fast":
    ...
```

### E0002: Variable Used Before Definition

**Error message:**

```
error[E0002]: variable '$result' used before definition
  --> my_agent.sr:8:12
     |
   8 |     return $result
     |            ^^^^^^^
```

**Cause:** You referenced a variable that hasn't been assigned yet.

**Solutions:**

1. Initialize the variable before use
2. Check variable scoping (flow variables are local)
3. Define global variables in `on start do`

```streetrace
# Fix: Initialize before use
flow process:
    $result = run agent my_agent $input
    return $result
```

### E0003: Duplicate Definition

**Error message:**

```
error[E0003]: duplicate definition of model 'main'
  --> my_agent.sr:5:1
     |
   5 | model main = openai/gpt-4
     | ^^^^^^^^^^^^^^^^^^^^^^^^^
```

**Cause:** Two definitions have the same name.

**Solutions:**

1. Rename one of the definitions
2. Remove the duplicate
3. If importing, the local definition will override

```streetrace
# Fix: Use different names
model main = anthropic/claude-sonnet
model secondary = openai/gpt-4
```

### E0004: Type Mismatch

**Error message:**

```
error[E0004]: type mismatch: expected string, got int
  --> my_agent.sr:12:15
     |
  12 |     name: 42
     |           ^^
```

**Cause:** A value doesn't match the expected type.

**Solutions:**

1. Use the correct type
2. Check schema field definitions

```streetrace
# Fix: Use correct type
schema User:
    name: string    # Expects string
    age: int        # Expects int
```

### E0005: Import File Not Found

**Error message:**

```
error[E0005]: import file not found: ./missing.sr
  --> my_agent.sr:1:1
     |
   1 | import ./missing.sr
     | ^^^^^^^^^^^^^^^^^^^^
```

**Cause:** The imported file doesn't exist at the specified path.

**Solutions:**

1. Check the file path is correct
2. Ensure the file exists
3. Use relative paths from the current file

```streetrace
# Fix: Correct the path
import ./agents/my_agent.sr
```

### E0006: Circular Import

**Error message:**

```
error[E0006]: circular import detected: a.sr -> b.sr -> a.sr
  --> b.sr:1:1
     |
   1 | import ./a.sr
     | ^^^^^^^^^^^^^
```

**Cause:** Two files import each other, creating a cycle.

**Solutions:**

1. Restructure to avoid circular dependencies
2. Extract shared definitions to a third file
3. Use forward declarations where possible

```streetrace
# Fix: Extract shared definitions
# shared.sr - contains common definitions
# a.sr - imports shared.sr
# b.sr - imports shared.sr
```

### E0007: Invalid Token

**Error message:**

```
error[E0007]: invalid token or unexpected end of input
  --> my_agent.sr:10:5
     |
  10 |     @invalid syntax here
     |     ^
```

**Cause:** The parser encountered unexpected characters or the file ended unexpectedly.

**Solutions:**

1. Check for special characters that aren't valid
2. Ensure all blocks are properly closed
3. Verify string quotes are balanced

```streetrace
# Common issues:
# - Missing colon after definitions
# - Unclosed strings
# - Invalid characters

# Fix: Proper syntax
model main = anthropic/claude-sonnet  # Correct

agent:  # Don't forget the colon
    tools github
```

### E0008: Mismatched Indentation

**Error message:**

```
error[E0008]: mismatched indentation
  --> my_agent.sr:6:1
     |
   5 |     tools github
   6 | instruction my_prompt
     | ^
```

**Cause:** Indentation doesn't match the expected block structure.

**Solutions:**

1. Use consistent indentation (4 spaces recommended)
2. Don't mix tabs and spaces
3. Ensure block contents are indented

```streetrace
# Fix: Consistent indentation
agent:
    tools github
    instruction my_prompt  # Same indent level
```

### E0009: Invalid Guardrail Action

**Error message:**

```
error[E0009]: invalid guardrail action 'retry' in 'on input' context
  --> my_agent.sr:8:5
     |
   8 |     retry with "Please try again"
     |     ^^^^^
```

**Cause:** The guardrail action isn't valid in the current event handler.

**Solutions:**

1. Use the action in an appropriate context
2. Check the action availability table below

| Action | on input | on output | on tool-call | on tool-result |
|--------|----------|-----------|--------------|----------------|
| `mask` | Yes | Yes | No | Yes |
| `block` | Yes | Yes | Yes | Yes |
| `warn` | Yes | Yes | Yes | Yes |
| `retry` | No | Yes | No | No |

```streetrace
# Fix: Use retry in on output, not on input
on output do
    retry with "Please try again" if $score < 0.5
end
```

### E0010: Missing Required Property

**Error message:**

```
error[E0010]: missing required property 'instruction' in agent
  --> my_agent.sr:3:1
     |
   3 | agent my_agent:
     | ^^^^^^^^^^^^^^^
```

**Cause:** A required property wasn't provided.

**Solutions:**

1. Add the missing property
2. Check documentation for required fields

```streetrace
# Fix: Add required property
agent my_agent:
    tools github
    instruction my_prompt  # Required
```

### E0011: Circular Agent Reference

**Error message:**

```
error[E0011]: circular agent reference detected: agent_a -> agent_b -> agent_a
  --> my_agent.sr:6:1
```

**Cause:** Agents reference each other through `delegate` or `use` in a cycle.

**Solutions:**

1. Reorganize the agent hierarchy to remove cycles
2. Extract shared functionality to a separate agent
3. Use flows instead of agent-to-agent references

```streetrace
# Problem: Circular reference
agent agent_a:
    instruction a_prompt
    use agent_b

agent agent_b:
    instruction b_prompt
    use agent_a  # Creates cycle!

# Fix: Restructure to remove cycle
agent shared_helper:
    instruction helper_prompt

agent agent_a:
    instruction a_prompt
    use shared_helper

agent agent_b:
    instruction b_prompt
    use shared_helper
```

### W0002: Agent Has Both delegate and use

**Warning message:**

```
warning[W0002]: agent 'my_agent' has both delegate and use - this is unusual
  --> my_agent.sr:10:1
```

**Cause:** An agent uses both `delegate` (coordinator pattern) and `use` (hierarchical pattern).

**Why this warning?** Having both patterns on the same agent is unusual because:
- `delegate` makes the LLM decide which sub-agent handles the request
- `use` gives the agent tools to explicitly call other agents

These are typically separate concerns that belong on different agents.

**Solutions:**

1. Split into separate agents (recommended)
2. If intentional, you can ignore the warning

```streetrace
# Problem: Both delegate and use
agent mixed:
    instruction mixed_prompt
    delegate billing_agent
    use helper_agent

# Fix: Split responsibilities
agent coordinator:
    instruction coordinator_prompt
    delegate billing_agent, support_agent

agent support_agent:
    instruction support_prompt
    use helper_agent  # Support uses helper
```

## Common Parse Errors

### Missing Colon

**Problem:**

```streetrace
model main = anthropic/claude-sonnet
agent  # Missing colon
    tools github
```

**Fix:**

```streetrace
model main = anthropic/claude-sonnet
agent:  # Add colon
    tools github
```

### Missing `do`/`end` Keywords

**Problem:**

```streetrace
on input  # Missing 'do'
    mask pii
# Missing 'end'
```

**Fix:**

```streetrace
on input do
    mask pii
end
```

### Unclosed String

**Problem:**

```streetrace
prompt greeting:
    Hello, welcome to our service.
    Please let me know how I can help.  # Prompt body is fine

model main = anthropic/claude-sonnet"  # Extra quote
```

**Fix:** Remove the extra quote or ensure strings are properly closed.

### Wrong Indentation in Prompt Body

**Problem:**

```streetrace
prompt greeting:
You are a helpful assistant.  # Not indented
```

**Fix:**

```streetrace
prompt greeting:
    You are a helpful assistant.  # Indented
```

## Runtime Errors

### Model Not Configured

**Error:** `LLM provider error: API key not configured`

**Solution:** Set the appropriate environment variable:

```bash
export ANTHROPIC_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here
```

### Tool Connection Failed

**Error:** `MCP connection failed: Connection refused`

**Solution:**

1. Check the tool URL is correct
2. Verify the MCP server is running
3. Check authentication credentials

```streetrace
# Verify credentials
tool github = mcp "https://api.github.com/mcp/" with auth bearer ${env:GITHUB_PAT}
```

### Timeout Exceeded

**Error:** `Agent timeout: exceeded 2 minutes`

**Solution:**

1. Increase the timeout
2. Optimize the agent's task
3. Split into smaller sub-tasks

```streetrace
timeout long = 10 minutes

agent slow_task:
    timeout long
```

## Debugging Tips

### Use `dump-python` to Inspect Generated Code

```bash
streetrace dump-python my_agent.sr
```

This shows what Python code the compiler generates, helping identify issues.

### Validate Before Running

Always validate first:

```bash
streetrace check my_agent.sr && streetrace my_agent.sr
```

### Use Verbose Mode

```bash
streetrace check ./agents/ -v
```

Shows which files are being checked.

### Check JSON Output for Programmatic Processing

```bash
streetrace check my_agent.sr --format json | jq '.errors'
```

### Isolate the Problem

If a file has multiple errors, create a minimal test file with just the problematic
section:

```streetrace
# test.sr - minimal reproduction
model main = anthropic/claude-sonnet

# Just the failing part
agent:
    tools unknown_tool  # Test if this causes E0001
```

## Getting Help

If you encounter an error not covered here:

1. Check the error code category (E00xx = reference, E04xx = syntax, etc.)
2. Use `dump-python` to see the generated code
3. Create a minimal reproduction case
4. Check GitHub issues for similar problems

## See Also

- [Getting Started](getting-started.md) - Introduction to Streetrace DSL
- [Syntax Reference](syntax-reference.md) - Complete language reference
- [Multi-Agent Patterns](multi-agent-patterns.md) - Coordinator, hierarchical, and iterative patterns
- [CLI Reference](cli-reference.md) - Command-line tools
