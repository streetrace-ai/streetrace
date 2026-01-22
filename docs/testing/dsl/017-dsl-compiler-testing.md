# DSL Compiler Manual Testing Guide

| Field | Value |
|-------|-------|
| **Feature ID** | 017-dsl-compiler |
| **Feature Name** | DSL Compiler for Streetrace Agent Definition Language |
| **Status** | Draft |
| **Last Updated** | 2026-01-20 |

## Overview

This document provides comprehensive manual testing instructions for the Streetrace DSL compiler feature. The DSL compiler transforms `.sr` (Streetrace) files through a complete pipeline: lexing, parsing with Lark, AST transformation, semantic analysis, Python code generation, and compilation to bytecode.

### Feature Scope

The DSL compiler enables developers to:

1. **Write agent definitions** in a declarative `.sr` file format
2. **Validate syntax and semantics** before execution
3. **Inspect generated Python code** for debugging
4. **Execute DSL agents** through the standard Streetrace runtime
5. **Debug runtime errors** with stack traces translated to `.sr` line numbers

### User Journeys

| Journey | Description | Primary Commands |
|---------|-------------|------------------|
| Validation in Development | Validate `.sr` files before execution | `streetrace check` |
| Debugging Generated Code | Inspect the Python code produced from DSL | `streetrace dump-python` |
| Agent Execution | Run DSL-defined agents | `streetrace run my_agent.sr` |
| CI/CD Integration | Validate agents in pipelines | `streetrace check --format json` |
| Runtime Error Investigation | Debug errors with source-mapped traces | (automatic) |

---

## 1. Environment Setup

### 1.1 Prerequisites

Ensure Streetrace is installed with DSL support:

```bash
poetry install
```

Verify the DSL commands are available:

```bash
poetry run streetrace check --help
poetry run streetrace dump-python --help
```

### 1.2 Environment Variables

No specific environment variables are required for basic DSL compilation. However, DSL files may reference environment variables using `${env:VAR}` syntax:

| Variable Pattern | Access |
|------------------|--------|
| `STREETRACE_*` | Allowed by default |
| `SR_*` | Allowed by default |
| Other variables | Require explicit allowlist |

### 1.3 Test File Location

The repository includes pre-built example DSL files for testing:

```bash
# Example DSL files demonstrating various features
agents/examples/dsl/

# Converted production agents
agents/*.sr
```

**Available Example Files:**

| File | Features Demonstrated |
|------|----------------------|
| `agents/examples/dsl/minimal.sr` | Basic agent structure |
| `agents/examples/dsl/handlers.sr` | Event handlers, guardrails |
| `agents/examples/dsl/flow.sr` | Agent definitions, flows |
| `agents/examples/dsl/parallel.sr` | Multiple agents, flows |
| `agents/examples/dsl/schema.sr` | Structured outputs |
| `agents/examples/dsl/policies.sr` | Retry/timeout policies |
| `agents/examples/dsl/match.sr` | Request classification, flows |
| `agents/examples/dsl/complete.sr` | Combined features |
| `agents/examples/dsl/specific_model.sr` | Model-specific prompts |

**Converted Production Agents:**

| File | Original |
|------|----------|
| `agents/generic.sr` | `agents/generic.yml` |
| `agents/reviewer.sr` | `agents/reviewer.yml` |
| `agents/orchestrator.sr` | `agents/orchestrator.yml` |

Alternatively, create test files in a temporary directory:

```bash
mkdir -p /tmp/dsl-test
cd /tmp/dsl-test
```

---

## 2. CLI Command Testing

### 2.1 `streetrace check` Command

The `check` command validates DSL files without execution.

#### Usage

```
streetrace check [OPTIONS] PATH

Arguments:
  PATH  DSL file or directory to validate  [required]

Options:
  -v, --verbose    Enable verbose output
  --format FORMAT  Output format: text (default), json
  --strict         Treat warnings as errors
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All files valid |
| 1 | Validation errors found |
| 2 | File not found or permission error |

#### Test Scenario: Validate a Valid File

**Input:** Use the pre-built example `agents/examples/dsl/minimal.sr`:

```streetrace
# Minimal Agent Example
# Demonstrates the simplest possible DSL agent definition

model main = anthropic/claude-sonnet

prompt greeting: """You are a helpful assistant. Greet the user warmly and offer to help with their questions."""

agent:
    instruction greeting
```

**Command:**

```bash
poetry run streetrace check agents/examples/dsl/minimal.sr
```

**Expected Output:**

```
valid (1 model, 1 agent)
```

**Expected Exit Code:** `0`

#### Test Scenario: Validate with Verbose Output

**Command:**

```bash
poetry run streetrace check agents/examples/dsl/minimal.sr --verbose
```

**Expected Output:**

```
agents/examples/dsl/minimal.sr: valid (1 model, 1 agent)
```

#### Test Scenario: Validate a Directory

**Setup:** Use the pre-built example directory `agents/examples/dsl/`

**Command:**

```bash
poetry run streetrace check agents/examples/dsl/
```

**Expected Output:** Validation results for each `.sr` file found (9 files total).

#### Test Scenario: JSON Output Format

**Command:**

```bash
poetry run streetrace check minimal_agent.sr --format json
```

**Expected Output:**

```json
{
  "version": "1.0",
  "file": "minimal_agent.sr",
  "valid": true,
  "errors": [],
  "warnings": [],
  "stats": {
    "models": 1,
    "agents": 1,
    "flows": 0,
    "handlers": 0
  }
}
```

#### Test Scenario: File Not Found

**Command:**

```bash
poetry run streetrace check nonexistent.sr
```

**Expected Output:**

```
error: file not found: nonexistent.sr
```

**Expected Exit Code:** `2`

---

### 2.2 `streetrace dump-python` Command

The `dump-python` command outputs the generated Python code for inspection.

#### Usage

```
streetrace dump-python [OPTIONS] FILE

Arguments:
  FILE  DSL file to convert  [required]

Options:
  --no-comments      Exclude source comments from output
  -o, --output FILE  Output file path (default: stdout)
