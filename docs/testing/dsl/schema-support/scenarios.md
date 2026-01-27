# Schema Support - Test Scenarios

This document describes manual end-to-end test scenarios for the Schema Support feature.

## Feature Scope

The Schema Support feature covers:

1. **Schema definitions** - `schema Name:` blocks with typed fields
2. **Prompt expecting clause** - `expecting SchemaName` modifier on prompts
3. **Runtime validation** - JSON parsing and Pydantic validation with retry
4. **Agent output_schema** - Passing schema to ADK LlmAgent
5. **Error handling** - JSONParseError and SchemaValidationError

## User Journeys

### Journey 1: Get Structured Output from LLM

A user wants to receive structured, typed data from an LLM instead of parsing free text.

**Steps**:
1. Define a schema with required fields
2. Create a prompt with `expecting` clause
3. Run the agent or flow
4. Verify response matches schema structure

### Journey 2: Handle Validation Failures

A user's prompt sometimes receives invalid responses that don't match the schema.

**Steps**:
1. Create a schema with specific type requirements
2. Run with input that may produce edge-case responses
3. Verify retry mechanism activates on validation failure
4. Verify final error if retries exhausted

### Journey 3: Use Optional Fields

A user wants some schema fields to be optional when the LLM doesn't have relevant data.

**Steps**:
1. Define schema with optional fields (`type?`)
2. Run with input where optional fields may be absent
3. Verify response validates with null/missing optional fields

---

## Scenario 1: Basic Schema Validation

**Feature**: Schema definitions convert to Pydantic models and validate responses.

### Scenario 1.1: Simple Schema with Required Fields

**Input DSL** (`test_simple_schema.sr`):
```sr
model main = anthropic/claude-sonnet

schema SimpleResult:
    success: bool
    message: string

prompt analyze expecting SimpleResult: """
Analyze the input. Return success=true if it looks valid, false otherwise.
Include a brief message explaining your decision.

Input: ${input_prompt}
"""

agent analyzer:
    instruction analyze
```

**Test Command**:
```bash
poetry run streetrace run test_simple_schema.sr --input "Hello world"
```

**Expected Output**:
- Valid JSON matching the schema
- Example:
```json
{
  "success": true,
  "message": "The input 'Hello world' is a valid greeting."
}
```

**Verification**:
1. Response is valid JSON
2. Has `success` field with boolean value
3. Has `message` field with string value
4. No extra fields outside schema

### Scenario 1.2: Schema with List Fields

**Input DSL** (`test_list_schema.sr`):
```sr
model main = anthropic/claude-sonnet

schema ListResult:
    items: list[string]
    counts: list[int]

prompt extract expecting ListResult: """
Extract items and their counts from the input.

Input: ${input_prompt}
"""

agent extractor:
    instruction extract
```

**Test Command**:
```bash
poetry run streetrace run test_list_schema.sr --input "3 apples, 2 oranges, 5 bananas"
```

**Expected Output**:
```json
{
  "items": ["apples", "oranges", "bananas"],
  "counts": [3, 2, 5]
}
```

**Verification**:
1. `items` is a list of strings
2. `counts` is a list of integers
3. List contents are correctly extracted

### Scenario 1.3: Schema with Float Fields

**Input DSL** (`test_float_schema.sr`):
```sr
model main = anthropic/claude-sonnet

schema ScoreResult:
    name: string
    score: float
    percentile: float

prompt evaluate expecting ScoreResult: """
Evaluate the input and assign a score between 0.0 and 1.0.
Calculate the percentile as a percentage (0-100).

Input: ${input_prompt}
"""

agent evaluator:
    instruction evaluate
```

**Test Command**:
```bash
poetry run streetrace run test_float_schema.sr --input "Excellent work on the project"
```

**Expected Output**:
```json
{
  "name": "Project Evaluation",
  "score": 0.95,
  "percentile": 95.0
}
```

