# Str33tRace🚗💨 Project Overview

## Project Goal
StreetRace🚗💨 is an agentic AI coding partner designed to help engineers leverage AI capabilities directly from the command line to create software. It serves as a bridge between AI language models and local file systems, allowing AI to assist with coding tasks by reading, writing, and manipulating files in a local development environment.

The primary goal is to create a seamless experience where developers can interact with an AI assistant that has access to necessary file system operations, enabling it to help write, modify, and debug code in real-time from the command line.

## Core Functionality
- Provides a set of tools for AI models to interact with the file system (read/write files, list directories)
- Uses litellm to standardize interactions with multiple AI providers
- Executes CLI commands with interactive capabilities (allowing real-time input/output)
- Searches for text within files using glob patterns
- Supports multiple AI backends including Anthropic, Gemini, OpenAI, and locally-hosted models via Ollama
- Offers both interactive and non-interactive command-line interfaces

## Project Structure

Core components include:
* src/streetrace/application.py: Main application orchestration
* src/streetrace/interaction_manager.py: Implements the ReAct agent pattern for tool usage with AI models and implements litellm integration and tool execution
* src/streetrace/history.py: Manages conversation context
* src/streetrace/tools/: Implements file operations and CLI tools
* src/streetrace/ui/: Console UI implementation
* src/streetrace/commands/: User commands processing
* .streetrace directory contains StreetRace🚗💨 context and configuration files and rules that need to be followed by LLMs at all times, including this file. These files are not part of the core application structure.
* main.py is the entry point which parses command-line arguments and initializes core components

## Integration

StreetRace works with multiple AI providers:

- Anthropic's Anthropic (via `ANTHROPIC_API_KEY`)
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
