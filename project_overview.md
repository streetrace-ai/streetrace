# StreetRace Project Overview

## Project Goal
StreetRace is an agentic AI coding partner designed to help engineers leverage AI capabilities directly from the command line to create software. It serves as a bridge between AI language models and local file systems, allowing AI to assist with coding tasks by reading, writing, and manipulating files in a local development environment.

The primary goal is to create a seamless experience where developers can interact with an AI assistant that has access to necessary file system operations, enabling it to help write, modify, and debug code in real-time from the command line.

## Core Functionality
- Provides a set of tools for AI models to interact with the file system (read/write files, list directories)
- Executes CLI commands with interactive capabilities (allowing real-time input/output)
- Searches for text within files using glob patterns
- Supports multiple AI backends including Claude, Gemini, OpenAI, and locally-hosted models via Ollama
- Offers both interactive and non-interactive command-line interfaces
- Provides internal commands for session control (e.g., `exit`, `quit`, `history`) # <-- Added history

## Project Structure

### Root Files
- `main.py` - Application entry point. Parses arguments, initializes core components (UI, AI provider, tools, etc.), and delegates execution to `app.application.Application`.
- `claude.py` - Core logic for interacting with Claude AI models
- `gemini.py` - Core logic for interacting with Google's Gemini AI models
- `openai_client.py` - Core logic for interacting with OpenAI models
- `ollama_client.py` - Core logic for interacting with locally hosted models via Ollama
- `messages.py` - Message handling and formatting functions
- `colors.py` - Terminal color utilities for improved UI
- `requirements.txt` / `pyproject.toml` / `setup.py` - Python package configuration

### App Directory
- `application.py` - Orchestrates the main application flow, managing interactive and non-interactive modes, and coordinating UI, command execution, prompt processing, and AI interaction.
- `command_executor.py` - Handles execution of internal commands (like 'exit', 'quit').
- `console_ui.py` - Manages user interaction via the console (input/output).
- `interaction_manager.py` - Manages the interaction cycle with the AI model, including tool calls and response handling.
- `prompt_processor.py` - Processes user prompts, extracts context (like file mentions), and prepares system messages.

### Documentation
- `README.md` - Main project documentation
- `README-claude.md` - Claude-specific documentation
- `README-openai.md` - OpenAI-specific documentation
- `README-ollama.md` - Ollama-specific documentation
- `TODO.md` - Upcoming tasks and features

### Tools Directory
- `fs_tool.py` - File system interaction tools (list_directory, read_file, write_file)
- `cli.py` - CLI command execution tool with interactive capabilities
- `search.py` - Text search functionality across files
- `path_utils.py` - Path manipulation and security utilities
- `read_directory_structure.py` - Directory traversal utilities
- `read_file.py` / `write_file.py` - File I/O utilities

### Tests Directory
Contains unit tests for the core functionality, including:
- File system tools tests
- Path security validation tests
- AI model integration tests
- Search functionality tests

### Examples Directory
Contains example scripts demonstrating how to use the StreetRace APIs programmatically.

### .streetrace Directory
Contains configuration files:
- `system.md` - Custom system message for AI models
- `rules.md` - Development rules and guidelines for the project

## Integration
StreetRace works with multiple AI providers:
- Anthropic's Claude (via `ANTHROPIC_API_KEY`)
- Google's Gemini (via `GEMINI_API_KEY`)
- OpenAI models (via `OPENAI_API_KEY`)
- Open-source models via Ollama (local or remote)

The architecture allows for easy switching between providers based on available API keys or specific needs for different tasks.

## Usage Scenarios
- Code generation and modification
- Project exploration and understanding
- Code search and refactoring
- Script execution and debugging
- Documentation generation
- Reviewing conversation history (`history` command) # <-- Added history usage

StreetRace bridges the gap between powerful AI language models and local development environments, making it easier for developers to leverage AI assistance in their daily workflow.

## Instructions

Whenever you make any changes in this project, ensure this file is up to date and update with necessary changes.
