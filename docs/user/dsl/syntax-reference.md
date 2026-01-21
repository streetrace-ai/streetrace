# Streetrace DSL Syntax Reference

This document provides a complete reference for the Streetrace DSL syntax. Use this as a
lookup guide when writing `.sr` files.

## File Structure

A `.sr` file contains top-level declarations in any order:

```streetrace
import base from streetrace

model main = anthropic/claude-sonnet

schema MyOutput:
    field1: string

tool my_tool = mcp "https://example.com/mcp/"

retry default = 3 times, exponential backoff
timeout default = 2 minutes

policy compaction:
    trigger: token_usage > 0.8

on start do
    $goal = run get_agent_goal  # Call user-defined flow
end

flow my_workflow:
    $result = run agent my_agent
    return $result

agent my_agent:
    tools my_tool
    instruction my_prompt

prompt my_prompt:
    You are a helpful assistant.
```

## Models

Models define LLM configurations.

### Short Form

```streetrace
model main = anthropic/claude-sonnet
model fast = anthropic/haiku
model reasoning = openai/gpt-4
```

The `main` model is the default for prompts that don't specify a model.

### Long Form

```streetrace
model main:
    provider: anthropic
    name: claude-sonnet
    temperature: 0.7
    max_tokens: 4096
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `provider` | string | LLM provider (anthropic, openai, etc.) |
| `name` | string | Model name at the provider |
| `temperature` | float | Sampling temperature (0.0-2.0) |
| `max_tokens` | int | Maximum response tokens |

## Schemas

Schemas define structured output types for prompts.

```streetrace
schema TaskResult:
    success: bool
    message: string
    items: list[string]
    metadata: object
    count: int?
```

### Field Types

| Type | Description | Example |
|------|-------------|---------|
| `bool` | Boolean value | `true`, `false` |
| `string` | Text string | `"hello"` |
| `int` | Integer number | `42` |
| `float` | Decimal number | `3.14` |
| `list[T]` | List of type T | `list[string]` |
| `object` | Generic object | `{}` |
| `T?` | Optional type T | `int?` |

## Tools

Tools provide capabilities to agents.

### MCP Tools

```streetrace
# Basic MCP tool
tool github = mcp "https://api.github.com/mcp/"

# With bearer auth
tool github = mcp "https://api.github.com/mcp/" with auth bearer ${env:GITHUB_PAT}

# With basic auth
tool api = mcp "https://api.example.com/mcp/" with auth basic ${env:API_CREDENTIALS}
```

### Built-in Tools

```streetrace
tool fs = builtin streetrace.fs
tool docs = builtin streetrace.docs
```

### Long Form

```streetrace
tool github:
    type: mcp
    url: https://api.github.com/mcp/
    headers:
        Authorization: "Bearer ${env:GITHUB_PAT}"
        X-Custom-Header: "value"
```

## Imports

Import definitions from other sources.

```streetrace
# Base Streetrace definitions (implicit for most files)
import base from streetrace

# Local .sr file
import ./custom_agent.sr

# Named import from local file
import custom from ./custom_agent.sr

# Python package
import lib from pip://third_party_library

# MCP server
import server from mcp://server_name
```

## Policies

### Retry Policy

```streetrace
retry default = 3 times, exponential backoff
retry aggressive = 5 times, linear backoff
retry simple = 2 times, fixed backoff
```

Backoff strategies:
- `exponential` - Doubles delay between retries
- `linear` - Constant delay increase between retries
- `fixed` - Same delay between all retries

### Timeout Policy

```streetrace
timeout default = 2 minutes
timeout long = 10 minutes
timeout short = 30 seconds
```

Units: `seconds`, `minutes`, `hours`

### Compaction Policy

```streetrace
policy compaction:
    trigger: token_usage > 0.8
    strategy: summarize_with_goal
    preserve: [$goal, last 3 messages, tool results]
    use model: "compact"
```

## Event Handlers

Handlers intercept events in the agent lifecycle.

### Event Types

| Handler | When it triggers |
|---------|------------------|
| `on start` | Agent initialization |
| `on input` | Before processing user input |
| `on output` | Before returning agent output |
| `on tool-call` | Before tool execution |
| `on tool-result` | After tool returns |
| `after start` | After start handlers complete |
| `after input` | After input handlers complete |
| `after output` | After output handlers complete |
| `after tool-call` | After tool-call handlers complete |
| `after tool-result` | After tool-result handlers complete |

### Handler Syntax

```streetrace
on input do
    mask pii
    block if jailbreak
    $custom_var = process($input)