```

#### Test Scenario: Dump Python to Stdout

**Command:**

```bash
poetry run streetrace dump-python minimal_agent.sr
```

**Expected Output:** Python code including:

- Class definition extending `DslAgentWorkflow`
- Model definitions
- Tool configurations
- Agent setup methods
- Source line comments (e.g., `# minimal_agent.sr:5`)

#### Test Scenario: Dump Without Comments

**Command:**

```bash
poetry run streetrace dump-python minimal_agent.sr --no-comments
```

**Expected Output:** Python code without `# filename:line` comments.

#### Test Scenario: Dump to File

**Command:**

```bash
poetry run streetrace dump-python minimal_agent.sr -o /tmp/generated.py
```

**Expected Output:**

```
wrote: /tmp/generated.py
```

**Verification:**

```bash
python -m py_compile /tmp/generated.py  # Should succeed
```

---

### 2.3 `streetrace run` Command (DSL Agent Execution)

The `run` command executes DSL agents directly.

#### Test Scenario: Run a DSL Agent

**Command:**

```bash
poetry run streetrace run minimal_agent.sr --model anthropic/claude-sonnet
```

**Expected Behavior:**

1. DSL file is compiled to Python bytecode
2. Workflow class is instantiated
3. Agent executes in the Streetrace runtime
4. User can interact with the agent

---

## 3. Example DSL Files for Testing

The following examples are available in the `agents/examples/dsl/` directory. Each should be validated using `streetrace check`.

### 3.1 Minimal Agent

**File:** `agents/examples/dsl/minimal.sr`

```streetrace
# Minimal Agent Example
# Demonstrates the simplest possible DSL agent definition

model main = anthropic/claude-sonnet

prompt greeting: """You are a helpful assistant. Greet the user warmly and offer to help with their questions."""

agent:
    instruction greeting
```

**Validation:**

```bash
poetry run streetrace check agents/examples/dsl/minimal.sr
# Expected: valid (1 model, 1 agent)
```

### 3.2 Agent with Event Handlers

**File:** `agents/examples/dsl/handlers.sr`

```streetrace
# Event Handlers Example
# Demonstrates event handlers with guardrail actions

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

# Input guardrails - protect against harmful inputs
on input do
    mask pii
    block if jailbreak
end

# Output guardrails - ensure safe outputs
on output do
    mask pii
end

prompt assistant: """You are a helpful coding assistant. Help the user with their programming questions and tasks. Be concise and provide code examples when helpful."""

agent:
    tools fs
    instruction assistant
```

**Validation:**

```bash
poetry run streetrace check agents/examples/dsl/handlers.sr
# Expected: valid (1 model, 1 agent, 2 handlers)
```

### 3.3 Agent with Multiple Definitions

**File:** `agents/examples/dsl/flow.sr`

```streetrace
# Flow Example
# Demonstrates basic flow definition

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt summarize_prompt: """Summarize the analysis results into a final report. Highlight critical issues and provide recommendations."""

agent summarizer:
    tools fs
    instruction summarize_prompt
    description "Summarizes analysis results"

agent:
    tools fs
    instruction summarize_prompt
```

**Validation:**

```bash
poetry run streetrace check agents/examples/dsl/flow.sr
# Expected: valid (2 models, 3 agents, 1 flow)
```

**Note:** The actual `flow.sr` file includes additional models, agents, and a flow definition beyond the simplified example shown above.

### 3.4 Agent with Parallel Execution

**File:** `agents/examples/dsl/parallel.sr`

```streetrace
# Parallel Execution Example
# Demonstrates basic agent definitions

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt synthesize_prompt: """Combine the research results from multiple sources. Provide a comprehensive summary with all relevant information. Cite sources and highlight key findings."""

agent synthesizer:
    tools fs
    instruction synthesize_prompt
    description "Synthesizes research results"

agent:
    tools fs
    instruction synthesize_prompt
```

**Validation:**

```bash
poetry run streetrace check agents/examples/dsl/parallel.sr
# Expected: valid (1 model, 4 agents, 1 flow)
```

**Note:** The actual `parallel.sr` file includes additional agents and a flow definition beyond the simplified example shown above.

### 3.5 Agent with Schema (Structured Output)

**File:** `agents/examples/dsl/schema.sr`

```streetrace
# Schema Example
# Demonstrates structured outputs with schemas

model main = anthropic/claude-sonnet

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

prompt review_code expecting CodeReviewResult: """You are an expert code reviewer. Analyze the provided code for bugs, security issues, and code quality. Evaluate logic errors, security vulnerabilities, performance issues, and code style. Provide your assessment in the structured format."""

prompt analyze_task expecting TaskAnalysis: """Analyze the given task and provide a structured assessment. Consider priority level (high, medium, low), estimated time to complete, dependencies on other tasks or systems, potential risks and challenges, and recommended implementation approach."""

prompt report_bug expecting BugReport: """Document the bug based on the provided information. Include all relevant details for reproducing and fixing the bug. Be specific about steps to reproduce and expected vs actual behavior."""

agent code_reviewer:
    instruction review_code
    description "Reviews code and provides structured feedback"

agent task_analyst:
    instruction analyze_task
    description "Analyzes tasks and provides structured estimates"

agent bug_reporter:
    instruction report_bug
    description "Creates structured bug reports"

agent:
    instruction review_code
```

**Validation:**

```bash
poetry run streetrace check agents/examples/dsl/schema.sr
# Expected: valid (1 model, 4 agents)
```

### 3.6 Agent with Policies

**File:** `agents/examples/dsl/policies.sr`

```streetrace
# Policies Example
# Demonstrates retry and timeout policies

model main = anthropic/claude-sonnet
model fast = anthropic/haiku

retry default = 3 times, exponential backoff
retry simple = 2 times, fixed backoff

timeout default = 2 minutes
timeout short = 30 seconds

tool fs = builtin streetrace.fs

prompt reliable_task: """Perform the requested task reliably. If you encounter errors, report them clearly."""

agent reliable_worker:
    instruction reliable_task
    retry default
    timeout default
    description "Reliable worker with standard retry and timeout"

agent quick_responder:
    instruction reliable_task
    retry simple
    timeout short
    description "Fast responder for quick queries"

agent:
    tools fs
    instruction reliable_task
    retry default
    timeout default
```

**Validation:**

```bash
poetry run streetrace check agents/examples/dsl/policies.sr
# Expected: valid (2 models, 3 agents)
```

