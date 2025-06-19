"""list_directory tool implementation."""

from pathlib import Path
from typing import TypedDict

from streetrace.tools.definitions.path_utils import (
    is_ignored,
    load_gitignore_for_directory,
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
