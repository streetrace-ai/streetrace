# Task Definition: DSL Compiler Implementation

## Feature Information

| Field | Value |
|-------|-------|
| **Feature ID** | 017-dsl-compiler |
| **Feature Name** | DSL Compiler for Streetrace Agent Definition Language |
| **Source Design Doc** | [017-dsl-compiler.md](/home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-compiler.md) |
| **Related Documents** | [017-dsl-grammar.md](/home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-grammar.md), [017-dsl-integration.md](/home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-integration.md), [017-dsl-examples.md](/home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-examples.md) |

## Summary

Implement the DSL compiler for Streetrace's Domain-Specific Language. The compiler transforms `.sr` files through a complete pipeline: lexing, parsing with Lark, AST transformation, semantic analysis, Python code generation, and compilation to bytecode. The implementation includes CLI commands for validation and debugging, source map support for error translation, and integration with the existing Streetrace runtime.

## Implementation Requirements

### Core Compiler Pipeline

1. **Parser Module** (`streetrace/dsl/grammar/`)
   - `streetrace.lark` - Complete Lark EBNF grammar file
   - `StreetraceIndenter` - Custom indenter for Python-style indentation
   - `ParserFactory` - Creates configured Lark parser instances (LALR/Earley modes)

2. **AST Module** (`streetrace/dsl/ast/`)
   - AST node dataclasses with position metadata (`lark.tree.Meta`)
   - `AstTransformer` using `lark.ast_utils.create_transformer`
   - Support for all DSL constructs: models, schemas, tools, agents, prompts, flows, handlers, policies

3. **Semantic Analyzer** (`streetrace/dsl/semantic/`)
   - Reference validation (models, tools, prompts, agents)
   - Variable scoping (global from `on start`, local in flows/handlers)
   - Type checking for expressions
   - Import resolution
   - Cycle detection in agent/flow references

4. **Code Generator** (`streetrace/dsl/codegen/`)
   - `CodeGenVisitor` - AST visitor producing Python code
   - `CodeEmitter` - Handles indentation and line tracking
   - Generation patterns for all DSL constructs
   - Source map entries for each generated line

5. **Source Map System** (`streetrace/dsl/sourcemap/`)
   - `SourceMapping` dataclass
   - `SourceMapRegistry` - Bidirectional mappings
   - Custom exception hook for stack trace translation

6. **Error Reporter** (`streetrace/dsl/errors/`)
   - Contextual error messages (rustc-style)
   - Error code registry (E0001-E0010)
   - JSON output format for tooling

7. **Cache** (`streetrace/dsl/cache.py`)
   - In-memory bytecode cache keyed by content hash
   - LRU eviction policy

8. **Main Compiler** (`streetrace/dsl/compiler.py`)
   - `compile_dsl()` - Main compilation function
   - `validate_dsl()` - Validation without execution

### CLI Commands

1. **`streetrace check`**
   - Validate `.sr` files without execution
   - Support directory validation
   - Exit codes: 0 (valid), 1 (validation errors), 2 (file errors)
   - `--verbose`, `--format json`, `--strict` options

2. **`streetrace dump-python`**
   - Output generated Python code
   - `--no-comments`, `--output FILE` options

### Runtime Integration

1. **DslAgentLoader** (`streetrace/dsl/loader.py`)
   - Integration with AgentManager
   - Loads `.sr` files and produces workflow instances

2. **Runtime Base Classes** (`streetrace/dsl/runtime/`)
   - `DslAgentWorkflow` - Base class for generated workflows
   - `WorkflowContext` - Runtime context with `$variables`

## Success Criteria

1. **Parser Foundation**
   - All examples from 017-dsl-examples.md parse successfully
   - Parse errors include line/column information

2. **AST and Semantic Analysis**
   - All examples produce valid AST
   - Semantic errors detected for undefined references
   - Variable scoping rules enforced

3. **Code Generator**
   - Generated code passes `py_compile`
   - All examples execute correctly
   - Source maps accurately track line numbers

4. **CLI and Diagnostics**
   - Exit codes match specification
   - Error messages follow style guide
   - JSON output parses correctly

5. **Integration**
   - DSL agents load via `streetrace run my_agent.sr`
   - Stack traces show `.sr` line numbers
   - Performance: < 100ms compilation for typical agents

## Dependencies on Existing Code

- `streetrace/agents/agent_manager.py` - Agent discovery and creation
- `streetrace/workflow/supervisor.py` - Workflow orchestration
- `streetrace/commands/command_executor.py` - CLI command registration
- `streetrace/log.py` - Logging utilities

## External Dependencies

- `lark` - Parser library (add to pyproject.toml)

## Test Coverage Requirements

| Category | Target Coverage |
|----------|-----------------|
| Grammar Tests | 95%+ |
| AST Transformer Tests | 90%+ |
| Semantic Analysis Tests | 90%+ |
| Code Generator Tests | 90%+ |
| Source Map Tests | 95%+ |
| CLI Tests | 80%+ |
| Integration Tests | All examples |
| Error Message Tests | All error codes |
