"""find_in_files tool implementation."""

from pathlib import Path
from typing import TypedDict

from streetrace.tools.path_utils import normalize_and_validate_path
from streetrace.tools.tool_call_result import ToolOutput


class SearchResult(TypedDict):
    """A single search result."""

    filepath: str
    line_number: int
    snippet: str


def find_in_files(
    pattern: str,
    search_string: str,
    work_dir: Path,
) -> tuple[list[SearchResult], ToolOutput]:
    """Search for text occurrences in files given a glob pattern and a search string.

    Args:
        pattern (str): Glob pattern to match files (relative to work_dir).
        search_string (str): The string to search for.
        work_dir (str): The root directory for the glob pattern.

    Returns:
        tuple[SearchResult, ToolOutput]:
            SearchResult: A list of dictionaries, where each dictionary
                represents a match. Each dictionary contains the file path, line
                number, and a snippet of the line where the match was found.
            ToolOutput: UI view of the read data (X matches found)

    Raises:
        ValueError: If the pattern resolves to paths outside the work_dir.

    """
    matches: list[SearchResult] = []

    work_dir = work_dir.resolve()

    for file_path in work_dir.glob(pattern):
        # Validate each matching file is within work_dir
        try:
            abs_filepath = normalize_and_validate_path(file_path, work_dir)
            if abs_filepath.is_dir():
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
        except (OSError, ValueError, UnicodeDecodeError):
            # If the file is outside work_dir, can't be read, or is binary
            # Just skip it and continue with other files
            pass

    display_output = "\n".join([f"* {m.get("filepath")}" for m in matches])
    if not display_output:
        display_output = "0 matches found"
    return matches, ToolOutput(type="markdown", content=display_output)
