"""File system tools."""

from pathlib import Path

import streetrace.tools.find_in_files as s
import streetrace.tools.read_directory_structure as rds
import streetrace.tools.read_file as rf
import streetrace.tools.write_file as wf
from streetrace.tools import cli


def _clean_path(input_str: str) -> str:
    """Clean the input by removing unwanted whitespace characters, but preserving quotes."""
    # Only strip whitespace, not quotes
    return input_str.strip("\"'\r\n\t ")


def list_directory(path: str, work_dir: Path) -> tuple[dict[str, list[str]], str]:
    """Read directory structure while honoring .gitignore rules.

    Args:
        path (str): The path to scan. Must be within the work_dir.
        work_dir (str): The working directory.

    Returns:
        tuple[dict[str, list[str]], str]:
            dict[str, list[str]]: Dictionary with 'dirs' and 'files' lists containing paths relative to work_dir
            str: UI view representation

    Raises:
        ValueError: If the requested path is outside the allowed root path.

    """
    return rds.read_directory_structure(_clean_path(path), work_dir)


def read_file(
    path: str,
    work_dir: Path,
    encoding: str = "utf-8",
) -> tuple[str | bytes, str]:
    """Read file contents.

    Args:
        path (str): The path to the file to read. Must be within the work_dir.
        work_dir (str): The working directory.
        encoding (str, optional): Text encoding to use. Defaults to 'utf-8'.

    Returns:
        tuple[str, str]:
            str or bytes: Contents of the file as a string (in text mode) or bytes (in binary mode)
            str: UI view of the read data (X characters read)

    """
    return rf.read_file(_clean_path(path), work_dir, encoding)


def write_file(path: str, content: str, work_dir: Path) -> tuple[str, str]:
    """Write content to a file.

    Args:
        path (str): The path to the file to write. Must be within the work_dir.
        content (str or bytes): Content to write to the file.
        work_dir (str): The working directory.
        encoding (str, optional): Text encoding to use. Defaults to 'utf-8'.

    Returns:
        tuple[str, str]:
            str: Path of the written file (relative to work_dir)
            str: A diff string if the file existed before (or creation message).

    """
    return wf.write_utf8_file(
        _clean_path(path),
        content,
        work_dir,
    )


def execute_cli_command(
    command: list[str] | str,
    work_dir: Path,
) -> tuple[cli.CliResult, str]:
    """Execute a CLI command interactively. Does not provide shell access.

    Args:
        command (list[str] or str): The command to execute.
        work_dir (Path): The working directory.

    Returns:
        tuple[cli.CliResult, str]:
            cli.CliResult: A dictionary containing:
                - stdout: The captured standard output of the command
                - stderr: The captured standard error of the command
                - return_code: The return code of the command
            str: UI view representation (rocess completed (return code))

    """
    return cli.execute_cli_command(command, work_dir)


def find_in_files(
    pattern: str,
    search_string: str,
    work_dir: Path,
) -> tuple[list[s.SearchResult], str]:
    """Search for text occurrences in files given a glob pattern and a search string.

    Args:
        pattern (str): Glob pattern to match files (relative to work_dir).
        search_string (str): The string to search for.
        work_dir (Path): The working directory for the glob pattern.

    Returns:
        tuple[list[s.SearchResult], str]:
            list[s.SearchResult]: A list of dictionaries, where each dictionary
                represents a match. Each dictionary contains the file path, line
                number, and a snippet of the line where the match was found.
            str: UI view of the read data (X matches found)

    """
    return s.find_in_files(
        _clean_path(pattern),
        _clean_path(search_string),
        work_dir=work_dir,
    )


def find_feature_code_pointers(
    keywords: list[str],
    work_dir: Path,
) -> tuple[list[s.SearchResult], str]:
    """Search for any of the given keywords in project files and return occurrences to identify code pointers where a certain feature can be found.

    Args:
        keywords (list[str]): Exact match keywords to search for.
        work_dir (Path): The working directory for the glob pattern.

    Returns:
        tuple[list[s.SearchResult], str]:
            list[s.SearchResult]: A list of dictionaries, where each dictionary
                represents a match. Each dictionary contains the file path, line
                number, and a snippet of the line where the match was found.
            str: UI view of the read data (X matches found)

    """
    results = []
    for keyword in keywords:
        matches, _ = find_in_files("**/*.py", keyword, work_dir)
        results.extend(matches)
    for keyword in keywords:
        matches, _ = find_in_files("**/*.md", keyword, work_dir)
        results.extend(matches)
    return results, f"{len(results)} matches found"


# Define common tools list
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_in_files",
            "description": "Search for text occurrences in files given a glob pattern and a search string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match files.",
                    },
                    "search_string": {
                        "type": "string",
                        "description": "The string to search for.",
                    },
                },
                "required": ["pattern", "search_string"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_feature_code_pointers",
            "description": "Search for any of the given keywords in project files and return occurrences to identify code pointers where a certain feature can be found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exact match keywords to search for",
                    },
                },
                "required": ["keywords"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_cli_command",
            "description": "Execute a CLI command in interactive mode and returns the output, error, and return code. Does not provide shell access.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The CLI command to execute.",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write utf-8 text to a file. Overwrites the file if it already exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write to.",
                    },
                    "content": {
                        "type": "string",
                        "description": "New content of the file.",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to retrieve the contents from.",
                    },
                    "encoding": {
                        "type": "string",
                        "description": 'Text encoding to use. Defaults to "utf-8".',
                    },
                },
                "required": ["path", "encoding"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in the requested directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to retrieve the contents from.",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
]

TOOL_IMPL = {
    "find_feature_code_pointers": find_feature_code_pointers,
    "find_in_files": find_in_files,
    "execute_cli_command": execute_cli_command,
    "write_file": write_file,
    "read_file": read_file,
    "list_directory": list_directory,
}
