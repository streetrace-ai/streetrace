# Escalation Feature - Test Scenarios

This document describes manual end-to-end test scenarios for the Escalation feature.

## Feature Scope

The Escalation feature covers:

1. **Normalized comparison operator (`~`)** - Case-insensitive, formatting-stripped comparison
2. **Prompt escalation conditions** - `escalate if` clause on prompts
3. **Run statement escalation handlers** - `on escalate` clause on run statements

## User Journeys

### Journey 1: Build Iterative Refinement Workflow

A user wants to build a workflow where two agents iteratively improve a prompt until one
detects that further changes would degrade quality.

**Steps**:
1. Define prompts with escalation conditions
2. Define agents using those prompts
3. Create flow with loop and escalation handlers
4. Run workflow with input prompt
5. Verify flow terminates when agent escalates

### Journey 2: Handle LLM Output Formatting

A user needs to compare LLM output to expected values, but LLM adds formatting like
bold markers, punctuation, or varying capitalization.

**Steps**:
1. Use `~` operator for comparison
2. Verify comparison succeeds despite formatting differences

### Journey 3: Batch Processing with Skip

A user processes a batch of items and wants to skip items that fail validation
without stopping the entire workflow.

**Steps**:
1. Define agent with escalation for failed items
2. Use `on escalate continue` in for loop
3. Verify failed items are skipped, successful items processed

---

## Scenario 1: Normalized Equals Operator

**Feature**: `~` operator normalizes text before comparison.

### Scenario 1.1: Case Insensitivity

