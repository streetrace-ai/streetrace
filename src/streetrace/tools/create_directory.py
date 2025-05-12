"""write_file tool implementation."""

from pathlib import Path

from streetrace.tools.path_utils import (
    normalize_and_validate_path,
)


def create_directory(
    path: str,
    work_dir: Path,
) -> tuple[str, str]:
    """Create a directory (with all parents) in the working directory.

    Args:
        path (str): Path to create under current working directory.
        work_dir (Path): Root path that restricts access.
            The file_path must be within this work_dir for security.

    Returns:
        tuple[str, str]:
            str: Operation status
            str: Always None.

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
        return f"Successfully created directory '{rel_path!s}'", None
