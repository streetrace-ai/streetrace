# Prompt Escalation

The Escalation feature enables cleaner agent communication patterns by allowing prompts to define
when their output should trigger special handling. This is particularly useful for iterative
refinement loops and agent coordination.

## The Problem

When agents communicate, LLM outputs often include formatting noise like markdown, punctuation,
and varying capitalization. This makes comparing outputs difficult:

```sr
# This comparison fails because LLM might output "**Drifting.**\n" instead of "DRIFTING"
$new = run agent peer1 $current
if $new == "DRIFTING":
    return $current
```

Additionally, the logic for "when to stop" is mixed with "what to do when stopped":

```sr
# Verbose pattern - checking and handling mixed together
$new = run agent peer1 $current
if $new == "DRIFTING":
    return $current
$current = $new

$new = run agent peer2 $current
if $new == "DRIFTING":
    return $current
$current = $new
```

## The Solution

The Escalation feature separates these concerns:

1. **The `~` operator** handles LLM output formatting noise
2. **Prompt escalation conditions** define when output signals "stop"
3. **Run escalation handlers** define what to do when stopped

```sr
# Clean pattern with escalation
prompt pi_enhancer: """..."""
    escalate if ~ "DRIFTING"

agent peer1:
    instruction pi_enhancer

flow main:
    $current = $input_prompt
    loop max 3 do
        $current = run agent peer1 $current, on escalate return $current
        $current = run agent peer2 $current, on escalate return $current
    end
    return $current
```

## The `~` Operator (Normalized Equals)

The `~` operator performs "normalized equality" - comparing values after removing formatting noise.

### Normalization Rules

The operator applies these transformations before comparing:

1. Remove markdown modifiers (`**`, `*`, `_`, `` ` ``, `#`)
2. Remove punctuation (`.`, `!`, `?`, `,`, `;`, `:`)
3. Convert to lowercase
4. Collapse multiple whitespace to single space
5. Strip leading/trailing whitespace

### Examples

| Left Value | Right Value | `~` Result | `==` Result |
|------------|-------------|------------|-------------|
| `"DRIFTING"` | `"DRIFTING"` | `true` | `true` |
| `"drifting"` | `"DRIFTING"` | `true` | `false` |
| `"**Drifting.**\n"` | `"DRIFTING"` | `true` | `false` |
| `"  Drifting!  "` | `"DRIFTING"` | `true` | `false` |
| `"I am drifting"` | `"DRIFTING"` | `false` | `false` |
| `"Yes"` | `"YES"` | `true` | `false` |
| `"  yes.  "` | `"YES"` | `true` | `false` |

### Usage in Expressions

The `~` operator can be used anywhere expressions are valid:

```sr
# In if statements
if $response ~ "YES":
    log "User confirmed"

# In assignments
$is_approved = $answer ~ "APPROVED"

# In match blocks
match $status
    when ~ "SUCCESS" -> return { success: true }
    when ~ "FAILED" -> return { success: false }
end
```

### When to Use `~` vs `==`

| Scenario | Use |
|----------|-----|
| Comparing LLM outputs | `~` |
| Comparing structured data | `==` |
| Case-sensitive matching | `==` |
| Signal words from agents | `~` |
| Exact string validation | `==` |

## Prompt Escalation Conditions

Prompts can define conditions that trigger escalation when their output matches.

### Syntax

```sr
prompt <name> [modifiers]:
    """<prompt body>"""
    escalate if <condition>
```

### Available Conditions

| Condition | Description | Example |
|-----------|-------------|---------|
| `~ STRING` | Normalized equality | `escalate if ~ "DRIFTING"` |
| `== STRING` | Exact match | `escalate if == "ERROR"` |
| `!= STRING` | Not equal | `escalate if != "OK"` |
| `contains STRING` | Contains substring | `escalate if contains "ERROR"` |

### Examples

```sr
# Escalate on normalized match (recommended for LLM outputs)
prompt analyzer: """
    Analyze the input. If it's diverging from the goal, respond with just "DRIFTING".
    Otherwise, provide your analysis.
    """
    escalate if ~ "DRIFTING"

# Escalate on exact match
prompt classifier: """
    Classify the input. If human review is needed, respond with exactly "NEEDS_HUMAN".
    """
    escalate if == "NEEDS_HUMAN"

# Escalate if output contains error indicator
prompt detector: """
    Process the data. Include "ERROR" in your response if something is wrong.
    """
    escalate if contains "ERROR"
```

## Run Statement Escalation Handlers

Run statements can include handlers that execute when the called agent escalates.

### Syntax

```sr
$result = run agent <name> <args>, on escalate <action>
```

Or without assignment:

```sr
run agent <name> <args>, on escalate <action>
```

### Available Actions

| Action | Effect | Use Case |
|--------|--------|----------|
| `return <expr>` | Return from flow with value | Return previous state |
| `continue` | Skip to next loop iteration | Skip failed items |
| `abort` | Stop execution with error | Critical failure |

### Examples

```sr
# Return previous value on escalation
$current = run agent peer1 $current, on escalate return $current

# Continue loop on escalation
for $item in $items do
    run agent processor $item, on escalate continue
end

# Abort on escalation
$result = run agent critical_task $input, on escalate abort
```

## Complete Example: The Resolver Pattern

This example implements an iterative refinement loop where two peer agents enhance each other's
output until one detects drift.

```sr
streetrace v1

model main = anthropic/claude-sonnet

# Peer 1's prompt with escalation condition
prompt pi_enhancer: """
    You are a prompt engineering expert. Review and enhance this prompt:

    ${current}

    If the prompt has diverged from its original intent or become worse,
    respond with just "DRIFTING".

    Otherwise, provide an improved version.
    """
    escalate if ~ "DRIFTING"

# Peer 2's prompt with escalation condition
prompt pi_reviewer: """
    Review this prompt for clarity and effectiveness:

    ${current}

    If further changes would degrade quality, respond with just "DRIFTING".

    Otherwise, suggest improvements.
    """
    escalate if ~ "DRIFTING"

agent peer1:
    instruction pi_enhancer

agent peer2:
    instruction pi_reviewer

flow main:
    $current = $input_prompt

    loop max 5 do
        # Run peer1, return current value if it escalates
        $current = run agent peer1 $current, on escalate return $current

        # Run peer2, return current value if it escalates
        $current = run agent peer2 $current, on escalate return $current
    end

    # Return final result after max iterations
    return $current
```

### How It Works

1. User provides initial prompt
2. Peer1 enhances it or says "DRIFTING" if it detects drift
3. If peer1 escalates, flow returns the current (un-degraded) value
4. Otherwise, peer2 reviews peer1's output
5. If peer2 escalates, flow returns the current value
6. Loop continues until escalation or max iterations reached

## Best Practices

### Use Normalized Comparison for LLM Outputs

Always use `~` when comparing LLM outputs to expected strings:

```sr
# Good - handles formatting variations
escalate if ~ "DRIFTING"

# Fragile - exact match fails on "Drifting." or "**DRIFTING**"
escalate if == "DRIFTING"
```

### Keep Escalation Words Simple

Use short, distinctive words that LLMs can reliably output:

```sr
# Good - simple, distinctive
escalate if ~ "STOP"
escalate if ~ "DONE"
escalate if ~ "ERROR"

# Avoid - too similar to natural language
escalate if ~ "I think we should stop now"
```

### Match Handler Action to Context

| Context | Recommended Action |
|---------|-------------------|
| Iterative refinement loop | `return $previous_value` |
| Processing items in batch | `continue` |
| Critical validation | `abort` |
| Optional enhancement | `continue` |

### Document Escalation Signals in Prompts

Make the escalation signal clear in the prompt text:

```sr
prompt reviewer: """
    Review this document. If it meets all criteria, respond with just "APPROVED".
    Otherwise, list the issues.

    Note: Respond with exactly "APPROVED" (case-insensitive) to signal completion.
    """
    escalate if ~ "APPROVED"
```

## Common Patterns

### Guard Pattern

Run a check agent before the main task:

```sr
flow guarded_task $input:
    # Check if input is valid
    $check = run agent validator $input, on escalate abort

    # Only runs if validator didn't escalate
    $result = run agent processor $input
    return $result
```

### Refinement Loop

Iteratively improve until stable:

```sr
flow refine $initial:
    $current = $initial

    loop max 10 do
        $current = run agent improver $current, on escalate return $current
    end

    return $current
```

### Batch Processing with Skip

Process items, skipping failures:

```sr
flow process_batch $items:
    $results = []

    for $item in $items do
        $result = run agent processor $item, on escalate continue
        push $result to $results
    end

    return $results
```

## Troubleshooting

### Escalation Not Triggering

1. **Check prompt instruction** - Ensure the LLM knows to output the escalation word
2. **Use `~` operator** - LLM might include formatting like `**DRIFTING**`
3. **Check for extra text** - LLM might say "DRIFTING - because..."

Debug by logging the raw output:

```sr
$result = run agent checker $input
log "Raw result: ${result}"
if $result ~ "DRIFTING":
    log "Would escalate"
```

### Unexpected Escalation

1. **Check for partial matches** - `contains` matches substrings
2. **Verify the escalation word** - Is it too common in normal output?

### Handler Not Executing

1. **Verify syntax** - Handler must be on same line: `run agent ..., on escalate return $x`
2. **Check prompt has escalation** - The agent's prompt must define `escalate if`

## See Also

- [Getting Started](getting-started.md) - DSL basics
- [Syntax Reference](syntax-reference.md) - Complete syntax guide
- [Multi-Agent Patterns](multi-agent-patterns.md) - Agent coordination
- [Troubleshooting](troubleshooting.md) - Common issues