**Input DSL** (`test_case.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

flow main:
    if $input_prompt ~ "YES":
        return "matched"
    end
    return "no match"
```

**Test Commands**:
```bash
# Test lowercase
poetry run streetrace run test_case.sr --input "yes"
# Expected: "matched"

# Test uppercase
poetry run streetrace run test_case.sr --input "YES"
# Expected: "matched"

# Test mixed case
poetry run streetrace run test_case.sr --input "Yes"
# Expected: "matched"
```

**Expected Output**:
All three variations return `"matched"`.

### Scenario 1.2: Whitespace Handling

**Input DSL** (`test_whitespace.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

flow main:
    if $input_prompt ~ "HELLO WORLD":
        return "matched"
    end
    return "no match"
```

**Test Commands**:
```bash
# Test extra spaces
poetry run streetrace run test_whitespace.sr --input "  hello   world  "
# Expected: "matched"

# Test newlines
poetry run streetrace run test_whitespace.sr --input "hello\nworld"
# Expected: "matched"
```

**Expected Output**:
Both variations return `"matched"`.

### Scenario 1.3: Punctuation and Markdown

**Input DSL** (`test_formatting.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

flow main:
    if $input_prompt ~ "DONE":
        return "matched"
    end
    return "no match"
```

**Test Commands**:
```bash
# Test with punctuation
poetry run streetrace run test_formatting.sr --input "Done."
# Expected: "matched"

# Test with markdown
poetry run streetrace run test_formatting.sr --input "**Done!**"
# Expected: "matched"

# Test with multiple formatting
poetry run streetrace run test_formatting.sr --input "  **DONE**!!\n"
# Expected: "matched"
```

**Expected Output**:
All variations return `"matched"`.

---

## Scenario 2: Prompt Escalation Conditions

**Feature**: Prompts can define `escalate if` conditions.

### Scenario 2.1: Normalized Escalation

**Input DSL** (`test_prompt_escalation.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt checker: """
    If the following text is offensive, respond with "BLOCKED".
    Otherwise, respond with "ALLOWED".

    Text: ${text}
    """
    escalate if ~ "BLOCKED"

agent checker:
    instruction checker

flow main:
    $text = $input_prompt
    $result = run agent checker $text, on escalate return "CONTENT_BLOCKED"
    return $result
```

**Test Commands**:
```bash
# Test with offensive content (mock - LLM should detect)
poetry run streetrace run test_prompt_escalation.sr --input "Some offensive text here"
# Expected: "CONTENT_BLOCKED" (if LLM responds "BLOCKED")

# Test with normal content
poetry run streetrace run test_prompt_escalation.sr --input "Hello world"
# Expected: LLM response (likely "ALLOWED")
```

**Verification**:
- Check generated code contains `EscalationSpec(op='~', value='BLOCKED')`
- When LLM outputs "BLOCKED" (any formatting), escalation triggers
- When LLM outputs "ALLOWED", no escalation

### Scenario 2.2: Exact Match Escalation

**Input DSL** (`test_exact_escalation.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt exact_checker: """
    Respond with exactly "ERROR" if invalid, or "OK" if valid.
    Input: ${input}
    """
    escalate if == "ERROR"

agent exact_checker:
    instruction exact_checker

flow main:
    $result = run agent exact_checker $input_prompt, on escalate return "EXACT_ERROR"
    return $result
```

**Verification**:
- Check generated code contains `EscalationSpec(op='==', value='ERROR')`
- Only exact "ERROR" triggers escalation
- "Error" or "ERROR." does NOT trigger (case/punctuation mismatch)

### Scenario 2.3: Contains Escalation

**Input DSL** (`test_contains_escalation.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt status_checker: """
    Describe the status of: ${item}
    Include "ERROR" in your response if there's a problem.
    """
    escalate if contains "ERROR"

agent status_checker:
    instruction status_checker

flow main:
    $result = run agent status_checker $input_prompt, on escalate return "HAS_ERROR"
    return $result
```

**Verification**:
- Check generated code contains `EscalationSpec(op='contains', value='ERROR')`
- "There was an ERROR processing" triggers escalation
- "Success" does NOT trigger

---

## Scenario 3: Escalation Handler Actions

**Feature**: Run statements can specify handler actions.

### Scenario 3.1: Return Action

**Input DSL** (`test_return_handler.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt improver: """
    Improve: ${current}
    If cannot improve, respond "DONE".
    """
    escalate if ~ "DONE"

agent improver:
    instruction improver

flow main:
    $current = $input_prompt
    $current = run agent improver $current, on escalate return $current
    return "Improved to: " + $current
```

**Test Commands**:
```bash
# Run with already optimal input
poetry run streetrace run test_return_handler.sr --input "This is already perfect"
# Expected: "This is already perfect" (returned unchanged if LLM says DONE)
```

**Generated Code Verification**:
```python
async for _event in ctx.run_agent_with_escalation('improver', ctx.vars['current']):
    yield _event
_result, _escalated = ctx.get_last_result_with_escalation()
ctx.vars['current'] = _result
if _escalated:
    ctx.vars['_return_value'] = ctx.vars['current']
    return
```

### Scenario 3.2: Continue Action

**Input DSL** (`test_continue_handler.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt processor: """
    Process: ${item}
    If cannot process, respond "SKIP".
    """
    escalate if ~ "SKIP"

agent processor:
    instruction processor

flow main:
    $items = ["valid1", "invalid", "valid2"]
    $results = []

    for $item in $items do
        $result = run agent processor $item, on escalate continue
        push $result to $results
    end

    return $results
```

**Generated Code Verification**:
```python
if _escalated:
    continue
```

**Expected Behavior**:
- "invalid" item causes escalation and is skipped
- "valid1" and "valid2" are processed and added to results

### Scenario 3.3: Abort Action

**Input DSL** (`test_abort_handler.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt validator: """
    Validate: ${input}
    If invalid, respond "INVALID".
    """
    escalate if ~ "INVALID"

agent validator:
    instruction validator

flow main:
    $result = run agent validator $input_prompt, on escalate abort
    return $result
```

**Generated Code Verification**:
```python
if _escalated:
    raise AbortError('Escalation triggered abort')
```

**Expected Behavior**:
- If validator returns "INVALID", `AbortError` is raised
- Workflow stops immediately

---

## Scenario 4: Integration with Loop

**Feature**: Escalation handlers work with loop blocks.

### Scenario 4.1: Resolver Pattern

**Input DSL** (`test_resolver_pattern.sr`):
```sr
streetrace v1

model main = anthropic/claude-sonnet

prompt peer1: """
    Enhance: ${current}
    If cannot improve, respond "DRIFTING".
    """
    escalate if ~ "DRIFTING"

prompt peer2: """
    Review: ${current}
    If degraded, respond "DRIFTING".
    """
    escalate if ~ "DRIFTING"

agent peer1:
    instruction peer1

agent peer2:
    instruction peer2

flow main:
    $current = $input_prompt

    loop max 5 do
        $current = run agent peer1 $current, on escalate return $current
        $current = run agent peer2 $current, on escalate return $current
    end

    return $current
```

**Expected Behavior**:
1. Loop runs up to 5 times
2. Each peer can trigger early exit via return
3. Final result is last stable value

**Test Commands**:
```bash
# Run with simple prompt
poetry run streetrace run test_resolver_pattern.sr --input "Write a haiku about coding"

# Check iteration count in debug output
STREETRACE_LOG_LEVEL=DEBUG poetry run streetrace run test_resolver_pattern.sr --input "Write a haiku"
```

---

## Scenario 5: Code Generation Verification

**Feature**: Generated Python correctly implements escalation.

### Scenario 5.1: Verify Imports

**Check generated code includes**:
```python
from streetrace.dsl.runtime.utils import normalized_equals
from streetrace.dsl.runtime.workflow import (
    DslAgentWorkflow,
    EscalationSpec,
    PromptSpec,
)
```

### Scenario 5.2: Verify PromptSpec with Escalation

**Input DSL**:
```sr
prompt test: """Body"""
    escalate if ~ "STOP"
```

**Expected Generated Code**:
```python
_prompts = {
    'test': PromptSpec(
        body=lambda ctx: f"""Body""",
        escalation=EscalationSpec(op='~', value='STOP'),
    ),
}
```

### Scenario 5.3: Verify normalized_equals Usage

**Input DSL**:
```sr
flow main:
    if $answer ~ "YES":
        return true
    end
```

**Expected Generated Code**:
```python
if normalized_equals(ctx.vars['answer'], "YES"):
```

---

## Troubleshooting

### Escalation Not Triggering

**Symptoms**: Agent outputs escalation word but handler doesn't execute.

**Debug Steps**:
1. Check LLM raw output:
   ```sr
   $result = run agent checker $input
   log "Raw: ${result}"
   ```
2. Verify prompt has `escalate if` clause
3. Check operator matches expectation (`~` vs `==`)

### Unexpected Escalation

**Symptoms**: Escalation triggers when it shouldn't.

**Debug Steps**:
1. Check for unintended matches with `contains`
2. Verify LLM isn't outputting escalation word unexpectedly
3. Check for case sensitivity issues (use `~` not `==`)

### Handler Not Running

**Symptoms**: Escalation detected but handler action doesn't execute.

**Debug Steps**:
1. Verify `on escalate` syntax is on same line as `run`
2. Check generated code has `if _escalated:` block
3. Verify handler action is valid (`return`, `continue`, `abort`)

## Reference Documents

- `docs/tasks/017-dsl/escalation-operator/tasks.md`: Design specification, 2026-01-27
- `docs/user/dsl/escalation.md`: User documentation, 2026-01-27
- `docs/dev/dsl/escalation.md`: Developer documentation, 2026-01-27
