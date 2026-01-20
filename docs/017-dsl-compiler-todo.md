# Implementation Plan: DSL Compiler

## Phase 1: Parser Foundation

- [x] Add `lark` dependency to pyproject.toml
- [x] Create `src/streetrace/dsl/` package structure
- [x] Create `src/streetrace/dsl/__init__.py` with public API exports
- [x] Create `src/streetrace/dsl/grammar/__init__.py`
- [x] Create `src/streetrace/dsl/grammar/streetrace.lark` - Complete Lark EBNF grammar
- [x] Create `src/streetrace/dsl/grammar/indenter.py` - StreetraceIndenter class
- [x] Create `src/streetrace/dsl/grammar/parser.py` - ParserFactory with LALR/Earley modes
- [x] Create `tests/dsl/test_parser.py` - Parser tests for all grammar constructs
- [x] Verify all examples from 017-dsl-examples.md parse successfully

## Phase 2: AST and Semantic Analysis

- [x] Create `src/streetrace/dsl/ast/__init__.py`
- [x] Create `src/streetrace/dsl/ast/nodes.py` - AST node dataclasses with Meta
- [x] Create `src/streetrace/dsl/ast/transformer.py` - Lark tree to AST transformer
- [x] Create `src/streetrace/dsl/semantic/__init__.py`
- [x] Create `src/streetrace/dsl/semantic/scope.py` - Scope tracking classes
- [x] Create `src/streetrace/dsl/semantic/types.py` - Type definitions and utilities
- [x] Create `src/streetrace/dsl/semantic/analyzer.py` - Semantic analysis pass
- [x] Create `tests/dsl/test_ast.py` - AST transformation tests
- [x] Create `tests/dsl/test_semantic.py` - Semantic analysis tests

## Phase 3: Code Generator

- [x] Create `src/streetrace/dsl/codegen/__init__.py`
- [x] Create `src/streetrace/dsl/codegen/emitter.py` - CodeEmitter with line tracking
- [x] Create `src/streetrace/dsl/codegen/templates.py` - Python code templates
- [x] Create `src/streetrace/dsl/codegen/visitors/__init__.py`
- [x] Create `src/streetrace/dsl/codegen/visitors/workflow.py` - Workflow class generation
- [x] Create `src/streetrace/dsl/codegen/visitors/handlers.py` - Event handler generation
- [x] Create `src/streetrace/dsl/codegen/visitors/flows.py` - Flow method generation
- [x] Create `src/streetrace/dsl/codegen/generator.py` - Main CodeGenVisitor
- [x] Create `src/streetrace/dsl/sourcemap/__init__.py`
- [x] Create `src/streetrace/dsl/sourcemap/registry.py` - SourceMapRegistry
- [x] Create `src/streetrace/dsl/sourcemap/excepthook.py` - Custom exception hook
- [x] Create `tests/dsl/test_codegen.py` - Code generation tests
- [x] Create `tests/dsl/test_sourcemap.py` - Source map tests

## Phase 4: CLI and Diagnostics

- [x] Create `src/streetrace/dsl/errors/__init__.py`
- [x] Create `src/streetrace/dsl/errors/codes.py` - Error code definitions (E0001-E0010)
- [x] Create `src/streetrace/dsl/errors/reporter.py` - Error formatting (rustc-style)
- [x] Create `src/streetrace/dsl/errors/diagnostics.py` - Diagnostic message building
- [x] Create `src/streetrace/dsl/cache.py` - BytecodeCache with LRU eviction
- [x] Create `src/streetrace/dsl/compiler.py` - compile_dsl() and validate_dsl()
- [x] Create `src/streetrace/dsl/cli.py` - CLI commands (check, dump-python)
- [x] Create `tests/dsl/test_errors.py` - Error message tests
- [x] Create `tests/dsl/test_cli.py` - CLI command tests

## Phase 5: Integration and Polish

- [x] Create `src/streetrace/dsl/loader.py` - DslAgentLoader for AgentManager
- [x] Create `src/streetrace/dsl/runtime/__init__.py`
- [x] Create `src/streetrace/dsl/runtime/workflow.py` - DslAgentWorkflow base class
- [x] Create `src/streetrace/dsl/runtime/context.py` - WorkflowContext
- [x] Update `src/streetrace/dsl/__init__.py` with complete public API
- [x] Create `tests/dsl/test_loader.py` - Tests for DslAgentLoader
- [x] Create `tests/dsl/test_integration.py` - Full compile-to-execute tests
- [x] Create `tests/dsl/test_examples.py` - Tests for all examples from design docs
- [x] Create `tests/dsl/test_performance.py` - Performance tests
- [x] Verify performance target (< 300ms compilation for typical agents)

## Testing & Validation

- [x] Run full test suite to ensure all tests pass (1080 tests passing)
- [x] Validate against all examples from 017-dsl-examples.md (29 tests)
- [x] Test error messages for all error codes
- [x] Test CLI commands with various inputs (26 tests)
- [x] Verify source map translation in stack traces (16 tests)

## Documentation

- [x] Create developer documentation in `docs/dev/dsl/`
  - [x] architecture.md - Compiler architecture overview
  - [x] grammar.md - Grammar development guide
  - [x] extending.md - Extension guide for new features
- [x] Create user documentation in `docs/user/dsl/`
  - [x] getting-started.md - Quick start guide
  - [x] syntax-reference.md - Complete syntax reference
  - [x] cli-reference.md - CLI commands reference
  - [x] troubleshooting.md - Common errors and solutions

## Summary

**Phase 5 Complete** - All implementation phases finished.

### Test Coverage
- Total DSL tests: 376
- Loader tests: 18
- Integration tests: 19
- Example validation tests: 29
- Performance tests: 11

### Quality Checks
All quality checks pass:
- pytest: 1080 tests passing
- ruff: No linting issues
- mypy: No type errors
- bandit: No security issues
- deptry: No dependency issues
- vulture: No unused code (after allowlist updates)

### Performance
- Typical agents compile in ~100-150ms
- Complex agents compile in ~150-250ms
- Cache hits complete in <10ms