### 3.7 Agent with Pattern Matching

**File:** `agents/examples/dsl/match.sr`

```streetrace
# Pattern Matching Example
# Demonstrates request classification agents

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt classify_prompt: """Classify the user request into one of these categories: billing (payment, invoice, subscription issues), technical (bugs, errors, technical support), sales (pricing, plans, upgrades), or feedback (suggestions, complaints, praise). Return only the category name."""

agent classifier:
    instruction classify_prompt
    description "Classifies user requests"

agent:
    tools fs
    instruction classify_prompt
```

**Validation:**

```bash
poetry run streetrace check agents/examples/dsl/match.sr
# Expected: valid (1 model, 7 agents, 1 flow)
```

**Note:** The actual `match.sr` file includes additional agents and a flow definition beyond the simplified example shown above.

### 3.8 Complete Example (Combined Features)

**File:** `agents/examples/dsl/complete.sr`

This example combines multiple DSL features: models, schemas, tools, policies, event handlers, and agents.

```streetrace
# Complete Example
# Demonstrates major DSL features

model main = anthropic/claude-sonnet
model fast = anthropic/haiku

schema AnalysisResult:
    summary: string
    score: float
    issues: list[string]
    recommendations: list[string]

tool fs = builtin streetrace.fs

retry default = 3 times, exponential backoff
timeout default = 2 minutes

on input do
    mask pii
    block if jailbreak
end

on output do
    mask pii
end

prompt analyze_code expecting AnalysisResult: """Analyze the provided code for quality issues. Look for security vulnerabilities, performance problems, code style issues, and logic errors. Provide a structured analysis result."""

prompt main_instruction: """You are a code analysis assistant. Help users analyze their codebase for quality issues. Available commands: Analyze a file or directory, Get recommendations for improvement, Explain specific issues."""

agent code_analyzer:
    instruction analyze_code
    description "Analyzes code quality"

agent:
    tools fs
    instruction main_instruction
    retry default
    timeout default
```

**Validation:**

```bash
poetry run streetrace check agents/examples/dsl/complete.sr
# Expected: valid (2 models, 2 agents, 2 handlers)
```

### 3.9 Converted Production Agents

The following production agents have been converted from YAML to DSL format:

#### Generic Coding Assistant

**File:** `agents/generic.sr` (converted from `agents/generic.yml`)

```bash
poetry run streetrace check agents/generic.sr
# Expected: valid (1 model, 1 agent)
```

#### Code Reviewer

**File:** `agents/reviewer.sr` (converted from `agents/reviewer.yml`)

```bash
poetry run streetrace check agents/reviewer.sr
# Expected: valid (1 model, 1 agent)
```

#### Orchestrator

**File:** `agents/orchestrator.sr` (converted from `agents/orchestrator.yml`)

```bash
poetry run streetrace check agents/orchestrator.sr
# Expected: valid (1 model, 1 agent)
```

### 3.10 Validate All Example Files

To validate all example DSL files at once:

```bash
poetry run streetrace check agents/examples/dsl/ agents/*.sr --verbose
```

**Expected Output:** All 12 files should report as valid (9 examples + 3 production agents).

### 3.11 Generic Flow Definition Tests

**Important**: The DSL supports arbitrary user-defined flows. The following tests verify that flow definitions and calls are not limited to specific names.

#### Test: Custom Flow with LLM Call

This test verifies that users can define any flow that calls an LLM prompt:

**Input:** `custom_flow.sr`

```streetrace
model main = anthropic/claude-sonnet
model analysis = anthropic/haiku

schema SentimentResult:
    sentiment: string
    confidence: float
    explanation: string

prompt sentiment_analysis_prompt using model "analysis" expecting SentimentResult:
    Analyze the sentiment of the following text.
    Return sentiment (positive, negative, neutral), confidence (0-1), and explanation.

    Text: $text

flow analyze_sentiment $text:
    $result = call llm sentiment_analysis_prompt $text
    return $result

on start do
    $input_prompt = initial user prompt
    run main_workflow
end

flow main_workflow:
    $sentiment = run analyze_sentiment $input_prompt
    return $sentiment

agent:
    instruction main_prompt

prompt main_prompt:
    You are a sentiment analysis assistant.
```

**Command:**

```bash
poetry run streetrace check custom_flow.sr
```

**Expected Output:** `valid (2 models, 1 agent, 2 flows)`

#### Test: Multiple Custom Flows with Different Names

This test verifies that multiple flows with different naming patterns work correctly:

**Input:** `multi_flow.sr`

```streetrace
model main = anthropic/claude-sonnet

# Note: These flows demonstrate that any names work - they are NOT built-in features

flow extract_entities $text:
    $entities = call llm entity_extraction_prompt $text
    return $entities

flow validate_format $data:
    $validation = call llm format_validation_prompt $data
    return $validation

flow summarize_findings $entities $validation:
    $summary = call llm summary_prompt $entities $validation
    return $summary

on start do
    $input = initial user prompt
    $entities = run extract_entities $input
    $validated = run validate_format $entities
    $summary = run summarize_findings $entities $validated
end

prompt entity_extraction_prompt:
    Extract entities from the text.
    Text: $text

prompt format_validation_prompt:
    Validate the data format.
    Data: $data

prompt summary_prompt:
    Summarize the findings.
    Entities: $entities
    Validation: $validation

agent:
    instruction summary_prompt
```

**Command:**

```bash
poetry run streetrace check multi_flow.sr
```

**Expected Output:** `valid (1 model, 1 agent, 3 flows, 1 handler)`

**Note:** These tests demonstrate that flow names like `analyze_sentiment`, `extract_entities`, `validate_format`, and `summarize_findings` all work - proving the implementation is generic, not hardcoded to specific patterns.

---

## 4. Edge Case Testing

### 4.1 Syntax Error Cases

#### Test: Missing Colon After Agent Definition

**Input:** `missing_colon.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: """Hello"""

agent
    tools fs
    instruction greeting
```

**Command:**

```bash
poetry run streetrace check missing_colon.sr
```

**Expected Output:** Error indicating unexpected token, expected `:`.

**Expected Exit Code:** `1`

#### Test: Invalid Indentation

