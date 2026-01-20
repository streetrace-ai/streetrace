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

Create test `.sr` files in a temporary directory or use the examples from the design documentation:

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

**Input:** Create file `minimal_agent.sr`:

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool github = mcp "https://api.github.com/mcp/"

prompt my_prompt: """You are a helpful assistant."""

agent:
    tools github
    instruction my_prompt
```

**Command:**

```bash
poetry run streetrace check minimal_agent.sr
```

**Expected Output:**

```
valid (1 model, 1 agent)
```

**Expected Exit Code:** `0`

#### Test Scenario: Validate with Verbose Output

**Command:**

```bash
poetry run streetrace check minimal_agent.sr --verbose
```

**Expected Output:**

```
minimal_agent.sr: valid (1 model, 1 agent)
```

#### Test Scenario: Validate a Directory

**Setup:** Create multiple `.sr` files in `/tmp/dsl-test/agents/`

**Command:**

```bash
poetry run streetrace check /tmp/dsl-test/agents/
```

**Expected Output:** Validation results for each `.sr` file found.

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

The following examples are derived from `017-dsl-examples.md`. Each should be validated using `streetrace check`.

### 3.1 Minimal Agent

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool github = mcp "https://api.github.com/mcp/" with auth bearer ${env:GITHUB_PAT}

prompt my_prompt: """You are a helpful assistant..."""

agent:
    tools github, streetrace.fs
    instruction my_prompt
```

### 3.2 Agent with Event Handlers

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt greeting: """You are a helpful assistant."""

on input do
    mask pii
    block if jailbreak
end

on output do
    warn if sensitive
end

agent:
    tools fs
    instruction greeting
```

### 3.3 Agent with Flow

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt fetch_prompt: """Fetch invoices from the system."""

prompt process_prompt: """Process the invoice data."""

agent fetch_invoices:
    instruction fetch_prompt

agent process_invoice:
    instruction process_prompt

flow my_workflow:
    $invoices = run agent fetch_invoices
    for $invoice in $invoices do
        $result = run agent process_invoice $invoice
    end
    return $result
```

### 3.4 Agent with Parallel Execution

```streetrace
streetrace v1

model main = anthropic/claude-opus

tool web = mcp "https://search.api/mcp/"
tool docs = builtin streetrace.docs

prompt web_prompt: """Search the web."""

prompt doc_prompt: """Search docs."""

prompt combine_prompt: """Combine results."""

agent web_search:
    tools web
    instruction web_prompt

agent doc_search:
    tools docs
    instruction doc_prompt

agent synthesize:
    instruction combine_prompt

flow research:
    parallel do
        $web_results = run agent web_search
        $doc_results = run agent doc_search
    end
    $combined = run agent synthesize
    return $combined
```

### 3.5 Agent with Schema (Structured Output)

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

schema ReviewResult:
    approved: bool
    comments: list[string]
    severity: string

prompt review_prompt expecting ReviewResult: """
You are an expert code reviewer. Analyze the pull request
for bugs, security issues, and code quality.
"""

agent code_reviewer:
    instruction review_prompt
```

### 3.6 Agent with Policies

```streetrace
streetrace v1

model main = anthropic/claude-sonnet
model compact = anthropic/claude-opus

retry default = 3 times, exponential backoff
timeout default = 2 minutes

policy compaction:
    trigger: token_usage > 0.8
    strategy: summarize_with_goal
    preserve: [$goal, last 3 messages, tool results]
    use model: "compact"

prompt greeting: """Hello, I am your assistant."""

agent:
    instruction greeting
    retry default
    timeout default
```

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
time poetry run streetrace check minimal_agent.sr
```

**Expected:** Real time should be under 300ms including process startup overhead.

**For accurate measurement**, use the performance test suite:

```bash
poetry run pytest tests/dsl/test_performance.py -v --no-header
```

### 7.2 Performance Thresholds

| Agent Type | Target Time | Test Threshold |
|------------|-------------|----------------|
| Minimal (typical) | < 100ms | < 300ms |
| Complex (multiple features) | < 200ms | < 500ms |
| Cache hit | < 5ms | < 10ms |

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

1. **Create DSL file** with all major features
2. **Validate** with `streetrace check`
3. **Inspect** with `streetrace dump-python`
4. **Execute** with `streetrace run`
5. **Verify** runtime behavior matches specification

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

## References

- `017-dsl-compiler.md`: Design Document, Section 6 (CLI Interface), Accessed 2026-01-20
- `017-dsl-grammar.md`: Grammar Specification, Section 3 (Complete Grammar), Accessed 2026-01-20
- `017-dsl-integration.md`: Integration Design, Section 12 (Implementation Requirements), Accessed 2026-01-20
- `017-dsl-examples.md`: DSL Examples, All Sections, Accessed 2026-01-20

---

## See Also

- [DSL Grammar Specification](../dev/dsl/grammar.md) (if available)
- [User Guide: DSL Quick Start](../user/dsl/getting-started.md) (if available)
- [RFC-017: Streetrace Agent Definition DSL](https://github.com/streetrace-ai/rfc/design/017-streetrace-dsl.md)
