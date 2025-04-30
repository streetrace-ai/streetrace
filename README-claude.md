# Anthropic AI Assistant

This script (`anthropic.py`) allows you to interact with Anthropic's Anthropic 3 Sonnet AI model in a terminal interface with tool-calling capabilities for code assistance.

## Features

- Interactive terminal-based interface to Anthropic 3 Sonnet
- Tool-calling capabilities for file system operations:
  - List directory contents
  - Read file contents
  - Write to files
  - Execute CLI commands
  - Search for text in files
- Conversation history management
- Colorized output in the terminal
- Detailed logging

## Requirements

- Python 3.8+
- Anthropic API key

## Installation

1. Install the required package:

```bash
pip install anthropic
```

2. Set up your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

## Usage

You can import the script and use the `generate_with_tool` function in your Python code:

```python
from anthropic import generate_with_tool

# Start a new conversation
conversation_history = generate_with_tool("List all Python files in the current directory")

# Continue the conversation
conversation_history = generate_with_tool("Explain what the main.py file does", conversation_history)
```

### Conversation Flow

1. You provide a prompt to the model
2. The model responds with text and/or makes tool calls
3. If the model makes tool calls, they are executed and the results are fed back to the model
4. This continues until the model completes its response without making any more tool calls

## Logging

Logs are written to `claude_generation.log` and include:
- User prompts
- Model responses
- Tool calls and their results
- Any errors that occur

## Adapting the Tools

You can modify the `tools` list in the script to add, remove, or modify the available tools. Each tool definition requires:
- A name
- A description
- An input schema defining the parameters

Corresponding functions must be added to the `tools_dict` dictionary.

## System Prompt

The system prompt instructs Anthropic to act as an experienced software engineer working on a project with you. You can modify the `SYSTEM` variable to change these instructions.

## Model Configuration

The script uses Anthropic 3 Sonnet (version 20240229). You can change this by modifying the `model` parameter in the `client.messages.create()` call.