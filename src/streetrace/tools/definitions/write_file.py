"""write_file tool implementation."""

import codecs
from pathlib import Path

from streetrace.tools.definitions.path_utils import (
    ensure_parent_directory_exists,
    normalize_and_validate_path,
)
from streetrace.tools.definitions.result import OpResult, OpResultCode

# TODO(krmrn42): Idea, is it possible to check the basic file syntax before or after writing? At least line breaks, escape sequences.


def write_utf8_file(
    path: str,
    content: str,
    work_dir: Path,
) -> OpResult:
    """Create or overwrite a file with content encoded as utf-8.

    Always specify two parameters when calling this function: path to the file, and content to write.

    Args:
        path (str): The path to the file to write, relative to the working directory.
        content (str): Content to write to the file.
        work_dir (str): The working directory.

    Returns:
        dict[str,str]:
            "tool_name": "write_file"
            "result": "success" or "failure"
            "error": error message if there was an error writing to the file

    """
    try:
        work_dir = work_dir.resolve()

        # Normalize and validate the path
        abs_file_path = normalize_and_validate_path(path, work_dir)
        rel_file_path = abs_file_path.relative_to(work_dir)

        # Create directory if it doesn't exist
        ensure_parent_directory_exists(abs_file_path)

        # Write the content to the file
        with codecs.open(str(abs_file_path), "w", encoding="utf-8") as f:
            f.write(content)
    except (ValueError, OSError) as e:
        msg = f"Error writing to file '{rel_file_path}': {e!s}"
        return OpResult(
            tool_name="write_file",
            result=OpResultCode.FAILURE,
            error=msg,
        )
    else:
        return OpResult(
            tool_name="write_file",
            result=OpResultCode.SUCCESS,
        )
