# Streetrace

Streetrace is an agentic AI coding partner that enables engineers to leverage AI from the command line to create software.

**Project Description:**

Streetrace defines a set of tools that the AI model can use to interact with the file system (listing directories, reading/writing files, and executing CLI commands) and search for text within files. The core logic resides in `gemini.py` and `claude.py`, which define the `generate_with_tool` function for their respective models. This function takes a user prompt and conversation history as input, sends it to the AI model, and handles function calls from the model based on the defined tools. The `main.py` script provides a simple command-line interface for interacting with the `generate_with_tool` function.

**Key Components:**

*   `gemini.py`: Contains the core logic for interacting with the Gemini AI model, defining tools, and handling function calls.
*   `claude.py`: Contains the core logic for interacting with the Claude AI model, defining tools, and handling function calls.
*   `main.py`: Provides a command-line interface for interacting with the `generate_with_tool` function.
*   `tools/fs_tool.py`: Implements file system tools (list directory, read file, write file, execute CLI command).
*   `tools/search.py`: Implements a tool for searching text within files.
*   `README.md`: Provides a high-level overview of the project and instructions for usage and setup.

**Workflow:**

1.  The user provides a prompt through the command-line interface in `main.py`. 
2.  The prompt is passed to the `generate_with_tool` function in either `gemini.py` or `claude.py`. 
3.  The `generate_with_tool` function sends the prompt and conversation history to the AI model.
4.  The AI model processes the input and may call one of the defined tools.
5.  If a tool is called, the `generate_with_tool` function executes the corresponding function in `tools/fs_tool.py` or `tools/search.py`. 
6.  The result of the tool execution is sent back to the AI model.
7.  The AI model generates a response, which is displayed to the user. 
8.  The conversation history is updated, and the process repeats.

## Tools

*   `fs_tool.list_directory`: Lists files and directories in a given path.
*   `fs_tool.read_file`: Reads the content of a file.
*   `fs_tool.write_file`: Writes content to a file.
*   `fs_tool.execute_cli_command`: Executes a CLI command.
*   `search.search_files`: Searches for text in files matching a glob pattern.

## Usage

The tools can be used with the AI model to perform various tasks, such as reading and writing files, executing commands, and searching for information within files. The `search.search_files` tool searches for text in files within a given root directory, defaulting to the current directory.

### Command Line Arguments

Streetrace supports the following command line arguments:

```
python main.py [--engine {claude|gemini}] [--model MODEL_NAME] [--prompt PROMPT] [--path PATH]
```

Options:
- `--engine` - Choose AI engine (claude or gemini)
- `--model` - Specific model name to use (e.g., claude-3-7-sonnet-20250219 or gemini-2.0-flash-001)
- `--prompt` - Prompt to send to the AI model (skips interactive mode if provided)
- `--path` - Specify which path to use as the working directory for all file operations

If no engine is specified, Streetrace will automatically select an AI model based on the available API keys in the following order:
1. Claude (if ANTHROPIC_API_KEY is set)
2. Gemini (if GEMINI_API_KEY is set)
3. OpenAI (if OPENAI_API_KEY is set - not yet implemented)

#### Working with Files in Another Directory

The `--path` argument allows you to specify a different working directory for all file operations:

```
python main.py --path /path/to/your/project
```

This path will be used as the working directory (work_dir) for all tools that interact with the file system, including:
- list_directory
- read_file
- write_file
- search_files

This feature makes it easier to work with files in another location without changing your current directory.

#### Non-interactive Mode

You can use the `--prompt` argument to run Streetrace in non-interactive mode:

```
python main.py --prompt "List all Python files in the current directory"
```

This will execute the prompt once and exit, which is useful for scripting or one-off commands.

### System Message Customization

Streetrace now centralizes system message handling in `main.py` and passes it to the model-specific functions. By default, it looks for a system message in `.streetrace/system_message.txt` and uses a default message if not found.

You can also programmatically specify a custom system message when using the `generate_with_tool` function:

```python
from claude import generate_with_tool

# Define a custom system message
system_message = """You are a helpful AI assistant specializing in Python development.
You provide clear, concise explanations and write clean, well-documented code."""

# Use the custom system message
conversation_history = generate_with_tool(
    "Create a simple hello world script",
    system_message=system_message
)
```

See `example_claude.py` and `example_gemini.py` for complete examples of how to use custom system messages.

## Environment Setup

To use these tools, you need to set one of the following environment variables:
- `ANTHROPIC_API_KEY` for Claude AI model
- `GEMINI_API_KEY` for Gemini AI model
- `OPENAI_API_KEY` for OpenAI (not implemented yet)

## Running tests

To run the tests, execute `python -m unittest tests/*test*.py`.