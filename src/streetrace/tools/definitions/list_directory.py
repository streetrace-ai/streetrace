"""list_directory tool implementation."""

from pathlib import Path
from typing import TypedDict

import pathspec

from streetrace.tools.definitions.path_utils import (
    normalize_and_validate_path,
    validate_directory_exists,
)
from streetrace.tools.definitions.result import OpResult, OpResultCode


class ListDirItems(TypedDict):
    """Dir listing result to sent to LLM."""

    dirs: list[str] | None
    files: list[str] | None


class ListDirResult(OpResult):
    """Dir listing result to sent to LLM."""

    output: ListDirItems | None  # type: ignore[misc]


def load_gitignore_for_directory(path: Path) -> pathspec.PathSpec:
    """Load and compile .gitignore patterns for a given directory.

    Args:
        path (Path): The directory path to load .gitignore patterns from.

    Returns:
        pathspec.PathSpec: A compiled PathSpec object containing the ignore patterns,
        or None if no patterns are found.

    """
    gitignore_files: list[Path] = []
    current_path = path.resolve()

    # First, collect all gitignore paths from root to leaf
    while True:
        gitignore_path = current_path / ".gitignore"
        if gitignore_path.exists() and gitignore_path.is_file():
            gitignore_files.append(gitignore_path)
        parent_path = current_path.parent
        if current_path == parent_path:
            break
        current_path = parent_path

    # Reverse to process from root to leaf (so leaf patterns can override root patterns)
    gitignore_files.reverse()

    # Now read patterns from all files
    patterns = []
    for gitignore_path in gitignore_files:
        with gitignore_path.open() as f:
            for file_line in f:
                line = file_line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)

    # Create a single PathSpec from all collected patterns
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


# Check if file or directory is ignored with pre-loaded specs
def is_ignored(path: Path, base_path: Path, spec: pathspec.PathSpec) -> bool:
    """Check if a file or directory is ignored based on the provided PathSpec.

    Args:
        path (Path): The path to check.
        base_path (Path): The base directory for relative path calculation.
        spec (pathspec.PathSpec): The PathSpec object containing ignore patterns.

    Returns:
        bool: True if the path is ignored, False otherwise.

    """
    if path.is_absolute():
        path = path.relative_to(base_path)
    # Consider it a directory if it ends with '/' or if it exists and is a directory
    str_path = str(path)
    if base_path.joinpath(path).is_dir():
        str_path += "/"
    return spec.match_file(str_path) if spec else False


# Custom tool: read current directory structure honoring .gitignore correctly
def list_directory(
    path: str,
    work_dir: Path,
) -> ListDirResult:
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
    try:
        # Normalize and validate the path
        abs_path = normalize_and_validate_path(path, work_dir)

        # Check if directory exists
        validate_directory_exists(abs_path)

        # Get gitignore spec for the current directory
        spec = load_gitignore_for_directory(abs_path)

        # Use Path.glob to get all items in the current directory
        items = list(abs_path.glob("*"))
    except ValueError as ex:
        return ListDirResult(
            tool_name="list_directory",
            result=OpResultCode.FAILURE,
            output=None,
            error=str(ex),
        )
    else:
        dirs: list[str] = []
        files: list[str] = []

        # Filter items and classify them as directories or files
        for item in items:
            # Skip if item is ignored by gitignore rules
            if is_ignored(item, abs_path, spec):
                continue

            # Get path relative to work_dir
            rel_path = item.relative_to(work_dir)

            # Add to appropriate list
            if item.is_dir():
                dirs.append(str(rel_path))
            else:
                files.append(str(rel_path))

        # Sort for consistent output
        dirs.sort()
        files.sort()

        return ListDirResult(
            tool_name="list_directory",
            result=OpResultCode.SUCCESS,
            output=ListDirItems(
                dirs=dirs,
                files=files,
            ),
            error=None,
        )
