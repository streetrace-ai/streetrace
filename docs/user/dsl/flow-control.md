# Flow Control

This guide covers flow control constructs in the Streetrace DSL, including sequential
execution, parallel blocks, conditionals, and loops.

## Overview

Flows define multi-step workflows that orchestrate agent calls and data transformations.
Flow control constructs determine the execution order and enable patterns like concurrent
processing and iterative refinement.

## Parallel Execution

The `parallel do` block executes multiple agent calls concurrently, collecting results
into separate variables.

### Basic Syntax

```streetrace
parallel do
    $result1 = run agent task1 $input
    $result2 = run agent task2 $input
end
# Both $result1 and $result2 available here
```

### Key Points

- Only `run agent` statements are allowed inside parallel blocks
- All agents start simultaneously and run concurrently
- Results are collected after all agents complete
- Variables are assigned in declaration order

### Example: Parallel Data Fetching

```streetrace
flow fetch_pr_data $pr_url:
    # Fetch PR metadata and diff concurrently
    parallel do
        $pr_info = run agent pr_fetcher $pr_url
        $diff = run agent diff_fetcher $pr_url
    end

    # Both results available for further processing
    return { pr: $pr_info, diff: $diff }
```

### Example: Parallel Review Specialists

```streetrace
flow review_code $context $chunk:
    parallel do
        $security = run agent security_reviewer $context $chunk
        $bugs = run agent bug_reviewer $context $chunk
        $style = run agent style_reviewer $context $chunk
    end

    # Combine results from all specialists
    $all_findings = $security.findings + $bugs.findings + $style.findings
    return $all_findings
```

### Restrictions

The following are **not allowed** in parallel blocks:

```streetrace
# ERROR: Assignments not allowed
parallel do
    $x = 42  # Not allowed
end

# ERROR: call llm not allowed (wrap in agent instead)
parallel do
    $result = call llm my_prompt $input  # Not allowed
end

# ERROR: Control flow not allowed
parallel do
    if $condition:  # Not allowed
        run agent handler
    end
end
```

To run `call llm` in parallel, create a simple agent wrapper:

```streetrace
agent security_reviewer:
    instruction security_prompt

# Now can use in parallel
parallel do
    $security = run agent security_reviewer $context
end
```

## Sequential Execution

By default, statements execute sequentially:

```streetrace
flow process_data $input:
    $step1 = run agent preprocessor $input
    $step2 = run agent analyzer $step1
    $step3 = run agent postprocessor $step2
    return $step3
```

Each step waits for the previous one to complete.

## For Loops

Iterate over lists with `for ... in ... do`:

```streetrace
flow process_items $items:
    $results = []

    for $item in $items do
        $result = run agent processor $item
        push $result to $results
    end

    return $results
```

### Loop with Parallel Inner Block

Combine loops with parallel blocks for efficient batch processing:

```streetrace
flow review_all_chunks $chunks $context:
    $all_findings = []

    for $chunk in $chunks do
        # Each chunk reviewed by all specialists in parallel
        parallel do
            $security = run agent security_reviewer $context $chunk
            $bugs = run agent bug_reviewer $context $chunk
        end

        $all_findings = $all_findings + $security.findings
        $all_findings = $all_findings + $bugs.findings
    end

    return $all_findings
```

## Conditionals

Use `if` for conditional execution:

```streetrace
flow process_with_validation $input:
    $result = run agent processor $input

    if $result.valid:
        return $result.output
    end

    return "Validation failed"
```

### Single-Line Conditionals

For simple conditions:

```streetrace
if $result.completed:
    return $result
```

## Loop Block (Iterative Refinement)

The `loop` block supports iterative refinement patterns:

```streetrace
# Bounded loop with maximum iterations
loop max 5 do
    $quality = call llm quality_check $current
    if $quality.passed:
        return $current
    end
    $current = call llm improve $current
end

# Unbounded loop (requires exit condition)
loop do
    $result = run agent process $data
    if $result.done:
        return $result
    end
end
```

## Match Block (Pattern Matching)

Route execution based on values:

```streetrace
flow route_request $request:
    match $request.category
        when "billing" -> run agent billing_handler $request
        when "technical" -> run agent tech_handler $request
        when "sales" -> run agent sales_handler $request
        else -> escalate to human "Unknown category"
    end
```

## Failure Handling

Handle errors in flows with `on failure`:

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

## Flow Parameters

Flows accept parameters prefixed with `$`:

```streetrace
flow analyze $document $options:
    # $document and $options available in the flow body
    if $options.detailed:
        return run agent detailed_analyzer $document
    end
    return run agent quick_analyzer $document
```

## Calling Flows

Call other flows with `run`:

```streetrace
flow main $input:
    # Call user-defined flow
    $preprocessed = run preprocess $input
    $result = run agent analyzer $preprocessed
    return $result

flow preprocess $data:
    # Preprocessing logic
    return run agent cleaner $data
```

## Best Practices

### Use Parallel Blocks for Independent Operations

When operations don't depend on each other, run them in parallel:

```streetrace
# Good: Independent fetches run concurrently
parallel do
    $metadata = run agent fetch_metadata $id
    $content = run agent fetch_content $id
end

# Avoid: Sequential when parallel is possible
$metadata = run agent fetch_metadata $id
$content = run agent fetch_content $id  # Waits unnecessarily
```

### Combine Results After Parallel Blocks

Process combined results outside the parallel block:

```streetrace
parallel do
    $a = run agent analyzer1 $input
    $b = run agent analyzer2 $input
end

# Combine after both complete
$combined = $a.findings + $b.findings
$deduplicated = run agent deduplicator $combined
```

### Use Bounded Loops

Prefer bounded loops to prevent infinite execution:

```streetrace
# Preferred: Bounded loop
loop max 5 do
    # ...
end

# Use with caution: Unbounded loop
loop do
    # Must have guaranteed exit condition
end
```

## See Also

- [Syntax Reference](syntax-reference.md) - Complete DSL syntax
- [Expressions](expressions.md) - Expression syntax including filter
- [Multi-Agent Patterns](multi-agent-patterns.md) - Agent composition patterns
- [Troubleshooting](troubleshooting.md) - Common errors and solutions
