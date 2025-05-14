"""write_file tool implementation."""

import codecs
from pathlib import Path

from streetrace.tools.definitions.path_utils import (
    ensure_parent_directory_exists,
    normalize_and_validate_path,
)


def write_utf8_file(
    path: str,
    content: str,
    work_dir: Path,
) -> str:
    """Create or overwrite a file with content encoded as utf-8.

    Always specify two parameters when calling this function: path to the file, and content to write.

    Args:
        path (str): The path to the file to write, relative to the working directory.
        content (str): Content to write to the file.
        work_dir (str): The working directory.

    Returns:
        Write operation status.

    """
    work_dir = work_dir.resolve()

    # Normalize and validate the path
    abs_file_path = normalize_and_validate_path(path, work_dir)
    rel_file_path = abs_file_path.relative_to(work_dir)

    # Create directory if it doesn't exist
    ensure_parent_directory_exists(abs_file_path)

    # Write the content to the file
    try:
        with codecs.open(str(abs_file_path), "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        msg = f"Error writing to file '{rel_file_path}': {e!s}"
        raise OSError(msg) from e
    else:
        return str(rel_file_path)
