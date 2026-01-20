# CLI Reference

Streetrace provides command-line tools for validating and debugging `.sr` files. This
reference documents the available commands and their options.

## Commands Overview

| Command | Description |
|---------|-------------|
| `streetrace check` | Validate DSL files for syntax and semantic errors |
| `streetrace dump-python` | Generate Python code from DSL for debugging |

## streetrace check

Validate Streetrace DSL files for syntax and semantic correctness.

### Usage

```bash
streetrace check <path> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `path` | DSL file (`.sr`) or directory to validate |

### Options

| Option | Description |
|--------|-------------|
| `-v`, `--verbose` | Enable verbose output (shows file paths) |
| `--format {text,json}` | Output format (default: `text`) |
| `--strict` | Treat warnings as errors |

### Examples

**Validate a single file:**

```bash
streetrace check my_agent.sr
```

Output on success:

```
valid (1 model, 1 agent, 1 prompt)
```

**Validate with verbose output:**

```bash
streetrace check my_agent.sr -v
```

Output:

```
my_agent.sr: valid (1 model, 1 agent, 1 prompt)
```

**Validate all files in a directory:**

```bash
streetrace check ./agents/
```

Recursively validates all `.sr` files.

**JSON output for CI/CD:**

```bash
streetrace check my_agent.sr --format json
```

Output:

```json
{
  "version": "1.0",
  "file": "my_agent.sr",
  "valid": true,
  "errors": [],
  "warnings": [],
  "stats": {
    "models": 1,
    "agents": 1,
    "flows": 0,
    "handlers": 2
  }
}
```

**Strict mode (warnings become errors):**

```bash
streetrace check my_agent.sr --strict
```

### Exit Codes

| Code | Description |
|------|-------------|
| `0` | Validation passed |
| `1` | Validation errors found |
| `2` | File not found or cannot be read |

### Error Output

Errors are displayed in rustc-style format:

```
error[E0001]: undefined reference to model 'fast'
  --> my_agent.sr:15:18
     |
  14 |
  15 |     using model "fast"
  16 |
     |                  ^^^^
     |
     = help: defined models are: main, compact

Found 1 error in my_agent.sr
```

## streetrace dump-python

Generate Python code from a DSL file. Useful for debugging and understanding what the
compiler produces.

### Usage

```bash
streetrace dump-python <path> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `path` | DSL file (`.sr`) to convert |

### Options

| Option | Description |
|--------|-------------|
| `--no-comments` | Exclude source location comments from output |
| `-o`, `--output <file>` | Write to file instead of stdout |

### Examples

**View generated Python:**

```bash
streetrace dump-python my_agent.sr
```

Output:

```python
# my_agent.sr:1
_models["main"] = "anthropic/claude-sonnet"

# my_agent.sr:3
class MyAgentWorkflow(DslAgentWorkflow):
    # my_agent.sr:4
    _tools = ["github", "streetrace.fs"]

    # my_agent.sr:5
    async def on_start(self, ctx: WorkflowContext) -> None:
        ...
```

**Clean output (no source comments):**

```bash
streetrace dump-python my_agent.sr --no-comments
```

Output:

```python
_models["main"] = "anthropic/claude-sonnet"

class MyAgentWorkflow(DslAgentWorkflow):
    _tools = ["github", "streetrace.fs"]

    async def on_start(self, ctx: WorkflowContext) -> None:
        ...
```

**Save to file:**

```bash
streetrace dump-python my_agent.sr -o generated.py
```

Output:

```
wrote: generated.py
```

### Exit Codes

| Code | Description |
|------|-------------|
| `0` | Code generated successfully |
| `2` | File not found or parse error |

## Using in CI/CD

### GitHub Actions

```yaml
name: Validate DSL
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Streetrace
        run: pip install streetrace

      - name: Validate DSL files
        run: streetrace check ./agents/ --strict --format json
```

### Pre-commit Hook

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: streetrace-check
        name: Validate Streetrace DSL
        entry: streetrace check
        language: system
        files: '\.sr$'
        pass_filenames: true
```

### Makefile Integration

```makefile
.PHONY: check-dsl
check-dsl:
	streetrace check ./agents/ --strict

.PHONY: lint
lint: check-dsl
	ruff check src tests
```

## Error Codes Reference

| Code | Category | Description |
|------|----------|-------------|
| E0001 | Reference | Undefined reference to model, tool, agent, or prompt |
| E0002 | Reference | Variable used before definition |
| E0003 | Reference | Duplicate definition |
| E0004 | Type | Type mismatch in expression |
| E0005 | Import | Import file not found |
| E0006 | Import | Circular import detected |
| E0007 | Syntax | Invalid token or unexpected end of input |
| E0008 | Syntax | Mismatched indentation |
| E0009 | Semantic | Invalid guardrail action for context |
| E0010 | Semantic | Missing required property |

See [Troubleshooting](troubleshooting.md) for solutions to common errors.

## Tips

### Debugging Parse Errors

If you get syntax errors, use `dump-python` to see where parsing stops:

```bash
streetrace dump-python my_agent.sr 2>&1 | head -20
```

### Validating Before Deployment

Always validate in strict mode before deploying:

```bash
streetrace check ./agents/ --strict || exit 1
```

### Getting JSON for Tools

Use JSON output for programmatic access:

```bash
streetrace check my_agent.sr --format json | jq '.errors'
```

## See Also

- [Getting Started](getting-started.md) - Introduction to Streetrace DSL
- [Syntax Reference](syntax-reference.md) - Complete language reference
- [Troubleshooting](troubleshooting.md) - Error resolution
