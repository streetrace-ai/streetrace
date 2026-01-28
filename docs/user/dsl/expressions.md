# Expressions

This guide covers expressions in the Streetrace DSL, including variables, operators,
property access, filter expressions, and list operations.

## Overview

Expressions compute values that can be assigned to variables, passed to agents, or
used in conditions. The DSL provides a rich expression language optimized for working
with structured data from LLM outputs.

## Variables

Variables use the `$` prefix:

```streetrace
$name = "value"
$count = 42
$items = [1, 2, 3]
$config = { key: "value", count: 10 }
```

### Built-in Variables

| Variable | Description |
|----------|-------------|
| `$input_prompt` | Current user input |
| `$conversation` | Conversation history |
| `$current_agent` | Currently running agent |
| `$session_id` | Current session identifier |
| `$turn_count` | Number of conversation turns |

## Property Access

Access object properties with dot notation:

```streetrace
$result.status
$user.profile.name
$finding.category
```

### Nested Properties

Chain property access for deeply nested data:

```streetrace
$review.findings.first.severity
$context.pr.author.login
```

## Property Assignment

Assign values to object properties:

```streetrace
$review.findings = $filtered
$result.status = "completed"
$obj.nested.value = 42
```

This modifies the property in place rather than creating a new object.

### Example: Update After Filtering

```streetrace
# Get review result with findings
$review = call llm reviewer_instruction $context

# Filter to high-confidence findings
$filtered = filter $review.findings where .confidence >= 80

# Update the review object
$review.findings = $filtered

return $review
```

## Filter Expression

Filter lists based on conditions using the `filter ... where` syntax:

```streetrace
$filtered = filter $list where .property >= 80
```

### Implicit Property Access

The dot prefix (`.property`) accesses properties on each item being filtered:

```streetrace
# Filter findings by confidence
$high_confidence = filter $findings where .confidence >= 80

# Filter items that have a suggested fix
$fixable = filter $items where .suggested_fix != null

# Filter by nested property
$critical = filter $findings where .severity == "critical"
```

### Complex Conditions

Combine conditions with `and`, `or`, and comparison operators:

```streetrace
# Multiple conditions
$urgent = filter $findings where .severity == "critical" and .confidence >= 90

# Or conditions
$actionable = filter $findings where .severity == "critical" or .has_fix == true
```

### Comparison with Variables

Compare against variables in the outer scope:

```streetrace
$threshold = 80
$filtered = filter $findings where .confidence >= $threshold
```

## List Operations

### List Concatenation

Combine lists with the `+` operator:

```streetrace
$all = $list1 + $list2
$combined = $security_findings + $bug_findings + $style_findings
```

### Append Single Items

Wrap single items in a list literal for concatenation:

```streetrace
$items = $items + [$new_item]
$findings = $findings + [$validated_finding]
```

### Building Lists in Loops

```streetrace
$results = []
for $item in $input_items do
    $processed = run agent processor $item
    $results = $results + [$processed]
end
```

### Push Statement

An alternative to concatenation for appending:

```streetrace
$results = []
for $item in $items do
    $result = run agent handler $item
    push $result to $results
end
```

## Literals

### String Literals

```streetrace
$message = "Hello, world"
$path = "/path/to/file"
```

### Numeric Literals

```streetrace
$count = 42
$ratio = 3.14
$threshold = 80
```

### Boolean Literals

```streetrace
$active = true
$disabled = false
```

### Null Literal

```streetrace
$optional = null
```

### List Literals

```streetrace
$empty = []
$numbers = [1, 2, 3]
$mixed = [$item, "literal", 42]
```

### Object Literals

```streetrace
$config = { key: "value", count: 10 }
$context = {
    pr: $pr_info,
    repo: $repo_context,
    history: $chunk_history
}
```

## Operators

### Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Exact equality | `$a == $b` |
| `!=` | Not equal | `$a != $b` |
| `>` | Greater than | `$score > 80` |
| `<` | Less than | `$count < 10` |
| `>=` | Greater or equal | `$confidence >= 80` |
| `<=` | Less or equal | `$errors <= 5` |
| `~` | Normalized equality | `$response ~ "YES"` |
| `contains` | Contains substring | `$text contains "error"` |

### Normalized Equality (`~`)

Compares values after normalization (case-insensitive, ignoring formatting):

```streetrace
if $response ~ "YES":
    log "User confirmed"
```

Normalization removes:
- Markdown formatting (`**`, `*`, `_`, `` ` ``, `#`)
- Punctuation (`.`, `!`, `?`, `,`, `;`, `:`)
- Converts to lowercase
- Collapses whitespace

### Logical Operators

```streetrace
$a and $b
$a or $b
not $a
```

### Arithmetic Operators

```streetrace
$total = $a + $b
$difference = $a - $b
$product = $a * $b
$quotient = $a / $b
```

### String Concatenation

```streetrace
$message = "Status: " + $result.status
$full_path = $directory + "/" + $filename
```

## Function Calls

### Built-in Functions

```streetrace
process($value)              # Process a value
initial_user_prompt()        # Get the initial user prompt
```

### Library Functions

Call functions from imported libraries:

```streetrace
$converted = lib.convert($item)
$formatted = utils.format($data)
```

## Common Patterns

### Filter and Assign

```streetrace
$high_priority = filter $all_findings where .severity == "critical"
$review.findings = $high_priority
```

### Conditional List Building

```streetrace
$validated = []
for $finding in $findings do
    $result = run agent validator $finding
    if $result.valid:
        $validated = $validated + [$finding]
    end
end
```

### Combining Multiple Sources

```streetrace
parallel do
    $security = run agent security_reviewer $context
    $bugs = run agent bug_reviewer $context
end

$all = $security.findings + $bugs.findings
$filtered = filter $all where .confidence >= 80
```

### Object Construction

```streetrace
$full_context = {
    pr: $pr_info,
    repo: $repo_context,
    chunk_history: $history
}
$result = run agent reviewer $full_context
```

## Type Coercion

The DSL performs minimal type coercion:

- String concatenation with `+` converts operands to strings
- Comparison operators require compatible types
- Boolean contexts accept truthy/falsy values

## Error Handling

### Missing Properties

Accessing a missing property raises an error:

```streetrace
$x = $result.missing_property  # Error if property doesn't exist
```

Use schema definitions to ensure expected properties exist.

### Null Comparisons

Compare against `null` to check for optional values:

```streetrace
$has_fix = filter $findings where .suggested_fix != null
```

## See Also

- [Flow Control](flow-control.md) - Control flow constructs
- [Syntax Reference](syntax-reference.md) - Complete DSL syntax
- [Schema Support](schema-support.md) - Structured outputs with validation
- [Troubleshooting](troubleshooting.md) - Common errors and solutions
