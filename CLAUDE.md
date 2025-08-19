# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StreetRace🚗💨 is an agentic AI coding partner designed to help engineers leverage AI capabilities directly from the command line. It serves as a bridge between AI language models and project resources, enabling AI to take actions on various tasks, with the main focus being Developer Experience and Productivity, Software Delivery, and DevOps.

## Common Development Commands

### Environment Setup

- **Install dependencies**: `poetry install`
- **Run StreetRace**: `poetry run streetrace --model=$YOUR_FAVORITE_MODEL`

### Development Workflow

- **Run tests**: `poetry run pytest tests -vv --no-header --timeout=5 -q` or `make test`
- **Run single test**: `poetry run pytest tests/path/to/test_file.py::test_function_name -v`
- **Lint code**: `poetry run ruff check src tests --ignore=FIX002` or `make lint`
- **Type checking**: `poetry run mypy src` or `make typed`
- **Security scan**: `poetry run bandit -r src` or `make security`
- **Check dependencies**: `poetry run deptry src tests` or `make depcheck`
- **Find unused code**: `poetry run vulture src vulture_allow.txt` or `make unusedcode`
- **Run all checks**: `make check` (runs test, lint, typed, security, depcheck, unusedcode)

**Important**: Run `make check` frequently during development and address all reported issues immediately before committing.

### Coverage and Profiling

- **Generate coverage report**: `make coverage`
- **Profile startup**: `poetry run python scripts/profile_startup.py`
- **Compare profiles**: `poetry run python scripts/compare_profiles.py`

## Architecture Overview

StreetRace follows a modular, layered architecture with clear separation of concerns:

### Core Components

**Workflow Layer (`workflow/supervisor.py`)**

- Orchestrates interaction loop between users and AI agents
- Manages ADK sessions and conversation persistence
- Handles tool integration and event processing

**Agent Management (`agents/agent_manager.py`)**

- Discovers, validates, and creates specialized AI agents
- Supports both modern StreetRaceAgent interface and legacy function-based agents
- Manages agent lifecycle with proper dependency injection

**LLM Integration (`llm/`)**

- `model_factory.py`: Factory for creating and caching language model instances
- `llm_interface.py`: Abstraction layer for various LLM providers
- `lite_llm_client.py`: Resilient client with retry logic and cost tracking

**UI Layer (`ui/`)**

- `console_ui.py`: Terminal-based interface with rich text and interactive prompts
- `ui_bus.py`: Event-driven communication system using pub/sub pattern
- `completer.py`: Intelligent auto-completion for files and commands

**Tool System (`tools/`)**

- `tool_provider.py`: Centralizes tool discovery and MCP integration
- `fs_tool.py`: Safe file system operations within working directory
- `cli_tool.py` + `cli_safety.py`: Controlled CLI command execution with security analysis
- `agent_tools.py`: Agent discovery and management tools

### Key Patterns

- **Dependency Injection**: Used throughout for testability and modularity
- **Event-Driven Architecture**: UI components communicate via UiBus events
- **Factory Pattern**: For model and agent creation
- **Command Pattern**: For internal commands (`commands/command_executor.py`)
- **Security by Design**: CLI safety analysis prevents dangerous operations

## Code Style Guidelines

### Python Standards

- Use type annotations for all functions
- Provide docstrings for public symbols
- Use imperative mood for the first line of docstrings.
- Use absolute imports (`from streetrace... import ...`)
- Use double quotes for strings
- Keep functions under McCabe complexity 10
- Use module-level logger: `streetrace.log.get_logger(__name__)`
- When logging, ensure deferred formatting by passing values as arguments to the logging
  method.
- Use logging.exception when logging exceptions.
- Introduce descriptive constants instead of magic values in comparisons and document
  constants using a docstring.
- Use a single `with` statement with multiple contexts instead of nested `with`
  statements.
- Keep newline at end of file.
- Always run `ruff` on the changed files.
- When raising exceptions, assign the message to a variable first.
- Create small clearly isolated and testable modules with dependency injection.
- Avoid boolean positional arguments in method definitions - use keyword-only arguments or enums instead.

### Naming Conventions

- **Avoid generic adjectives**: Don't use words like "Enhanced", "Advanced", "Improved" in class, method, and variable names
- **Use function-focused names**: Name things based on what they do, not how "good" they are
- **Examples**:
  - ❌ `EnhancedMCPTransport`, `ReliableMCPTransport` → ✅ `MCPTransport` or `RetryingMCPTransport`
  - ❌ `AdvancedAgentLoader` → ✅ `AgentLoader` or `RecursiveAgentLoader`
  - ❌ `enhanced_validation()` → ✅ `validate_schema()` or `strict_validate_schema()`

### Error Handling Strategy

- **UI Layer**: Be tolerant - log errors, show fallbacks, never crash
- **Core/Internal**: Be fail-fast - assert assumptions, crash on invalid state
- **Natural Language Parsing**: Be selectively tolerant - enforce critical fields
- **Third-Party APIs**: Balance carefully - fail-fast for reliable APIs, tolerate loose schemas

### Testing

- Use pytest with existing fixtures in `conftest.py` files
- Break up tests by user scenarios
- Achieve >95% coverage by addressing largest gaps
- Use `assert` statements, not unittest methods
- Add `# noqa: SLF001` when accessing private members in tests

## Project Structure

```
src/streetrace/
├── agents/          # Agent discovery and specialized implementations
├── commands/        # Internal command system
├── llm/            # Language model interfaces and clients
├── session/        # Session management and persistence
├── tools/          # File system, CLI, and agent tools
├── ui/             # Terminal interface and event system
├── utils/          # Utilities (user ID, argument hiding)
├── workflow/       # Core orchestration logic
├── app.py          # Main application setup
└── main.py         # CLI entry point
```

## Development Environment

**Recommended**: Use VS Code Dev Container for enhanced terminal with persistent bash history, autocompletion, and command shortcuts like `gs` (git status), `pi` (poetry install), `check` (make check).

## Key Integration Points

- **MCP Protocol**: External tool servers via `tools/mcp_transport.py`
- **ADK Framework**: Google's Agent Development Kit for agent execution
- **LiteLLM**: Standardized access to multiple LLM providers
- **Rich/Prompt-toolkit**: Terminal UI with formatting and completion

## Performance Considerations

- Startup performance is continuously monitored via GitHub Actions
- LLM interfaces include token estimation and cost tracking
- Tool operations respect .gitignore for efficient file discovery
- Session persistence enables context continuity across runs

# important-instruction-reminders

Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (\*.md) or README files. Only create documentation files if explicitly requested by the User.