end

after output do
    push $message to $history
end
```

### Guardrail Actions

| Action | Description |
|--------|-------------|
| `mask pii` | Replace sensitive data with placeholders |
| `mask <type>` | Replace specific content type |
| `block if <condition>` | Block processing if condition is true |
| `warn if <condition>` | Log warning, continue processing |
| `warn "<message>"` | Log specific warning message |
| `retry with <message>` | Re-prompt with correction message |
| `retry with <message> if <condition>` | Conditional retry |

### Block Behavior by Context

| Context | `block` Behavior |
|---------|------------------|
| `on input` | Return rejection message, abort workflow |
| `on tool-call` | Return error to model, model continues |
| `on tool-result` | Show blocked content to model, continues |
| `on output` | Replace output with redaction message |

## Flows

Flows define multi-step workflows.

```streetrace
flow process_documents $documents:
    $results = []

    for $doc in $documents do
        $result = run agent processor $doc
        push $result to $results
    end

    return $results
```

### Flow Parameters

```streetrace
flow my_flow $param1 $param2:
    # $param1 and $param2 are available here
    return $param1
```

### Control Flow

**Conditionals**:

```streetrace
if $score > 0.8:
    return "high"

if $value > threshold:
    $result = process($value)
    log "Processed"
```

**Iteration**:

```streetrace
for $item in $items do
    $processed = run agent handler $item
    push $processed to $results
end
```

**Parallel Execution**:

```streetrace
parallel do
    $result1 = run agent task1
    $result2 = run agent task2
end
# Both $result1 and $result2 available here
```

**Iterative Loop**:

```streetrace
# Bounded loop (recommended)
loop max 5 do
    $quality = call llm quality_check $current
    if $quality.passed:
        return $current
    $current = call llm improve $current
end

# Unbounded loop (requires exit condition)
loop do
    $result = run agent process $data
    if $result.done:
        return $result
end
```

**Pattern Matching**:

```streetrace
match $category
    when "billing" -> run agent billing_handler $request
    when "technical" -> run agent tech_handler $request
    when "sales" -> run agent sales_handler $request
    else -> escalate to human "Unknown category"
end
```

### Flow Statements

| Statement | Description |
|-----------|-------------|
| `$var = <expr>` | Variable assignment |
| `run agent <name> <args>` | Run named agent |
| `$var = run agent <name>` | Run agent, capture result |
| `call llm <prompt> <args>` | Call LLM with prompt |
| `$var = call llm <prompt>` | Call LLM, capture result |
| `return <value>` | Return from flow |
| `push <value> to $list` | Append to list |
| `log <message>` | Log message |
| `notify <message>` | Send notification |
| `escalate to human <message>` | Escalate to human |

### Failure Handling

```streetrace
flow transfer_money $from $to $amount:
    $debit = run agent debit_account $from $amount

    $credit = run agent credit_account $to $amount
    on failure:
        run agent refund_account $from $amount
        notify "Transfer failed, refund issued"
        return { success: false }

    return { success: true }
```

## Agents

Agents define AI assistants with tools and instructions.

### Unnamed Agent (Default)

```streetrace
agent:
    tools github, streetrace.fs
    instruction my_prompt
```

### Named Agents

```streetrace
agent code_reviewer:
    tools github
    instruction review_prompt
    description: "Reviews code changes"
    retry default
    timeout 2 minutes
```

### Agent Properties

| Property | Description |
|----------|-------------|
| `tools` | Comma-separated tool names |
| `instruction` | Prompt name for system instruction |
| `description` | Human-readable description |
| `retry` | Retry policy name |
| `timeout` | Timeout policy name or literal |
| `delegate` | Comma-separated agent names for coordinator pattern |
| `use` | Comma-separated agent names for hierarchical pattern |

### Multi-Agent Patterns

**Coordinator Pattern (delegate)**:

```streetrace
agent coordinator:
    instruction coordinator_prompt
    delegate billing_agent, support_agent, sales_agent
```

The coordinator's LLM decides which sub-agent handles each request.

**Hierarchical Pattern (use)**:

```streetrace
agent researcher:
    instruction researcher_prompt
    use searcher, summarizer
```

The parent agent calls referenced agents as tools.

See [Multi-Agent Patterns](multi-agent-patterns.md) for detailed usage.

## Prompts

Prompts define reusable LLM instructions.

### Basic Prompt

```streetrace
prompt greeting:
    You are a helpful assistant. Greet the user warmly
    and offer to help with their questions.
