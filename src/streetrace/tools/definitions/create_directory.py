"""write_file tool implementation."""

from pathlib import Path

from streetrace.tools.definitions.path_utils import (
    normalize_and_validate_path,
)


def create_directory(
    path: str,
    work_dir: Path,
) -> list[dict[str, str]]:
    """Create a new directory or ensure a directory exists.

    Can create multiple nested directories. If the directory exists,
    the operation succeeds silently.

    Args:
        path (str): Path to create under current working directory.
        work_dir (Path): Root path that restricts access.

    Returns:
        Operation status.

    """
    work_dir = work_dir.resolve()

    # Normalize and validate the path
    abs_path = normalize_and_validate_path(path, work_dir)
    rel_path = abs_path.relative_to(work_dir)

    # Write the content to the file
    try:
        abs_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        msg = f"Error creating directory '{rel_path}': {e!s}"
        raise OSError(msg) from e
    else:
        return f"Successfully created directory '{rel_path!s}'"