**Input:** `bad_indent.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: """Hello"""

agent:
tools fs
    instruction greeting
```

**Command:**

```bash
poetry run streetrace check bad_indent.sr
```

**Expected Output:** Error [E0008] about mismatched indentation.

**Expected Exit Code:** `1`

#### Test: Unterminated `do/end` Block

**Input:** `unterminated_block.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: """Hello"""

on input do
    mask pii

agent:
    instruction greeting
```

**Command:**

```bash
poetry run streetrace check unterminated_block.sr
```

**Expected Output:** Error about unexpected end of input or missing `end`.

**Expected Exit Code:** `1`

---

### 4.2 Semantic Error Cases

#### Test: Undefined Model Reference

**Input:** `undefined_model.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt test_prompt using model "undefined_model": """Hello world"""
```

**Command:**

```bash
poetry run streetrace check undefined_model.sr
```

**Expected Output:**

```
error[E0001]: undefined reference to model 'undefined_model'
  --> undefined_model.sr:5:30
   |
 5 | prompt test_prompt using model "undefined_model": """Hello world"""
   |                              ^^^^^^^^^^^^^^^^
   |
   = help: defined models are: main
```

**Expected Exit Code:** `1`

#### Test: Variable Used Before Definition

**Input:** `undefined_var.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

flow test_flow:
    return $undefined_variable
```

**Command:**

```bash
poetry run streetrace check undefined_var.sr
```

**Expected Output:**

```
error[E0002]: variable '$undefined_variable' used before definition
  --> undefined_var.sr:6:12
   |
 6 |     return $undefined_variable
   |            ^^^^^^^^^^^^^^^^^^^
```

**Expected Exit Code:** `1`

#### Test: Duplicate Definition

**Input:** `duplicate_def.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet
model main = openai/gpt-4

prompt greeting: """Hello"""
```

**Command:**

```bash
poetry run streetrace check duplicate_def.sr
```

**Expected Output:** Error [E0003] about duplicate definition of model 'main'.

**Expected Exit Code:** `1`

#### Test: Circular Import (E0006)

**Input:** Create two files that import each other:

`a.sr`:
```streetrace
streetrace v1

import ./b.sr

model main = anthropic/claude-sonnet
```

`b.sr`:
```streetrace
streetrace v1

import ./a.sr

model compact = anthropic/haiku
```

**Expected Output:** Error [E0006] about circular import detected.

---

### 4.3 Special File Cases

#### Test: Empty File

**Input:** Create an empty `empty.sr` file.

**Command:**

```bash
poetry run streetrace check empty.sr
```

**Expected Behavior:** Either succeeds with 0 definitions or reports a meaningful error about empty file.

#### Test: File with Only Comments

**Input:** `comments_only.sr`

```streetrace
# This file only contains comments
# No actual definitions
```

**Command:**

```bash
poetry run streetrace check comments_only.sr
```

**Expected Behavior:** Should succeed (valid DSL with 0 definitions).

#### Test: Unicode Content in Prompts

**Input:** `unicode.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: """
Hello! 你好! Bonjour! مرحبا!
Emojis work too: 🚀 🎉 ✨
"""

agent:
    instruction greeting
```

**Command:**

```bash
poetry run streetrace check unicode.sr
```

**Expected Behavior:** Should parse and validate successfully.

#### Test: Large File

Create a file with many definitions (50+ agents, flows, prompts).

**Expected Behavior:**

- Compilation should complete in under 500ms
- No memory issues
- All definitions should be counted correctly

---

## 5. Error Code Reference

All error codes follow the format `E0001`-`E0010`. Each error includes:

1. Error level and code
2. Primary message (matter of fact, no periods)
3. Source context with line numbers
4. Caret(s) pointing to the error location
5. Help suggestion (when possible)

### Error Code Table

| Code | Category | Description | Trigger Input Example |
|------|----------|-------------|----------------------|
| E0001 | Reference | Undefined model, tool, agent, or prompt | `using model "nonexistent"` |
| E0002 | Scope | Variable used before definition | `return $undefined` |
| E0003 | Scope | Duplicate definition in same scope | Two `model main = ...` |
| E0004 | Type | Type mismatch in expression | (context dependent) |
| E0005 | Import | Import file not found | `import ./missing.sr` |
| E0006 | Import | Circular import detected | Mutual imports |
| E0007 | Syntax | Invalid token or unexpected end of input | Missing `end` keyword |
| E0008 | Syntax | Mismatched indentation | Inconsistent spaces/tabs |
| E0009 | Semantic | Invalid guardrail action for context | `retry` in wrong handler |
| E0010 | Semantic | Missing required property | Agent without instruction |

### Testing Error Code E0001

**Input:**

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt test using model "fast": """Hello"""
```

**Expected Output Format:**

```
error[E0001]: undefined reference to model 'fast'
  --> test.sr:5:22
   |
 5 | prompt test using model "fast": """Hello"""
   |                      ^^^^
   |
   = help: defined models are: main
```

### Testing Error Code E0002

**Input:**

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

flow test:
    $x = $y
    return $x
```

**Expected Output Format:**

```
error[E0002]: variable '$y' used before definition
  --> test.sr:6:10
   |
 6 |     $x = $y
   |          ^^
```

### Testing Error Code E0007

**Input:**

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt test: """Hello"""

agent:
    tools @#$%
    instruction test
```

**Expected Output Format:**

```
error[E0007]: invalid character
  --> test.sr:8:11
   |
 8 |     tools @#$%
   |           ^
   |
   = help: unexpected character '@'
```

### Testing Error Code E0010

**Input:**

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

agent helper:
    tools fs
```

**Expected Output Format:**

```
error[E0010]: missing required property 'instruction' in agent
  --> test.sr:7:1
   |
 7 | agent helper:
   | ^^^^^
```

---

## 6. Debugging and Diagnosis

### 6.1 Using Verbose Output

The `--verbose` flag provides additional details during validation:

```bash
poetry run streetrace check agents/ --verbose
```

This shows:
- Full file paths being checked
- Statistics for each file (models, agents, flows, handlers)
- More detailed progress information

### 6.2 Interpreting Source Maps

When runtime errors occur, the custom exception hook translates Python stack traces to DSL source locations:

