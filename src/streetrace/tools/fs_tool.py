"""File system tools for AI agents to safely interact with the local file system.

This module provides a standardized interface for AI agents to perform file system
operations like reading, writing, listing directories, and searching file contents.
All operations are constrained to the working directory for security, with path
sanitization and validation to prevent unauthorized access.
"""

# TODO(krmrn42): Use BaseToolset
from pathlib import Path
from typing import Any

import streetrace.tools.definitions.create_directory as c
import streetrace.tools.definitions.find_in_files as s
import streetrace.tools.definitions.list_directory as rds
import streetrace.tools.definitions.read_file as rf
import streetrace.tools.definitions.write_file as wf


def _clean_path(input_str: str) -> str:
    """Clean the input paths from surrounding whitespace and quotes."""
    # Only strip whitespace, not quotes
    return input_str.strip("\"'\r\n\t ")


def create_directory(
    path: str,
    work_dir: Path,
) -> dict[str, Any]:
    """Create a new directory or ensure a directory exists.

    Can create multiple nested directories. If the directory exists,
    the operation succeeds silently.

    Args:
        path (str): Path to create under current working directory.
        work_dir (Path): Root path that restricts access.

    Returns:
        dict[str,str]:
            "tool_name": "create_directory"
            "result": "success" or "failure"
            "error": error message if the directory creation failed
            "output": tool output if the directory was created

    """
    return dict(
        c.create_directory(
            _clean_path(path),
            work_dir=work_dir,
        ),
    )


def find_in_files(
    pattern: str,
    search_string: str,
    work_dir: Path,
) -> dict[str, Any]:
    """Recursively search for files and directories matching a pattern.

    Searches through all subdirectories from the starting path. The search
    is case-insensitive and matches partial names. Great for finding keywords
    and code symbols in files.

    Args:
        pattern (str): Glob pattern to match files within the working directory.
        search_string (str): The string to search for.
        work_dir (Path): The working directory for the glob pattern.

    Returns:
        dict[str,str|list[dict[str,str]]]:
            "tool_name": "find_in_files"
            "result": "success" or "failure"
            "error": error message if the search couldn't be completed
            "output" (list[dict[str,str]]): A list search results, where each
                dictionary item represents a match:
                - "filepath": path of the found file
                - "line_number": match line number
                - "snippet": match snippet

    """
    return dict(
        s.find_in_files(
            _clean_path(pattern),
            _clean_path(search_string),
            work_dir=work_dir,
        ),
    )


def list_directory(
    path: str,
    work_dir: Path,
) -> dict[str, Any]:
    """List all files and directories in a specified path.

    Honors .gitignore rules.

    Args:
        path (str): The path to scan, relative to the working directory.
        work_dir (str): The working directory.

    Returns:
        dict[str,str|dict[str,list[str]]]:
            "tool_name": "list_directory"
            "result": "success" or "failure"
            "error": error message if the listing couldn't be completed
            "output":
                dict[str,list[str]]:
                    - "dirs": list of directories in this directory
                    - "files": list of files in this directory

    """
    return dict(rds.list_directory(_clean_path(path), work_dir))


def read_file(
    path: str,
    work_dir: Path,
) -> dict[str, Any]:
    """Read the contents of a file from the file system.

    Args:
        path (str): The path to the file to read, relative to the working directory.
        work_dir (str): The working directory.

    Returns:
        dict[str,Any]:
            "tool_name": "read_file"
            "result": "success" or "failure"
            "error": error message if there was an error reading the file
            "output": file contents if the reading succeeded

    """
    return dict(rf.read_file(_clean_path(path), work_dir))


def write_file(
    path: str,
    content: str,
    work_dir: Path,
) -> dict[str, Any]:
    """Create or overwrite a file with content encoded as utf-8.

    For python scripts, checks python syntax before writing and outputs syntax errors
    if present.

    Args:
        path (str): The path to the file to write, relative to the working directory.
        content (str): Content to write to the file.
        work_dir (str): The working directory.

    Returns:
        dict[str,Any]:
            "tool_name": "write_file"
            "result": "success" or "failure"
            "error": error message if there was an error writing to the file

    """
    return dict(
        wf.write_utf8_file(
            _clean_path(path),
            content,
            work_dir,
        ),
    )
