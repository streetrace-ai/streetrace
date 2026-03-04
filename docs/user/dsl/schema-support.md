# Schema Support for Structured Outputs

Schema Support enables your prompts to receive structured, validated responses from LLMs.
Instead of parsing free-form text, define a schema and let StreetRace ensure responses
match your expected structure.

## Why Use Schemas?

Without schemas, LLM responses are unpredictable:
- May include explanatory text around JSON
- Field names might vary
- Types can be inconsistent
- Parsing errors cause runtime failures

With schemas:
- Responses are guaranteed to match your structure
- Type validation happens automatically
- Failed responses trigger automatic retry with feedback
- Results are ready to use as structured data

## Quick Start

### 1. Define a Schema

```streetrace
schema CodeReviewResult:
    approved: bool
    severity: string
    issues: list[string]
    suggestions: list[string]
    confidence: float
```

### 2. Create a Prompt with `expecting`

```streetrace
prompt review_code expecting CodeReviewResult: """
You are an expert code reviewer. Analyze the provided code for:
- Logic errors
- Security vulnerabilities
- Performance issues
- Code style

Provide your assessment in the structured format.
"""
```

### 3. Use with an Agent

```streetrace
agent code_reviewer:
    instruction review_code
    description "Reviews code and provides structured feedback"
```

### Complete Example

```streetrace
model main = anthropic/claude-sonnet

schema CodeReviewResult:
    approved: bool
    severity: string
    issues: list[string]
    suggestions: list[string]
    confidence: float

prompt review_code expecting CodeReviewResult: """
You are an expert code reviewer. Analyze the provided code for bugs,
security issues, and code quality. Provide your assessment.
"""

agent code_reviewer:
    instruction review_code
    description "Reviews code and provides structured feedback"
```

**Run**:
```bash
poetry run streetrace run code_review.sr --input "Review this: def add(a, b): return a + b"
```

**Output** (validated JSON):
```json
{
  "approved": true,
  "severity": "low",
  "issues": [],
  "suggestions": ["Add type hints for parameters"],
  "confidence": 0.95
}
```

## Schema Syntax

### Defining Schemas

Schemas are defined at the top level of your `.sr` file:

```streetrace
schema MySchema:
    field_name: type
    another_field: type
```

Field names must:
- Start with a letter or underscore
- Contain only letters, numbers, and underscores

### Supported Types

| Type | Description | Example Values |
|------|-------------|----------------|
| `bool` | Boolean | `true`, `false` |
| `string` | Text string | `"hello"`, `"world"` |
| `int` | Integer number | `42`, `-10`, `0` |
| `float` | Decimal number | `3.14`, `-0.5`, `1.0` |
| `list[T]` | List of type T | `["a", "b"]`, `[1, 2, 3]` |
| `T?` | Optional (nullable) | `"value"` or `null` |

### Type Examples

```streetrace
schema CompleteExample:
    # Required fields (must be present)
    name: string
    count: int
    score: float
    active: bool
    tags: list[string]
    scores: list[float]

    # Optional fields (can be null or missing)
    description: string?
    parent_id: int?
    metadata: list[string]?
```

## Using `expecting` with Prompts

The `expecting` modifier links a prompt to a schema:

```streetrace
prompt my_prompt expecting MySchema: """
Your prompt text here...
"""
```

When the prompt is used:
1. StreetRace adds JSON format instructions automatically
2. The LLM response is parsed as JSON
3. Pydantic validates the response against your schema
4. If validation fails, retry with error feedback (up to 3 times)

### With Model Selection

Combine `expecting` with `using model`:

```streetrace
prompt fast_analysis using model "fast" expecting QuickResult: """
Quickly analyze and categorize this input.
"""
```

## Schema Validation Behavior

### Automatic Retry

When the LLM returns invalid JSON or fails schema validation, StreetRace automatically:
1. Captures the error message
2. Sends the error back to the LLM
3. Requests a corrected response
4. Retries up to 3 times

Example retry feedback sent to LLM:
```
Error: 1 validation error for CodeReviewResult
confidence
  Input should be a valid number [type=float_parsing, ...]

Please fix the JSON and try again. Ensure you return only valid JSON
matching the schema.
```

### Validation Failure

After 3 failed attempts, a `SchemaValidationError` is raised. In flows, this triggers
the escalation system:

```streetrace
flow main:
    $result = call llm analyze_task $input_prompt
    # If validation fails 3 times, SchemaValidationError is raised
    # Handle with escalation if needed
```

## Using Schemas in Flows

### Direct LLM Calls

Use `call llm` to invoke schema-expecting prompts:

```streetrace
flow analyze:
    $result = call llm analyze_task $input_prompt
    # $result is a validated dict matching TaskAnalysis schema
    if $result.priority == "high":
        notify "High priority task detected!"
    return $result
```

### Accessing Structured Fields

Schema results are dictionaries with typed fields:

```streetrace
schema TaskAnalysis:
    priority: string
    estimated_hours: float
    dependencies: list[string]

flow process_task:
    $analysis = call llm analyze_task $input_prompt

    # Access fields directly
    log "Priority: ${analysis.priority}"
    log "Hours: ${analysis.estimated_hours}"

    for $dep in $analysis.dependencies do
        log "Depends on: ${dep}"
    end
```

