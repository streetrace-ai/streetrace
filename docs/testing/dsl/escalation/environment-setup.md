# Escalation Feature - Environment Setup

This document describes how to set up the environment for manual testing of the Escalation feature.

## Prerequisites

1. StreetRace installed and configured
2. Access to an LLM provider (Anthropic, OpenAI, etc.)
3. Valid API credentials configured

## Environment Variables

Set the following environment variables for testing:

```bash
# Required: LLM provider API key
export ANTHROPIC_API_KEY="your-api-key"
# or
export OPENAI_API_KEY="your-api-key"

# Optional: Enable debug logging
export STREETRACE_LOG_LEVEL="DEBUG"
```

## Test Artifacts

### Basic Escalation Test File

Create `test_escalation.sr`:

```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt checker: """
    Analyze this text: ${input}

    If it contains the word "stop", respond with just "ESCALATE".
    Otherwise, respond with "CONTINUE".
    """
    escalate if ~ "ESCALATE"

agent checker:
    instruction checker

flow main:
    $result = run agent checker $input_prompt, on escalate return "STOPPED"
    return $result
```

### Iterative Refinement Test File

Create `test_resolver.sr`:

```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt enhancer: """
    Improve this prompt: ${current}

    If you cannot improve it further, respond with just "DONE".
    Otherwise, provide your improved version.
    """
    escalate if ~ "DONE"

agent enhancer:
    instruction enhancer

flow main:
    $current = $input_prompt

    loop max 3 do
        $current = run agent enhancer $current, on escalate return $current
    end

    return $current
```

### Normalized Comparison Test File

Create `test_normalized.sr`:

```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt yesno: """
    Answer yes or no: ${question}
    """

agent yesno:
    instruction yesno

flow main:
    $answer = run agent yesno $input_prompt

    if $answer ~ "YES":
        return "Confirmed"
    end

    if $answer ~ "NO":
        return "Denied"
    end

    return "Unknown"
```

### Escalation Handler Actions Test File

Create `test_handlers.sr`:

```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt critical: """
    Validate: ${input}

    If validation fails, respond with "INVALID".
    Otherwise, respond with "VALID".
    """
    escalate if ~ "INVALID"

prompt optional: """
    Enhance: ${input}

    If no enhancement needed, respond with "SKIP".
    Otherwise, provide enhanced version.
    """
    escalate if ~ "SKIP"

agent validator:
    instruction critical

agent enhancer:
    instruction optional

flow test_abort:
    $result = run agent validator $input_prompt, on escalate abort
    return $result

flow test_continue:
    $results = []

    for $item in $items do
        $result = run agent enhancer $item, on escalate continue
        push $result to $results
    end

    return $results

flow test_return:
    $original = $input_prompt
    $result = run agent validator $original, on escalate return $original
    return $result
```

## Running Tests

### Compile and Run

```bash
# Compile DSL to Python
poetry run streetrace compile test_escalation.sr -o test_escalation_workflow.py

# Run with streetrace
poetry run streetrace run test_escalation.sr --input "Please stop processing"
poetry run streetrace run test_escalation.sr --input "Continue with the task"
```

### Check Generated Code

Inspect the generated Python to verify correct code generation:

```bash
# View generated code
cat test_escalation_workflow.py

# Look for escalation-related code
grep -n "escalat" test_escalation_workflow.py
grep -n "normalized_equals" test_escalation_workflow.py
```

### Debug Mode

Enable verbose output for debugging:

```bash
STREETRACE_LOG_LEVEL=DEBUG poetry run streetrace run test_escalation.sr --input "test"
```

## Verification Checklist

Before running scenarios, verify:

- [ ] DSL file compiles without errors
- [ ] Generated Python imports `normalized_equals`
- [ ] Generated Python imports `EscalationSpec` and `PromptSpec`
- [ ] Prompts with escalation generate `PromptSpec(escalation=...)`
- [ ] Run statements with handlers generate `run_agent_with_escalation()`
- [ ] LLM provider is accessible and responding

## Reference Documents

- `docs/tasks/017-dsl/escalation-operator/tasks.md`: Design specification, 2026-01-27
- `docs/user/dsl/escalation.md`: User documentation, 2026-01-27
- `docs/dev/dsl/escalation.md`: Developer documentation, 2026-01-27