**Example Runtime Error Output:**

```
Traceback (most recent call last):
  File "my_agent.sr", line 23, in flow_my_workflow
    return $result
           ^^^^^^^
NameError: variable '$result' is not defined

Note: This error occurred in generated code. Original location shown above.
```

The file name and line number reference the original `.sr` file, not the generated Python.

### 6.3 Viewing Generated Code for Debugging

To understand how your DSL compiles to Python:

```bash
poetry run streetrace dump-python my_agent.sr | less
```

Key elements to look for:
- Class name (derived from filename)
- `_models` dictionary with model configurations
- `_prompts` dictionary with prompt templates
- Handler methods (`on_input`, `on_output`, etc.)
- Flow methods (`flow_*`)

### 6.4 Common Issues and Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| Indentation errors | E0008 error | Use consistent 4-space indentation |
| Missing `end` | Unexpected token error | Ensure all `do` blocks have `end` |
| Undefined variable | E0002 error | Define variables in `on start` for global scope |
| Model not found | E0001 error | Check model name spelling and definition |
| Import not found | E0005 error | Verify file path is relative to current file |

---

## 7. Performance Testing

### 7.1 Compilation Time Verification

The specification requires compilation under 100ms for typical agents.

**Test Approach:**

```bash
# Test with minimal agent
time poetry run streetrace check agents/examples/dsl/minimal.sr

# Test with complex agent (multiple features)
time poetry run streetrace check agents/examples/dsl/complete.sr
```

**Expected:** Real time should be under 300ms including process startup overhead.

**For accurate measurement**, use the performance test suite:

```bash
poetry run pytest tests/dsl/test_performance.py -v --no-header
```

### 7.2 Performance Thresholds

| Agent Type | Example File | Target Time | Test Threshold |
|------------|--------------|-------------|----------------|
| Minimal (typical) | `agents/examples/dsl/minimal.sr` | < 100ms | < 300ms |
| Complex (multiple features) | `agents/examples/dsl/complete.sr` | < 200ms | < 500ms |
| Cache hit | Any `.sr` file (second run) | < 5ms | < 10ms |

### 7.3 Testing with Large Files

Create an agent with 50+ definitions:

```bash
# Generate a large test file
for i in {1..50}; do
  echo "agent agent_$i:"
  echo "    instruction prompt_$i"
  echo ""
  echo "prompt prompt_$i:"
  echo "    This is prompt number $i."
  echo ""
done > large_agent.sr
```

**Verify compilation time:**

```bash
time poetry run streetrace check large_agent.sr
```

---

## 8. Integration Testing

### 8.1 End-to-End Workflow

Use the complete example to test the full pipeline:

1. **Validate DSL file** with all major features:
   ```bash
   poetry run streetrace check agents/examples/dsl/complete.sr
   ```

2. **Inspect generated Python code**:
   ```bash
   poetry run streetrace dump-python agents/examples/dsl/complete.sr
   ```

3. **Verify Python code compiles**:
   ```bash
   poetry run streetrace dump-python agents/examples/dsl/complete.sr -o /tmp/complete.py
   python -m py_compile /tmp/complete.py
   ```

4. **Load workflow class programmatically**:
   ```python
   from pathlib import Path
   from streetrace.dsl.loader import DslAgentLoader

   loader = DslAgentLoader()
   workflow_class = loader.load(Path('agents/examples/dsl/complete.sr'))
   print(f'Loaded: {workflow_class.__name__}')
   ```

5. **Verify workflow instantiation**:
   ```python
   workflow = workflow_class()
   ctx = workflow.create_context()
   print(f'Models: {workflow_class._models}')
   print(f'Agents: {workflow_class._agents}')
   ```

### 8.2 Automated Test Verification

Run the full DSL test suite:

```bash
poetry run pytest tests/dsl/ -v --no-header
```

This covers:
- Parser tests (`test_parser.py`)
- AST transformation tests (`test_ast.py`)
- Semantic analysis tests (`test_semantic.py`)
- Code generation tests (`test_codegen.py`)
- Source map tests (`test_sourcemap.py`)
- CLI tests (`test_cli.py`)
- Example validation tests (`test_examples.py`)
- Performance tests (`test_performance.py`)

---

## 9. Multi-Agent Pattern Testing

This section covers testing for the multi-agent patterns. See related documentation:
- Design: `docs/tasks/017-dsl-compiler/agentic-patterns.md`: Section 1-11, Accessed 2026-01-21
- Developer: `docs/dev/dsl/agentic-patterns.md`: All Sections, Accessed 2026-01-21
- User: `docs/user/dsl/multi-agent-patterns.md`: All Sections, Accessed 2026-01-21

### 9.1 Coordinator/Dispatcher Pattern Tests

#### Test: Validate `delegate` Keyword Parsing

**Input:** `coordinator.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt billing_instruction:
    Handle billing inquiries.

agent billing_agent:
    instruction billing_instruction
    description "Handles billing"

prompt support_instruction:
    Handle technical support.

agent support_agent:
    instruction support_instruction
    description "Handles support"

prompt coordinator_instruction:
    Route requests: billing issues to billing_agent, tech issues to support_agent.

agent coordinator:
    instruction coordinator_instruction
    description "Routes requests"
    delegate billing_agent, support_agent
```

**Command:**

```bash
poetry run streetrace check coordinator.sr
```

**Expected Output:** `valid (1 model, 3 agents)`

**Expected Exit Code:** `0`

#### Test: Validate `delegate` Reference to Undefined Agent

**Input:** `delegate_undefined.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt coordinator_instruction:
    Route requests.

agent coordinator:
    instruction coordinator_instruction
    delegate nonexistent_agent
```

**Command:**

```bash
poetry run streetrace check delegate_undefined.sr
```

**Expected Output:**

```
error[E0001]: undefined reference to agent 'nonexistent_agent'
  --> delegate_undefined.sr:9:14
   |
 9 |     delegate nonexistent_agent
   |              ^^^^^^^^^^^^^^^^^^
```

**Expected Exit Code:** `1`

#### Test: Coordinator E2E Execution

**Setup:** Create `coordinator_e2e.sr` and use it with Streetrace.

**Manual Test:**