### With Agents

Agents using schema-expecting prompts receive structured output:

```streetrace
agent task_analyst:
    instruction analyze_task  # Has expecting TaskAnalysis

flow delegate_analysis:
    $result = run agent task_analyst $input_prompt
    # ADK handles schema validation when output_schema is set
    return $result
```

## Multiple Schemas

Define multiple schemas for different purposes:

```streetrace
schema CodeReviewResult:
    approved: bool
    severity: string
    issues: list[string]
    suggestions: list[string]
    confidence: float

schema TaskAnalysis:
    priority: string
    estimated_hours: float
    dependencies: list[string]
    risks: list[string]
    recommended_approach: string

schema BugReport:
    title: string
    description: string
    steps_to_reproduce: list[string]
    expected_behavior: string
    actual_behavior: string
    severity: string
    affected_files: list[string]

prompt review_code expecting CodeReviewResult: """..."""
prompt analyze_task expecting TaskAnalysis: """..."""
prompt report_bug expecting BugReport: """..."""
```

## Best Practices

### 1. Keep Schemas Focused

Define schemas with a specific purpose. Avoid catch-all schemas with many optional fields.

```streetrace
# Good - focused schema
schema SentimentResult:
    sentiment: string
    confidence: float
    keywords: list[string]

# Avoid - too generic
schema GenericResult:
    data: string?
    error: string?
    items: list[string]?
    count: int?
    # ... many more optional fields
```

### 2. Use Descriptive Field Names

Field names should clearly indicate their purpose:

```streetrace
# Good
schema ReviewOutcome:
    is_approved: bool
    blocking_issues: list[string]
    improvement_suggestions: list[string]

# Avoid
schema ReviewOutcome:
    ok: bool
    items: list[string]
    items2: list[string]
```

### 3. Choose Appropriate Types

- Use `bool` for yes/no decisions
- Use `string` for categories, enums, or text
- Use `int` for counts, IDs
- Use `float` for scores, percentages, measurements
- Use `list[T]` for collections

### 4. Handle Optional Fields

Mark fields optional when they may legitimately be absent:

```streetrace
schema SearchResult:
    found: bool
    match: string?        # Only present if found=true
    confidence: float?    # May not always be calculable
```

### 5. Prompt Clarity

Write clear prompts that guide the LLM to produce valid output:

```streetrace
prompt analyze expecting AnalysisResult: """
Analyze the input and provide your assessment.

For severity, use one of: "critical", "high", "medium", "low"
For confidence, provide a decimal between 0.0 and 1.0
List all issues found, even if the list is empty.
"""
```

## Error Messages

### JSONParseError

```
Failed to parse JSON from response: Expecting property name enclosed in double quotes
```

**Cause**: LLM returned invalid JSON syntax.
**Solution**: The system retries automatically. If persistent, simplify your schema or
clarify JSON requirements in the prompt.

### SchemaValidationError

```
Schema validation failed for 'CodeReviewResult': 1 validation error for CodeReviewResult
approved
  Field required [type=missing, ...]
```

**Cause**: Response missing required fields or wrong types.
**Solution**: Check that your prompt clearly requests all required fields. Consider
making some fields optional if appropriate.

### Multiple Code Blocks

```
Response contains multiple code blocks. Please return a single JSON object.
```

**Cause**: LLM returned multiple ```json``` blocks.
**Solution**: The system retries automatically with instructions to return a single block.

## Troubleshooting

### Schema Validation Keeps Failing

1. **Check prompt clarity**: Ensure the prompt explicitly requests JSON output
2. **Simplify schema**: Start with fewer fields, add more once basic validation works
3. **Use appropriate types**: Ensure types match what the LLM naturally produces
4. **Check field names**: Ensure LLM understands what each field should contain

### Getting Text Instead of JSON

If the LLM returns explanatory text instead of JSON:

1. Ensure `expecting SchemaName` is on the prompt
2. The system automatically adds JSON instructions
3. Check generated code with `poetry run streetrace dump-python your_file.sr`

### Debugging Schema Issues

View the generated Python code to see how schemas are created:

```bash
poetry run streetrace dump-python my_workflow.sr | grep -A 20 "_schemas"
```

## Limitations

Current limitations of schema support:

1. **No nested schemas**: Schemas cannot reference other schemas
   ```streetrace
   # NOT SUPPORTED
   schema Inner:
       value: int

   schema Outer:
       inner: Inner  # Cannot use Inner as a type
   ```

2. **No union types**: Fields cannot have multiple types
   ```streetrace
   # NOT SUPPORTED
   schema Result:
       value: string | int  # Union types not supported
   ```

3. **No enum constraints**: Cannot limit strings to specific values
   ```streetrace
   # NOT SUPPORTED
   schema Status:
       state: "pending" | "active" | "done"
   ```

4. **No field constraints**: Cannot add validation rules
   ```streetrace
   # NOT SUPPORTED
   schema Score:
       value: float @min(0.0) @max(1.0)
   ```

## See Also

- [Syntax Reference](syntax-reference.md) - Complete DSL syntax
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [Escalation](escalation.md) - Handling validation failures in flows