**Verification**:
1. `score` is a valid float
2. `percentile` is a valid float
3. Values are reasonable for the input

---

## Scenario 2: Optional Fields

**Feature**: Fields marked with `?` accept null values or can be missing.

### Scenario 2.1: Optional String Field

**Input DSL** (`test_optional_string.sr`):
```sr
model main = anthropic/claude-sonnet

schema OptionalResult:
    status: string
    details: string?

prompt check expecting OptionalResult: """
Check the input. Provide status as "ok" or "error".
Only include details if there's something notable to report.

Input: ${input_prompt}
"""

agent checker:
    instruction check
```

**Test Commands**:
```bash
# Case 1: Details present
poetry run streetrace run test_optional_string.sr --input "Something interesting"

# Case 2: Details absent
poetry run streetrace run test_optional_string.sr --input "Nothing special"
```

**Expected Output** (Case 1):
```json
{
  "status": "ok",
  "details": "The input contains interesting content"
}
```

**Expected Output** (Case 2):
```json
{
  "status": "ok",
  "details": null
}
```
or
```json
{
  "status": "ok"
}
```

**Verification**:
1. Required `status` field is always present
2. Optional `details` can be null or omitted
3. Both responses validate successfully

### Scenario 2.2: Multiple Optional Fields

**Input DSL** (`test_multi_optional.sr`):
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

Input: ${input_prompt}
"""

agent flexible:
    instruction flexible
```

**Test Command**:
```bash
poetry run streetrace run test_multi_optional.sr --input "Basic input"
```

**Verification**:
1. `required_field` is always present
2. Optional fields can be present, null, or missing
3. All combinations validate successfully

---

## Scenario 3: Validation Retry

**Feature**: Failed validation triggers automatic retry with error feedback.

### Scenario 3.1: Type Mismatch Recovery

This scenario tests that the system retries when the LLM returns wrong types.

**Input DSL** (`test_retry.sr`):
```sr
model main = anthropic/claude-sonnet

schema StrictTypes:
    count: int
    ratio: float
    active: bool

prompt strict expecting StrictTypes: """
Provide counts and ratios for the input.

IMPORTANT: count must be an integer (e.g., 5, not 5.0 or "five")
ratio must be a decimal number (e.g., 0.75)
active must be true or false (not "yes" or 1)

Input: ${input_prompt}
"""

agent strict_checker:
    instruction strict
```

**Test Command**:
```bash
STREETRACE_LOG_LEVEL=DEBUG poetry run streetrace run test_retry.sr --input "Count 5 items with 75% ratio"
```

**Expected Behavior**:
1. LLM returns response
2. If types are wrong, validation fails
3. Error message sent back to LLM
4. LLM retries with corrected response
5. Eventually validates successfully

**Log Output to Check**:
```
DEBUG ... Schema validation attempt 1/3 failed for 'strict': ...
DEBUG ... Schema validation attempt 2/3 ...
```

**Verification**:
1. Check debug logs for retry attempts
2. Final response validates correctly
3. All field types are correct

### Scenario 3.2: Missing Required Field Recovery

**Input DSL** (`test_missing_field.sr`):
```sr
model main = anthropic/claude-sonnet

schema AllRequired:
    field_a: string
    field_b: string
    field_c: string

prompt all_fields expecting AllRequired: """
Provide exactly three fields: field_a, field_b, and field_c.
Each should contain a single word describing the input.

Input: ${input_prompt}
"""

agent all_fields_checker:
    instruction all_fields
```

**Test Command**:
```bash
STREETRACE_LOG_LEVEL=DEBUG poetry run streetrace run test_missing_field.sr --input "Test input"
```

**Verification**:
1. If LLM omits a field, validation fails
2. Error feedback specifies missing field
3. LLM retries with all fields
4. Final response has all three fields

---

## Scenario 4: Schema in Flows

**Feature**: `call llm` with schema-expecting prompts returns validated dicts.

### Scenario 4.1: Flow Accessing Schema Fields

**Input DSL** (`test_flow_schema.sr`):
```sr
model main = anthropic/claude-sonnet

schema TaskStatus:
    completed: bool
    progress: int
    message: string

prompt check_task expecting TaskStatus: """
Check the status of the task described in the input.
Set completed to true if done, false otherwise.
Set progress as percentage (0-100).
Provide a brief status message.

