"""File discovery utilities."""

from pathlib import Path

# Directory names to ignore when discovering files
IGNORED_DIRECTORIES = {
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    "htmlcov",
    "venv",
    "env",
}


def find_files(
    base_paths: list[Path],
    glob_pattern: str,
    ignored_directories: set[str] | None = None,
) -> list[Path]:
    """Find files matching a glob pattern in search paths.

    Args:
        base_paths: List of base paths to search
        glob_pattern: Glob pattern to match files (e.g., "*.yaml", "*.py")
        ignored_directories: Set of directory names to ignore (defaults to
        IGNORED_DIRECTORIES)

    Returns:
        List of matching file paths, sorted and deduplicated

    """
    if ignored_directories is None:
        ignored_directories = IGNORED_DIRECTORIES

    files: list[Path] = []

    for search_path in base_paths:
        if not search_path.exists():
            continue

        # Find files matching the glob pattern
        matching_files = list(search_path.rglob(glob_pattern))

        # Filter out files in dot directories, dot files, or ignored directories
        filtered_files = [
            f
            for f in matching_files
            if not any(
                part.startswith(".") or part in ignored_directories for part in f.parts
            )
        ]

        files.extend(filtered_files)

    # Remove duplicates and sort
    return [f for f in sorted(set(files)) if f.is_file()]
