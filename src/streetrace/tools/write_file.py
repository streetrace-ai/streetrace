"""write_file tool implementation."""

import codecs
import difflib
from pathlib import Path

from streetrace.tools.path_utils import (
    ensure_parent_directory_exists,
    normalize_and_validate_path,
)


def write_utf8_file(file_path: str, content: str, work_dir: Path) -> tuple[str, str]:
    """Securely write content to a file, ensuring the path is within the allowed root path.

    Args:
        file_path (str): Path to the file to write. Can be relative to work_dir or absolute.
        content (str): Content to write to the file.
        work_dir (Path): Root path that restricts access.
            The file_path must be within this work_dir for security.

    Returns:
        tuple[str, str]:
            str: Path of the written file (relative to work_dir)
            str: A diff string if the file existed before (or creation message).

    Raises:
        ValueError: If the file path is outside the allowed root path
        TypeError: If content type doesn't match the mode (str for text, bytes for binary)
        IOError: If there are issues writing the file
        OSError: If directory creation fails

    """
    work_dir = work_dir.resolve()

    # Normalize and validate the path
    abs_file_path = normalize_and_validate_path(file_path, work_dir)
    rel_file_path = abs_file_path.relative_to(work_dir)

    # Create directory if it doesn't exist
    ensure_parent_directory_exists(abs_file_path)

    # Initialize diff message
    diff = ""

    # Write the content to the file
    try:
        original = None
        if abs_file_path.exists():
            with codecs.open(str(abs_file_path), "r", encoding="utf-8") as f:
                original = f.read()

        with codecs.open(str(abs_file_path), "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        msg = f"Error writing to file '{rel_file_path}': {e!s}"
        raise OSError(msg) from e
    else:
        written = content.splitlines(keepends=True)
        if original is not None:
            diff_lines = difflib.unified_diff(
                original.splitlines(keepends=True),
                written,
                fromfile=str(rel_file_path),
                tofile=str(rel_file_path),
            )
            diff = "".join(diff_lines)
            if not diff:  # Handle case where content is identical
                diff = f"File content unchanged: {rel_file_path}"
        else:
            diff = f"File created: {rel_file_path} ({len(written)} lines)"

        return str(rel_file_path), diff
