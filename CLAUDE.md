# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StreetRace is a Python CLI tool for engineering-native AI agents that integrate with development tools and workflows. It's built using Poetry for dependency management and provides a modular agent system with MCP (Model Context Protocol) integration.

## Development Commands

### Testing and Quality
- **Run tests**: `make test` or `poetry run pytest tests -vv --no-header --timeout=5 -q`
- **Run single test**: `poetry run pytest tests/path/to/test_file.py::test_function_name -vv`
- **Full quality checks**: `make check` (runs tests, linting, typing, security, and dependency checks)

### Code Quality
- **Linting**: `make lint` or `poetry run ruff check src tests --ignore=FIX002`
- **Type checking**: `make typed` or `poetry run mypy src`

### Development Setup
- **Install dependencies**: `poetry install`
- **Run application**: `poetry run streetrace --model=<model_name>`
- **Development install**: `poetry install --with dev,test`

## Architecture Overview

### Core Components

**Application Flow (`src/streetrace/app.py`)**:
- Entry point that orchestrates all components
- Creates dependency injection container with ModelFactory, AgentManager, ToolProvider
- Initializes UI, session management, and input processing pipeline
- Input flows through: CommandExecutor → BashHandler → PromptProcessor → Supervisor

**Workflow Engine (`src/streetrace/workflow/supervisor.py`)**:
- Core orchestration between users and AI agents
- Manages ADK (Agent Development Kit) sessions and conversation context
- Handles agent creation, tool integration, and event processing
- Maintains both session state and global history

**Agent System (`src/streetrace/agents/`)**:
- Modular agent discovery and management
- Supports both StreetRaceAgent interface and legacy function-based agents
- Agents located in `./agents/` directory with `agent.py` and `README.md`
- AgentManager handles validation, creation, and lifecycle

**Tool System (`src/streetrace/tools/`)**:
- ToolProvider manages tool discovery from static tools, StreetRace modules, and MCP servers
- Core tools: file operations (fs_tool), CLI execution (cli_tool), agent management (agent_tools)
- CLI safety layer analyzes command safety before execution
- Tools receive context (working directory) via hide_args decorator

**UI Architecture (`src/streetrace/ui/`)**:
- ConsoleUI provides terminal interface with rich formatting and autocompletion
- UiBus implements pub/sub pattern for decoupled component communication
- CommandCompleter and PathCompleter provide intelligent autocompletion
- Real-time token usage and cost tracking

### Key Design Patterns

**Dependency Injection**: Core components receive dependencies through constructors
**Command Pattern**: Commands are registered with CommandExecutor and executed through standard interface
**Factory Pattern**: ModelFactory creates and caches LLM interface instances
**Pub/Sub**: UiBus enables decoupled communication between components
**Decorator Pattern**: hide_args decorator for automatic context injection

### Security Features

- CLI command safety analysis using bashlex
- Path validation to prevent directory traversal
- Operations constrained to working directory
- Allowlist-based command approval

## Testing Structure

Tests are organized in `tests/` with:
- `unit/` - Component-specific unit tests
- `integration/` - Integration tests
- `manual/` - Manual testing utilities

Test configuration in `pyproject.toml` with pytest-asyncio for async testing.

## Configuration

- **pyproject.toml**: Poetry configuration, tool settings (ruff, mypy, pytest)
- **Makefile**: Development task automation
- **mypy.ini**: Type checking configuration
- **.streetrace/**: Project-specific context and system instructions