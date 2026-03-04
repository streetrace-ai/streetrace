# Schema Support - Environment Setup

This document describes the environment setup required for manual end-to-end testing of
the Schema Support feature.

## Prerequisites

### 1. Python Environment

Ensure you have StreetRace installed with development dependencies:

```bash
cd /path/to/streetrace
poetry install
```

### 2. API Keys

Schema validation requires working LLM calls. Set up at least one API key:

```bash
# Anthropic (recommended for testing)
export ANTHROPIC_API_KEY="your-key-here"

# Or OpenAI
export OPENAI_API_KEY="your-key-here"
```

### 3. Log Level (Optional)

For detailed debugging, enable debug logging:

```bash
export STREETRACE_LOG_LEVEL=DEBUG
```

## Test Files Location

Test DSL files should be created in a temporary directory or use the provided example:

```bash
# Existing example file
cat agents/examples/dsl/schema.sr

# Create temporary test directory
mkdir -p /tmp/schema-tests
```

## Verifying Setup

Run a basic test to verify the environment:

```bash
# Check DSL compilation works
poetry run streetrace check agents/examples/dsl/schema.sr

# Should output: "agents/examples/dsl/schema.sr: OK"
```

## Test Input Files

### Basic Schema Test (`basic_schema.sr`)

```sr
model main = anthropic/claude-sonnet

schema SimpleResult:
    success: bool
    message: string

prompt analyze expecting SimpleResult: """
Analyze the input and respond with your assessment.
Return success=true if input is valid, false otherwise.
Include a brief message explaining your decision.
"""

agent analyzer:
    instruction analyze
```

### Complex Schema Test (`complex_schema.sr`)

```sr
model main = anthropic/claude-sonnet

schema DetailedAnalysis:
    category: string
    confidence: float
    tags: list[string]
    issues: list[string]
    recommendations: list[string]
    needs_review: bool?

prompt detailed_analyze expecting DetailedAnalysis: """
Perform a detailed analysis of the input.

For category, choose from: "positive", "negative", "neutral"
For confidence, provide a value between 0.0 and 1.0
List relevant tags, issues found, and recommendations.
Set needs_review to true if human review is recommended.
"""

agent detailed_analyzer:
    instruction detailed_analyze
```

### Flow with Schema (`flow_schema.sr`)

```sr
model main = anthropic/claude-sonnet

schema TaskResult:
    completed: bool
    output: string
    errors: list[string]

prompt process_task expecting TaskResult: """
Process the given task and report results.
Set completed=true if successful.
Include output in the output field.
List any errors encountered in the errors list.
"""

flow main:
    $result = call llm process_task $input_prompt
    if $result.completed:
        return $result.output
    end
    return "Failed: " + $result.errors[0]
```

### Optional Fields Test (`optional_fields.sr`)

```sr
model main = anthropic/claude-sonnet

schema FlexibleResult:
    required_field: string
    optional_string: string?
    optional_int: int?
    optional_list: list[string]?

prompt flexible expecting FlexibleResult: """
Analyze the input. Always provide required_field.
Only include optional fields if they are relevant.
"""

agent flexible_analyzer:
    instruction flexible
```

## Creating Test Files

Copy these to your test directory:

```bash
cat > /tmp/schema-tests/basic_schema.sr << 'EOF'
model main = anthropic/claude-sonnet

schema SimpleResult:
    success: bool
    message: string

prompt analyze expecting SimpleResult: """
Analyze the input and respond with your assessment.
Return success=true if input is valid, false otherwise.
Include a brief message explaining your decision.
"""

agent analyzer:
    instruction analyze
EOF
```

## Environment Variables Summary

| Variable | Purpose | Example |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API access | `sk-ant-...` |
| `OPENAI_API_KEY` | OpenAI API access | `sk-...` |
| `STREETRACE_LOG_LEVEL` | Log verbosity | `DEBUG`, `INFO` |

## Reference Documents

- `docs/tasks/017-dsl/schema-support/tasks.md`: Design specification, 2026-01-27
- `docs/dev/dsl/schema-support.md`: Developer documentation, 2026-01-27
- `docs/user/dsl/schema-support.md`: User documentation, 2026-01-27