1. Start Streetrace with coordinator agent
2. Send "I have a billing question"
3. Verify LLM routes to billing_agent
4. Send "I can't login"
5. Verify LLM routes to support_agent

### 9.2 Hierarchical Task Decomposition Tests

#### Test: Validate `use` Keyword Parsing

**Input:** `hierarchical.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt searcher_instruction:
    Search for information.

agent searcher:
    instruction searcher_instruction
    description "Searches for info"

prompt summarizer_instruction:
    Summarize content.

agent summarizer:
    instruction summarizer_instruction
    description "Summarizes content"

prompt researcher_instruction:
    Research topics using available tools.

agent researcher:
    instruction researcher_instruction
    description "Researches topics"
    use searcher, summarizer
```

**Command:**

```bash
poetry run streetrace check hierarchical.sr
```

**Expected Output:** `valid (1 model, 3 agents)`

**Expected Exit Code:** `0`

#### Test: Validate `use` Reference to Undefined Agent

**Input:** `use_undefined.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt researcher_instruction:
    Research topics.

agent researcher:
    instruction researcher_instruction
    use nonexistent_agent
```

**Command:**

```bash
poetry run streetrace check use_undefined.sr
```

**Expected Output:**

```
error[E0001]: undefined reference to agent 'nonexistent_agent'
  --> use_undefined.sr:8:9
   |
 8 |     use nonexistent_agent
   |         ^^^^^^^^^^^^^^^^^^
```

**Expected Exit Code:** `1`

#### Test: Circular `use` Detection

**Input:** `circular_use.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt agent_a_instruction:
    Agent A.

agent agent_a:
    instruction agent_a_instruction
    use agent_b

prompt agent_b_instruction:
    Agent B.

agent agent_b:
    instruction agent_b_instruction
    use agent_a
```

**Command:**

```bash
poetry run streetrace check circular_use.sr
```

**Expected Output:**

```
error[E0011]: circular agent reference detected: agent_a -> agent_b -> agent_a
  --> circular_use.sr:6:1
```

**Expected Exit Code:** `1`

#### Test: Warning for Both delegate and use (W0002)

**Input:** `both_delegate_use.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt helper_instruction:
    Helper agent.

agent helper:
    instruction helper_instruction
    description "Helper"

prompt specialist_instruction:
    Specialist agent.

agent specialist:
    instruction specialist_instruction
    description "Specialist"

prompt mixed_instruction:
    Mixed pattern agent.

agent mixed:
    instruction mixed_instruction
    delegate helper
    use specialist
```

**Command:**

```bash
poetry run streetrace check both_delegate_use.sr
```

**Expected Output:**

```
warning[W0002]: agent 'mixed' has both delegate and use - this is unusual
  --> both_delegate_use.sr:19:1
```

**Expected Exit Code:** `0` (warnings do not cause failure)

**Note:** This warning indicates an unusual design pattern. Consider reorganizing into separate agents.

#### Test: Hierarchical E2E Execution

**Setup:** Create `hierarchical_e2e.sr`.

**Manual Test:**

1. Start Streetrace with researcher agent
2. Send "Research the history of AI"
3. Verify researcher invokes searcher as tool
4. Verify researcher invokes summarizer as tool
5. Verify results are aggregated in response

### 9.3 Iterative Refinement Pattern Tests

#### Test: Validate `loop` Block Parsing

**Input:** `loop.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt improver_instruction:
    Improve the text.

agent improver:
    instruction improver_instruction

prompt checker_instruction:
    Check quality. Return done=true when quality is good.

agent checker:
    instruction checker_instruction

flow iterative_refinement $text:
    $current = $text

    loop max 5 do
        $quality = run agent checker $current
        if $quality.done:
            return $current
        $current = run agent improver $current $quality.feedback
    end

    return $current

on start do
    $input_prompt = initial user prompt
    $result = run iterative_refinement $input_prompt
end
```

**Command:**

```bash
poetry run streetrace check loop.sr
```

**Expected Output:** `valid (1 model, 2 agents, 1 flow, 1 handler)`

**Expected Exit Code:** `0`

#### Test: Loop Without Max Iterations

**Input:** `loop_infinite.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt worker_instruction:
    Process data.

agent worker:
    instruction worker_instruction

flow continuous_process $input:
    $data = $input

    loop do
        $data = run agent worker $data
        if $data.complete:
            return $data
    end

on start do
    $input_prompt = initial user prompt
    $result = run continuous_process $input_prompt
end
```

**Command:**

```bash
poetry run streetrace check loop_infinite.sr
```

**Expected Output:** `valid (1 model, 1 agent, 1 flow, 1 handler)`

**Expected Exit Code:** `0`

**Note:** Infinite loops without exit conditions should generate a warning but not an error.

#### Test: Iterative Refinement E2E Execution

**Setup:** Create `refinement_e2e.sr` with quality-based iteration.

**Manual Test:**

1. Start Streetrace with refinement flow
2. Send "Write a summary of quantum computing"
3. Verify loop executes multiple times
4. Verify quality improves with each iteration
5. Verify loop exits when quality threshold met or max iterations reached

### 9.4 Combined Pattern Tests

#### Test: Coordinator with Hierarchical Agents

**Input:** `combined_patterns.sr`

```streetrace
model main = anthropic/claude-sonnet

# Low-level agents
prompt fetcher_instruction:
    Fetch data.

agent fetcher:
    instruction fetcher_instruction

prompt validator_instruction:
    Validate data.

agent validator:
    instruction validator_instruction

# Mid-level agent using low-level agents
prompt processor_instruction:
    Process data using available tools.

agent processor:
    instruction processor_instruction
    use fetcher, validator

# Specialized agents using processor
prompt report_agent_instruction:
    Generate reports.

agent report_agent:
    instruction report_agent_instruction
    use processor

prompt analysis_agent_instruction:
    Analyze data.

agent analysis_agent:
    instruction analysis_agent_instruction
    use processor

# Coordinator routing to specialized agents
prompt coordinator_instruction:
    Route: reports to report_agent, analysis to analysis_agent.

agent coordinator:
    instruction coordinator_instruction
    delegate report_agent, analysis_agent

on start do
    $input_prompt = initial user prompt
    $result = run agent coordinator $input_prompt
end
```

