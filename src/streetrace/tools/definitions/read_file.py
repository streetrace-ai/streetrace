"""read_file tool implementation."""

import codecs
from pathlib import Path

from streetrace.tools.definitions.path_utils import (
    normalize_and_validate_path,
    validate_file_exists,
)
from streetrace.tools.definitions.result import (
    OpResult,
    op_error,
    op_success,
)

_BINARY_THRESHOLD = 0.3
"""Threshold of non-text chars in file sample for the file to be considered binary."""


def is_binary_file(file_path: Path, sample_size: int = 1024) -> bool:
    """Detect if a file is binary by examining a sample of its content.

    Args:
        file_path (Path): Path to the file to check.
        sample_size (int, optional): Number of bytes to sample. Defaults to 1024.

    Returns:
        bool: True if the file appears to be binary, False otherwise.

    """
    try:
        with file_path.open("rb") as f:
            sample = f.read(sample_size)

        # Check for null bytes, which are rare in text files
        if b"\x00" in sample:
            return True

        # Check for high ratio of non-text characters
        text_chars = bytearray(
            {7, 8, 9, 10, 12, 13, 27}
            | set(range(0x20, 0x7F))
            | set(range(0x80, 0x100)),
        )
        non_text_chars = sum(1 for byte in sample if byte not in text_chars)
        return non_text_chars / len(sample) > _BINARY_THRESHOLD if sample else False
    except OSError:
        # If we can't read the file, assume it's not binary
        return False


def read_file(
    file_path: str,
    work_dir: Path,
    encoding: str = "utf-8",
) -> OpResult:
    """Read the contents of a file from the file system.

    Args:
        file_path (str): Path of the file to read, relative to the working directory.
        work_dir (str): The working directory.
        encoding (str): Text encoding to use.

    Returns:
        dict[str,str]:
            "tool_name": "read_file"
            "result": "success" or "failure"
            "error": error message if there was an error reading the file
            "output": file contents if the reading succeeded

    """
    try:
        # Normalize and validate the path
        abs_file_path = normalize_and_validate_path(file_path, work_dir)

        # Check if file exists and is a file (not a directory)
        validate_file_exists(abs_file_path)

        # Auto-detect binary if requested and we're not in binary mode already
        if is_binary_file(abs_file_path):
            return op_success(tool_name="read_file", output="<binary>")

        # Read and return file contents
        with codecs.open(str(abs_file_path), "r", encoding=encoding) as f:
            contents = f.read()
            return op_success(
                tool_name="read_file",
                output=contents,
            )
    except (ValueError, OSError) as e:
        return op_error(
            tool_name="read_file",
            error=str(e),
        )
