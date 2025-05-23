"""write_file tool implementation."""

from pathlib import Path

from streetrace.tools.definitions.path_utils import (
    normalize_and_validate_path,
)
from streetrace.tools.definitions.result import (
    OpResult,
    op_error,
    op_success,
)


def create_directory(
    path: str,
    work_dir: Path,
) -> OpResult:
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
    work_dir = work_dir.resolve()

    # Normalize and validate the path
    abs_path = normalize_and_validate_path(path, work_dir)
    rel_path = abs_path.relative_to(work_dir)

    # Write the content to the file
    try:
        abs_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return op_error(
            tool_name="create_directory",
            error=f"Error creating directory '{rel_path}': {e!s}",
        )
    else:
        return op_success(
            tool_name="create_directory",
            output=f"Successfully created directory '{rel_path!s}'",
        )
