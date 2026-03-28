"""Read-only file system tools for AI agents to safely inspect the local file system.

This module provides a subset of file system operations that are read-only,
allowing agents to explore the codebase and files without being able to
modify anything.
"""

from pathlib import Path
from typing import Any

import streetrace.tools.definitions.find_in_files as s
import streetrace.tools.definitions.list_directory as rds
import streetrace.tools.definitions.read_file as rf


def _clean_path(input_str: str) -> str:
    """Clean the input paths from surrounding whitespace and quotes."""
    return input_str.strip("\"'\r\n\t ")


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