Task: ${input_prompt}
"""

flow main:
    $status = call llm check_task $input_prompt

    if $status.completed:
        return "Done: " + $status.message
    end

    return "In progress (" + $status.progress + "%): " + $status.message
```

**Test Commands**:
```bash
# Completed task
poetry run streetrace run test_flow_schema.sr --input "Task: Deploy to production (done)"

# In-progress task
poetry run streetrace run test_flow_schema.sr --input "Task: Write documentation (50% done)"
```

**Expected Output** (completed):
```
Done: Deployment completed successfully
```

**Expected Output** (in progress):
```
In progress (50%): Documentation is halfway complete
```

**Verification**:
1. `$status.completed` is accessible as boolean
2. `$status.progress` is accessible as integer
3. `$status.message` is accessible as string
4. Flow logic works with structured data

### Scenario 4.2: Flow with List Iteration

**Input DSL** (`test_flow_list.sr`):
```sr
model main = anthropic/claude-sonnet

schema ItemList:
    items: list[string]
    priority: string

prompt extract_items expecting ItemList: """
Extract action items from the input.
List each item in the items array.
Set priority to "high", "medium", or "low".

Input: ${input_prompt}
"""

flow main:
    $result = call llm extract_items $input_prompt
    $output = "Priority: " + $result.priority + "\nItems:\n"

    for $item in $result.items do
        $output = $output + "- " + $item + "\n"
    end

    return $output
```

**Test Command**:
```bash
poetry run streetrace run test_flow_list.sr --input "Fix bug, write tests, update docs"
```

**Expected Output**:
```
Priority: high
Items:
- Fix bug
- Write tests
- Update docs
```

**Verification**:
1. List iteration works with schema field
2. Priority field is accessible
3. Output is correctly formatted

---

## Scenario 5: Agent with output_schema

**Feature**: Agents pass output_schema to ADK LlmAgent.

### Scenario 5.1: Agent Structured Output

**Input DSL** (`test_agent_schema.sr`):
```sr
model main = anthropic/claude-sonnet

schema ReviewResult:
    approved: bool
    comments: list[string]
    score: int

prompt review expecting ReviewResult: """
Review the code or text provided.
Set approved to true if acceptable.
List any comments or suggestions.
Provide a score from 1-10.
"""

agent reviewer:
    instruction review
    description "Reviews content and provides structured feedback"
```

**Test Command**:
```bash
poetry run streetrace run test_agent_schema.sr --input "def add(a, b): return a + b"
```

**Expected Output**:
```json
{
  "approved": true,
  "comments": ["Consider adding type hints", "Add docstring"],
  "score": 7
}
```

**Verification**:
1. Response is structured JSON
2. All fields match expected types
3. ADK handles schema automatically

### Scenario 5.2: Multiple Agents with Different Schemas

Use the example file with multiple schemas:

**Test Command**:
```bash
# Test code reviewer agent
poetry run streetrace run agents/examples/dsl/schema.sr --agent code_reviewer \
    --input "def divide(a, b): return a / b"

# Test task analyst agent
poetry run streetrace run agents/examples/dsl/schema.sr --agent task_analyst \
    --input "Implement user authentication"
```

**Verification**:
1. code_reviewer returns CodeReviewResult structure
2. task_analyst returns TaskAnalysis structure
3. Each agent uses its schema correctly

---

## Scenario 6: Error Cases

**Feature**: Proper error handling for validation failures.

### Scenario 6.1: SchemaValidationError After Retries

Create a scenario designed to fail validation:

**Input DSL** (`test_fail_validation.sr`):
```sr
model main = anthropic/claude-sonnet

schema ImpossibleSchema:
    exact_value: string
    specific_number: int

prompt impossible expecting ImpossibleSchema: """
Return exact_value as "IMPOSSIBLE_TO_GUESS_12345"
Return specific_number as exactly 98765
"""

flow main:
    $result = call llm impossible $input_prompt
    return $result.exact_value
```

**Note**: This test may not reliably fail - it depends on LLM behavior. For reliable
failure testing, use unit tests that mock LLM responses.

### Scenario 6.2: JSON Parse Error (Multiple Code Blocks)

This scenario requires an LLM that returns multiple code blocks. Not reliably reproducible
in manual testing.

**Expected Behavior** (if triggered):
```
Error: Response contains multiple code blocks. Please return a single JSON object.
```

---

## Scenario 7: Code Generation Verification

**Feature**: Generated Python code correctly implements schema support.

### Scenario 7.1: Verify Schema Emission

**Check generated code**:
```bash
poetry run streetrace dump-python agents/examples/dsl/schema.sr
```

**Expected Code** (excerpt):
```python
from pydantic import BaseModel, create_model

class SchemaWorkflow(DslAgentWorkflow):
    CodeReviewResult = create_model(
        "CodeReviewResult",
        approved=(bool, ...),
        severity=(str, ...),
        issues=(list[str], ...),
        suggestions=(list[str], ...),
        confidence=(float, ...),
    )

    _schemas: dict[str, type[BaseModel]] = {
        "CodeReviewResult": CodeReviewResult,
        "TaskAnalysis": TaskAnalysis,
        "BugReport": BugReport,
    }
```

**Verification**:
1. Pydantic imports are present
2. Each schema has `create_model()` call
3. Type mappings are correct (string -> str, etc.)
4. `_schemas` dict maps names to models

### Scenario 7.2: Verify PromptSpec with Schema

**Expected Code** (excerpt):
```python
_prompts = {
    'review_code': PromptSpec(
        body=lambda ctx: f"""You are an expert code reviewer...""",
        schema='CodeReviewResult',
    ),
}
```

**Verification**:
1. PromptSpec has `schema` parameter
2. Schema name matches defined schema
3. Schema reference is a string (name lookup at runtime)

---

## Troubleshooting

### Schema Not Being Applied

**Symptoms**: LLM returns free-form text instead of JSON.

**Debug Steps**:
1. Check prompt has `expecting SchemaName`:
   ```bash
   grep "expecting" your_file.sr
   ```
2. Verify schema is defined:
   ```bash
   grep "schema" your_file.sr
   ```
3. Check generated code:
   ```bash
   poetry run streetrace dump-python your_file.sr | grep "schema="
   ```

### Validation Always Failing

**Symptoms**: SchemaValidationError after 3 attempts.

**Debug Steps**:
1. Enable debug logging:
   ```bash
   STREETRACE_LOG_LEVEL=DEBUG poetry run streetrace run your_file.sr --input "test"
   ```
2. Check error messages in logs
3. Verify schema types match LLM output patterns
4. Simplify schema and retry

### Type Conversion Issues

**Symptoms**: LLM returns "5" (string) but schema expects int.

**Debug Steps**:
1. Check schema type definition
2. Make prompt more explicit about types:
   ```
   Return count as an integer number (e.g., 5), not a string.
   ```
3. Check if LLM model follows instructions well

---

## Reference Documents

- `docs/tasks/017-dsl/schema-support/tasks.md`: Design specification, 2026-01-27
- `docs/dev/dsl/schema-support.md`: Developer documentation, 2026-01-27
- `docs/user/dsl/schema-support.md`: User documentation, 2026-01-27
- `agents/examples/dsl/schema.sr`: Example DSL file with schemas, 2026-01-27
