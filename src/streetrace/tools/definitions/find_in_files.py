"""find_in_files tool implementation."""

from pathlib import Path
from typing import TypedDict

from streetrace.tools.definitions.path_utils import (
    is_ignored,
    load_gitignore_for_directory,
    normalize_and_validate_path,
)
from streetrace.tools.definitions.result import OpResult, OpResultCode


class SearchResult(TypedDict):
    """A single search result."""

    filepath: str
    line_number: int
    snippet: str


class FindInFilesResult(OpResult):
    """Tool result to send to LLM."""

    output: list[SearchResult] | None  # type: ignore[misc]


def find_in_files(
    pattern: str,
    search_string: str,
    work_dir: Path,
) -> FindInFilesResult:
    """Recursively search for files and directories matching a pattern.

    Searches through all subdirectories from the starting path. The search
    is case-insensitive and matches partial names. Great for finding keywords
    and code symbols in files. Honors .gitignore rules.

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
    matches: list[SearchResult] = []

    work_dir = work_dir.resolve()
    errors: list[str] = []

    for file_path in work_dir.glob(pattern):
        # Validate each matching file is within work_dir
        try:
            abs_filepath = normalize_and_validate_path(file_path, work_dir)
            if abs_filepath.is_dir():
                continue

            # Load gitignore patterns for the file's directory
            # This ensures nested .gitignore files are properly respected
            file_dir = abs_filepath.parent
            gitignore_spec = load_gitignore_for_directory(file_dir)

            # Skip files that are ignored by .gitignore
            if is_ignored(abs_filepath, work_dir, gitignore_spec):
                continue

            with abs_filepath.open(encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if search_string in line:
                        # Get path relative to work_dir for display
                        rel_path = abs_filepath.relative_to(work_dir)
                        matches.append(
                            SearchResult(
                                filepath=str(rel_path),
                                line_number=i + 1,
                                snippet=line.strip(),
                            ),
                        )
        except (OSError, ValueError, UnicodeDecodeError) as err:
            errors.append(str(err))
            # If the file is outside work_dir, can't be read, or is binary
            # Just skip it and continue with other files

    if matches or len(errors) == 0:
        return FindInFilesResult(
            tool_name="find_in_files",
            result=OpResultCode.SUCCESS,
            output=matches,
            error=None,
        )
    return FindInFilesResult(
        tool_name="find_in_files",
        result=OpResultCode.FAILURE,
        output=None,
        error="\n\n".join(errors),
    )