```

### Prompt Modifiers

```streetrace
prompt analyze_task using model "fast" expecting TaskResult:
    Analyze the given task and provide structured output.

    Task: ${task_description}
```

| Modifier | Description |
|----------|-------------|
| `using model "<name>"` | Use specific model |
| `expecting <Schema>` | Validate response against schema |
| `inherit $history` | Include conversation history |

### Variable Interpolation

```streetrace
prompt review_code:
    Review this code for issues:

    File: ${filename}
    Content:
    ${code_content}

    Focus on security and performance.
```

Variables use `${name}` syntax within prompt bodies.

## Variables

Variables use the `$` prefix.

### Variable Assignment

```streetrace
$name = "value"
$count = 42
$items = [1, 2, 3]
$config = { key: "value", count: 10 }
```

### Property Access

```streetrace
$result.status
$user.profile.name
$items[0]
```

### Built-in Variables

| Variable | Description |
|----------|-------------|
| `$input_prompt` | Current user input |
| `$conversation` | Conversation history |
| `$current_agent` | Currently running agent |
| `$session_id` | Current session identifier |
| `$turn_count` | Number of conversation turns |

### Scoping Rules

1. Variables in `on start do` are **global**
2. Variables in flows are **local** to that flow
3. Variables in handlers (except `on start`) are **local**

## Expressions

### Literals

```streetrace
"string value"
42
3.14
true
false
null
[1, 2, 3]
{ key: "value" }
```

### Operators

**Comparison**:

```streetrace
$a == $b
$a != $b
$a > $b
$a < $b
$a >= $b
$a <= $b
```

**Logical**:

```streetrace
$a and $b
$a or $b
not $a
```

**Arithmetic**:

```streetrace
$a + $b
$a - $b
$a * $b
$a / $b
```

**String**:

```streetrace
$text contains "pattern"
```

### Built-in Function Calls

```streetrace
process($value)              # Process a value
initial_user_prompt()        # Get the initial user prompt
```

User-defined flows are called using the `run` statement (see Flows section).

## Comments

```streetrace
# This is a comment

model main = anthropic/claude-sonnet  # Inline comment
```

## Environment Variables

Reference environment variables with `${env:NAME}`:

```streetrace
tool github = mcp "https://api.github.com/mcp/" with auth bearer ${env:GITHUB_PAT}
```

## Complete Example

```streetrace
import base from streetrace

# Models
model main = anthropic/claude-sonnet
model fast = anthropic/haiku

# Schemas
schema AnalysisResult:
    summary: string
    score: float
    issues: list[string]

# Tools
tool github = mcp "https://api.github.com/mcp/" with auth bearer ${env:GITHUB_PAT}

# Policies
retry default = 3 times, exponential backoff
timeout default = 2 minutes

# Initialization
on start do
    $goal = run get_agent_goal  # User-defined flow
    $history = []
end

# Guardrails
on input do
    mask pii
    block if jailbreak
end

on output do
    $drift = run detect_trajectory_drift $goal  # User-defined flow
    retry with $drift.message if $drift.score > 0.3
end

# History management
after output do
    push $message to $history
end

# Workflow
flow analyze_repository $repo_url:
    $files = run agent file_fetcher $repo_url
    $results = []

    for $file in $files do
        $analysis = run agent code_analyzer $file
        push $analysis to $results
    end

    $summary = run agent summarizer $results
    return $summary

# Agents
agent file_fetcher:
    tools github
    instruction fetch_prompt
    retry default
    timeout default

agent code_analyzer:
    tools streetrace.fs
    instruction analyze_prompt

agent summarizer:
    instruction summarize_prompt

# Prompts
prompt fetch_prompt:
    Fetch source files from the repository.
    Focus on code files, ignore build artifacts.

prompt analyze_prompt using model "fast" expecting AnalysisResult:
    Analyze the code file for quality issues.

    File: ${filename}
    Content: ${content}

prompt summarize_prompt:
    Summarize the analysis results into a final report.
    Highlight critical issues and provide recommendations.
```

## See Also

- [Getting Started](getting-started.md) - Introduction to Streetrace DSL
- [Multi-Agent Patterns](multi-agent-patterns.md) - Coordinator, hierarchical, and iterative patterns
- [CLI Reference](cli-reference.md) - Command-line tools
- [Troubleshooting](troubleshooting.md) - Error resolution
