# Streetrace

Streetrace is an agentic AI coding partner that enables engineers to leverage AI from the command line to create software.

**Project Description:**

Streetrace defines a set of tools that the AI model can use to interact with the file system (listing directories, reading/writing files, and executing CLI commands) and search for text within files. The core logic resides in `gemini.py`, which defines the `generate_with_tool` function. This function takes a user prompt and conversation history as input, sends it to the AI model, and handles function calls from the model based on the defined tools. The `main.py` script provides a simple command-line interface for interacting with the `generate_with_tool` function.

**Key Components:**

*   `gemini.py`: Contains the core logic for interacting with the AI model, defining tools, and handling function calls.
*   `main.py`: Provides a command-line interface for interacting with the `generate_with_tool` function.
*   `tools/fs_tool.py`: Implements file system tools (list directory, read file, write file, execute CLI command).
*   `tools/search.py`: Implements a tool for searching text within files.
*   `README.md`: Provides a high-level overview of the project and instructions for usage and setup.

**Workflow:**

1.  The user provides a prompt through the command-line interface in `main.py`. 
2.  The prompt is passed to the `generate_with_tool` function in `gemini.py`. 
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

## Environment Setup

To use these tools, you need to set the `GEMINI_API_KEY` environment variable with your Gemini API key.

## Running tests

To run the tests, execute `python -m unittest tests/*test*.py`.
