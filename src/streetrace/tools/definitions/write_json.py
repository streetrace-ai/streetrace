"""write_json tool implementation with automatic validation and error guidance."""

import codecs
import json
from pathlib import Path

from streetrace.tools.definitions.path_utils import (
    ensure_parent_directory_exists,
    normalize_and_validate_path,
)
from streetrace.tools.definitions.result import OpResult, OpResultCode


def write_json_file(
    path: str,
    content: str,
    work_dir: Path,
) -> OpResult:
    """Create or overwrite a JSON file with validation.

    This tool validates JSON syntax before writing and provides detailed
    error messages with fix suggestions if validation fails.

    Args:
        path (str): The path to the file to write, relative to the working directory.
        content (str): JSON content to write to the file (as a string).
        work_dir (str): The working directory.

    Returns:
        dict[str,str]:
            "tool_name": "write_json"
            "result": "success" or "failure"
            "error": error message with fix suggestions if JSON is invalid

    """
    try:
        work_dir = work_dir.resolve()

        # Normalize and validate the path
        abs_file_path = normalize_and_validate_path(path, work_dir)

        # Validate JSON before writing
        try:
            # Parse the JSON to validate it
            parsed_json = json.loads(content)
            # Re-serialize with proper formatting
            formatted_content = json.dumps(parsed_json, indent=2)
        except json.JSONDecodeError as e:
            # Provide detailed error message with fix suggestions
            error_msg = f"""JSON validation failed for '{path}':

Error: {e.msg}
Location: Line {e.lineno}, Column {e.colno} (character {e.pos})

Please fix the JSON syntax and try again. The error is at character position {e.pos}."""

            return OpResult(
                tool_name="write_json",
                result=OpResultCode.FAILURE,
                error=error_msg,
                output=None,
            )

        # Create directory if it doesn't exist
        ensure_parent_directory_exists(abs_file_path)

        # Write the formatted content to the file
        with codecs.open(str(abs_file_path), "w", encoding="utf-8") as f:
            f.write(formatted_content)

    except (ValueError, OSError) as e:
        msg = f"Error writing JSON file '{path}': {e!s}"
        return OpResult(
            tool_name="write_json",
            result=OpResultCode.FAILURE,
            error=msg,
            output=None,
        )
    else:
        return OpResult(
            tool_name="write_json",
            result=OpResultCode.SUCCESS,
            output=f"Successfully wrote valid JSON to {path}",
            error=None,
        )