**Command:**

```bash
poetry run streetrace check combined_patterns.sr
```

**Expected Output:** `valid (1 model, 6 agents, 1 handler)`

**Expected Exit Code:** `0`

### 9.5 Code Generation Tests

#### Test: Verify `delegate` Generates `sub_agents`

**Command:**

```bash
poetry run streetrace dump-python coordinator.sr
```

**Expected Output Contains:**

```python
coordinator = LlmAgent(
    name="coordinator",
    instruction="...",
    sub_agents=[billing_agent, support_agent]
)
```

#### Test: Verify `use` Generates `AgentTool`

**Command:**

```bash
poetry run streetrace dump-python hierarchical.sr
```

**Expected Output Contains:**

```python
from google.adk.tools import agent_tool

researcher = LlmAgent(
    name="researcher",
    instruction="...",
    tools=[
        agent_tool.AgentTool(agent=searcher),
        agent_tool.AgentTool(agent=summarizer)
    ]
)
```

#### Test: Verify `loop` Generates `LoopAgent`

**Command:**

```bash
poetry run streetrace dump-python loop.sr
```

**Expected Output Contains:**

```python
from google.adk.agents import LoopAgent

iterative_refinement_loop = LoopAgent(
    name="iterative_refinement_loop",
    max_iterations=5,
    sub_agents=[...]
)
```

### 9.6 Example Files for Multi-Agent Patterns

The following example files exist in `agents/examples/dsl/`:

| File | Pattern | Features Demonstrated |
|------|---------|----------------------|
| `agents/examples/dsl/coordinator.sr` | Coordinator/Dispatcher | `delegate` keyword, LLM routing |
| `agents/examples/dsl/hierarchical.sr` | Hierarchical | `use` keyword, agent-as-tool |
| `agents/examples/dsl/iterative.sr` | Iterative Refinement | `loop` block, quality checking |
| `agents/examples/dsl/combined.sr` | Combined | Multiple patterns together |

**Validate all example files:**

```bash
poetry run streetrace check agents/examples/dsl/coordinator.sr
# Expected: valid (2 models, 3 agents)

poetry run streetrace check agents/examples/dsl/hierarchical.sr
# Expected: valid (2 models, 4 agents)

poetry run streetrace check agents/examples/dsl/iterative.sr
# Expected: valid (2 models, 1 agent, 1 flow)

poetry run streetrace check agents/examples/dsl/combined.sr
# Expected: valid (2 models, 7 agents, 1 flow)
```

### 9.7 Automated Test Coverage

Add the following test modules to `tests/dsl/`:

| Module | Tests |
|--------|-------|
| `test_delegate.py` | Parser, AST, semantic analysis, codegen for `delegate` |
| `test_use.py` | Parser, AST, semantic analysis, codegen for `use` |
| `test_loop.py` | Parser, AST, semantic analysis, codegen for `loop` |
| `test_patterns.py` | Integration tests for combined patterns |

**Run pattern-specific tests:**

```bash
poetry run pytest tests/dsl/test_delegate.py tests/dsl/test_use.py tests/dsl/test_loop.py -v --no-header
```

### 9.8 ADK Integration Testing

This section covers testing the ADK integration layer that creates LlmAgent instances from
DSL agent definitions.

**Related Documentation**:
- Design: `docs/tasks/017-dsl/adk-integration/task.md`: Section 1-4, Accessed 2026-01-21
- Developer: `docs/dev/dsl/agentic-patterns.md`: Runtime Integration, API Reference sections, Accessed 2026-01-21

#### Test: Coordinator Pattern Creates Sub-Agents

This test verifies that agents with `delegate` keyword produce `LlmAgent` instances with
populated `sub_agents` list.

**Input:** `coordinator_integration.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt billing_prompt:
    Handle billing inquiries.

agent billing:
    instruction billing_prompt
    description "Billing specialist"

prompt support_prompt:
    Handle support requests.

agent support:
    instruction support_prompt
    description "Support specialist"

prompt coordinator_prompt:
    Route requests appropriately.

agent:
    instruction coordinator_prompt
    delegate billing, support
    description "Request coordinator"
```

**Test Procedure:**

```python
# Load the agent
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from streetrace.agents.dsl_agent_loader import DslAgentLoader

loader = DslAgentLoader()
agent_def = loader.load_from_path(Path("coordinator_integration.sr"))

# Mock dependencies
model_factory = MagicMock()
model_factory.get_current_model.return_value = "mock-model"
tool_provider = MagicMock()
tool_provider.get_tools.return_value = []
system_context = MagicMock()

# Create the ADK agent
import asyncio
adk_agent = asyncio.run(agent_def.create_agent(
    model_factory, tool_provider, system_context
))

# Verify sub_agents
assert hasattr(adk_agent, "sub_agents")
assert len(adk_agent.sub_agents) == 2
sub_agent_names = [sa.name for sa in adk_agent.sub_agents]
assert "billing" in sub_agent_names
assert "support" in sub_agent_names
```

**Expected Output:** Test passes with 2 sub-agents named "billing" and "support".

#### Test: Hierarchical Pattern Creates AgentTools

This test verifies that agents with `use` keyword produce `LlmAgent` instances with
`AgentTool` wrappers in the tools list.

**Input:** `hierarchical_integration.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt helper_prompt:
    Provide assistance.

agent helper:
    instruction helper_prompt
    description "Helper agent"

prompt parent_prompt:
    Orchestrate helpers.

agent:
    instruction parent_prompt
    use helper
    description "Parent orchestrator"
```

**Test Procedure:**

```python
# ... same setup as above ...

adk_agent = asyncio.run(agent_def.create_agent(
    model_factory, tool_provider, system_context
))

# Verify tools include AgentTool
from google.adk.tools.agent_tool import AgentTool
agent_tools = [t for t in adk_agent.tools if isinstance(t, AgentTool)]
assert len(agent_tools) == 1
assert agent_tools[0].agent.name == "helper"
```

**Expected Output:** Test passes with 1 AgentTool wrapping "helper" agent.

#### Test: Recursive Pattern Support

This test verifies that nested patterns (sub-agents with their own sub-agents/tools)
are resolved correctly.

**Input:** `recursive_integration.sr`

