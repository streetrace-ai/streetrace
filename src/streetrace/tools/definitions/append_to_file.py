"""append_to_file tool implementation."""

import codecs
from pathlib import Path

from streetrace.tools.definitions.path_utils import (
    ensure_parent_directory_exists,
    normalize_and_validate_path,
)
from streetrace.tools.definitions.result import OpResult, OpResultCode


def append_to_file(
    path: str,
    content: str,
    work_dir: Path,
) -> OpResult:
    """Append content to an existing file or create a new file if it doesn't exist.

    Args:
        path (str): The path to the file to append to, relative to the working
            directory.
        content (str): Content to append to the file.
        work_dir (str): The working directory.

    Returns:
        dict[str,str]:
            "tool_name": "append_to_file"
            "result": "success" or "failure"
            "error": error message if there was an error appending to the file

    """
    try:
        work_dir = work_dir.resolve()

        # Normalize and validate the path
        abs_file_path = normalize_and_validate_path(path, work_dir)

        # Create directory if it doesn't exist
        ensure_parent_directory_exists(abs_file_path)

        # Append the content to the file
        with codecs.open(str(abs_file_path), "a", encoding="utf-8") as f:
            f.write(content)
    except (ValueError, OSError) as e:
        msg = f"Error appending to file '{path}': {e!s}"
        return OpResult(
            tool_name="append_to_file",
            result=OpResultCode.FAILURE,
            error=msg,
            output=None,
        )
    else:
        return OpResult(
            tool_name="append_to_file",
            result=OpResultCode.SUCCESS,
            output=None,
            error=None,
        )
