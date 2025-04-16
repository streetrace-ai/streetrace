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

## Project Structure

### Root Directory (`./`)
- `README.md`, `README-*.md`: Main project documentation and provider-specific details.
- `CHANGES.md`: Project changelog.
- `CONTRIBUTING.md`: Contribution guidelines.
- `CONV.md`: Potentially conversation logs or related documentation.
- `LICENSE`: Project license file.
- `TODO.md`: List of upcoming tasks and features.
- `project_overview.md`: This file, providing a description of the project.
- `pyproject.toml`, `requirements.txt`: Python package and dependency definitions.

### Source Directory (`src/streetrace/`)
- `main.py`: Application entry point. Parses arguments, initializes core components.
- `application.py`: Orchestrates the main application flow, managing modes and coordinating UI, command execution, prompt processing, and AI interaction.
- `messages.py`: Message handling and formatting functions.
- `prompt_processor.py`: Processes user prompts, extracts context, and prepares system messages.

### LLM Directory (`src/streetrace/llm/`)
- Contains the logic for interacting with different Large Language Models.
- `llmapi.py`: Defines the base interface for LLM providers.
- `llmapi_factory.py`: Factory for creating specific LLM provider instances.
- `generate.py`: Handles the generation process.
- `wrapper.py`: Wraps LLM interactions.
- `history_converter.py`: Converts message history for different models.
- Subdirectories for each provider (`claude/`, `gemini/`, `ollama/`, `openai/`) containing provider-specific implementation details.

### Tools Directory (`src/streetrace/tools/`)
- Contains tools provided to the AI model for interacting with the environment.
- `fs_tool.py`: File system interaction tools (list_directory, read_file, write_file).
- `cli.py`: CLI command execution tool.
- `search.py`: Text search functionality.
- `path_utils.py`: Path manipulation and security utilities.
- `read_directory_structure.py`: Directory traversal utilities.
- `read_file.py`, `write_file.py`: Specific file I/O utilities.

### UI Directory (`src/streetrace/ui/`)
- `console_ui.py`: Manages user interaction via the console.
- `interaction_manager.py`: Manages the interaction cycle with the AI model.
- `colors.py`: Terminal color utilities.

### Commands Directory (`src/streetrace/commands/`)
- `command_executor.py`: Handles execution of internal commands (like 'exit', 'quit').

### Documentation Directory (`docs/`)
- Contains supplementary documentation.
- `claude_data_conversion.md`: Details on Claude-specific data handling.
- `provider_interface.md`: Description of the LLM provider interface.
    *(Note: This directory might contain other relevant architecture or technical documents as per `rules.md`)*

### Tests Directory (`tests/`)
- Contains unit and integration tests for various components (tools, LLM interactions, utilities, etc.).

### Examples Directory (`examples/`)
- Contains example scripts demonstrating programmatic usage.

*(Configuration files like `system.md` and `rules.md` are typically found in a `.streetrace` directory, which is not part of the core application structure but contains project configuration/rules).*

## Integration
StreetRace works with multiple AI providers:
- Anthropic's Claude (via `ANTHROPIC_API_KEY`)
- Google's Gemini (via `GEMINI_API_KEY`)
- OpenAI models (via `OPENAI_API_KEY`)
- Open-source models via Ollama (local or remote)

The architecture (`src/streetrace/llm`) allows for easy switching between providers based on available API keys or specific needs for different tasks.

## Usage Scenarios
- Code generation and modification
- Project exploration and understanding
- Code search and refactoring
- Script execution and debugging
- Documentation generation

StreetRace bridges the gap between powerful AI language models and local development environments, making it easier for developers to leverage AI assistance in their daily workflow.

## Instructions

Whenever you make any changes in this project, ensure this file is up to date and update with necessary changes.
