# Gemini Tooling

This project provides a set of tools for interacting with the Gemini language model.

## Tools

*   `fs_tool.list_directory`: Lists files and directories in a given path.
*   `fs_tool.read_file`: Reads the content of a file.
*   `fs_tool.write_file`: Writes content to a file.
*   `fs_tool.execute_cli_command`: Executes a CLI command.
*   `search.search_files`: Searches for text in files matching a glob pattern.

## Usage

The tools can be used with the Gemini model to perform various tasks, such as reading and writing files, executing commands, and searching for information within files. The `search.search_files` tool searches for text in files within a given root directory, defaulting to the current directory.

## Environment Setup

To use these tools, you need to set the `GEMINI_API_KEY` environment variable with your Gemini API key.

## Running tests

To run the tests, execute `python -m unittest tests/test_search.py`.