```streetrace
model main = anthropic/claude-sonnet

prompt leaf_prompt:
    Leaf agent.

agent leaf:
    instruction leaf_prompt
    description "Leaf agent"

prompt middle_prompt:
    Middle agent uses leaf.

agent middle:
    instruction middle_prompt
    use leaf
    description "Middle agent"

prompt root_prompt:
    Root delegates to middle.

agent:
    instruction root_prompt
    delegate middle
    description "Root coordinator"
```

**Test Procedure:**

```python
# ... same setup as above ...

adk_agent = asyncio.run(agent_def.create_agent(
    model_factory, tool_provider, system_context
))

# Verify hierarchy
assert len(adk_agent.sub_agents) == 1
middle_agent = adk_agent.sub_agents[0]
assert middle_agent.name == "middle"

# Verify middle has leaf as AgentTool
from google.adk.tools.agent_tool import AgentTool
middle_tools = [t for t in middle_agent.tools if isinstance(t, AgentTool)]
assert len(middle_tools) == 1
assert middle_tools[0].agent.name == "leaf"
```

**Expected Output:** Test passes with correctly nested hierarchy.

#### Test: Agent Cleanup

This test verifies that `close()` properly cleans up all nested agents and tools.

**Test Procedure:**

```python
# Create agent hierarchy
adk_agent = asyncio.run(agent_def.create_agent(
    model_factory, tool_provider, system_context
))

# Close the agent
asyncio.run(agent_def.close(adk_agent))

# Verify workflow instance cleared
assert agent_def._workflow_instance is None
```

**Expected Output:** Test passes with no errors during cleanup.

#### Test: Description Field Propagation

This test verifies that agent descriptions are correctly passed to LlmAgent.

**Test Procedure:**

```python
adk_agent = asyncio.run(agent_def.create_agent(
    model_factory, tool_provider, system_context
))

# Check description on root agent
assert adk_agent.description == "Root coordinator"

# Check description on sub-agent
assert adk_agent.sub_agents[0].description == "Middle agent"
```

**Expected Output:** Test passes with correct descriptions at each level.

#### Running ADK Integration Tests

```bash
# Run existing agent loader tests
poetry run pytest tests/dsl/test_dsl_agent_loader.py -v --no-header

# Run agentic pattern tests
poetry run pytest tests/dsl/test_agentic_patterns.py -v --no-header
```

---

## 10. Known Compiler Issues

This section documents known issues in the DSL compiler that testers should be aware of.

### 10.1 Open Issues

#### Tool Passing Inconsistency in Flow Context

**Status**: Open

When flows execute `ctx.run_agent()`, the dynamically created agent does not receive tools from
the agent definition. Tools are only passed correctly in the main agent loader path.

**Impact**: Agents invoked via flows cannot use their DSL-defined tools.

**Test**: Create a flow that invokes an agent with tools and verify the tools are accessible.

**Tracking**: See `docs/tasks/017-dsl/tech_debt.md` for details.

#### Flow Event Streaming

**Status**: Open

Flow execution returns only the final response from agent runs. Intermediate ADK events are
consumed but not yielded to callers.

**Impact**: No support for progress monitoring or event-driven streaming in flows.

**Tracking**: See `docs/tasks/017-dsl/tech_debt.md` for details.

#### SequentialAgent Pattern Not Implemented

**Status**: Open

The design doc specifies that consecutive `run agent` statements should use ADK's `SequentialAgent`
for better coordination. Currently each agent is run independently.

**Tracking**: See `docs/tasks/017-dsl/tech_debt.md` for details.

### 10.2 Issue Tracking

For detailed root cause analysis and fix requirements, see:
- Developer documentation: `docs/dev/dsl/architecture.md` (Known Limitations section)
- Tech debt tracking: `docs/tasks/017-dsl/tech_debt.md`

### 10.3 Resolved Issues

The following issues from earlier versions have been fixed:

| Issue | Description | Status |
|-------|-------------|--------|
| Comma-Separated Name Lists | `tools fs, cli` syntax now works correctly | ✅ Fixed |
| Flow Parameter Variable Scoping | Flow parameters (`$input`) are now properly scoped | ✅ Fixed |
| Policy Property Transformation | Complex policy blocks parse correctly | ✅ Fixed |
| Runtime Integration | DSL agents work with `streetrace --agent` flag | ✅ Fixed |
| Flow Call Validation | Flow calls (`run my_flow`) validate against flows | ✅ Fixed |
| Tool Loading to LlmAgent | Tools passed to LlmAgent constructor in loader | ✅ Fixed |
| Instruction Resolution | Direct field access instead of keyword matching | ✅ Fixed |
| Model Resolution Priority | Follows prompt model → main → CLI priority | ✅ Fixed |
| Variable Definition Order | `$` prefix stripped when defining scope variables | ✅ Fixed |

---

## References

- `017-dsl-compiler.md`: Design Document, Section 6 (CLI Interface), Accessed 2026-01-20
- `017-dsl-grammar.md`: Grammar Specification, Section 3 (Complete Grammar), Accessed 2026-01-20
- `017-dsl-integration.md`: Integration Design, Section 12 (Implementation Requirements), Accessed 2026-01-20
- `017-dsl-examples.md`: DSL Examples, All Sections, Accessed 2026-01-20
- `docs/tasks/017-dsl/adk-integration/task.md`: ADK Integration Task, All Sections, Accessed 2026-01-21
- `docs/dev/dsl/agentic-patterns.md`: Developer Guide, Runtime Integration, Accessed 2026-01-21
- `src/streetrace/agents/dsl_agent_loader.py`: Implementation Source, Lines 341-843, Accessed 2026-01-21

---

## See Also

- [DSL Architecture](../../dev/dsl/architecture.md) - Compiler pipeline and design
- [DSL API Reference](../../dev/dsl/api-reference.md) - Complete API documentation
- [DSL Grammar Specification](../../dev/dsl/grammar.md) - Grammar syntax and patterns
- [User Guide: DSL Quick Start](../../user/dsl/getting-started.md) - Getting started guide
- [User Guide: Troubleshooting](../../user/dsl/troubleshooting.md) - Common errors and solutions
- [CLI Reference](../../user/dsl/cli-reference.md) - Command-line options
