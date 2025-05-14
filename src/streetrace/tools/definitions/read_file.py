"""read_file tool implementation."""

import codecs
from pathlib import Path

from streetrace.tools.definitions.path_utils import (
    normalize_and_validate_path,
    validate_file_exists,
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
) -> dict[str, str]:
    """Read the contents of a file from the file system.

    Args:
        file_path (str): The path to the file to read, relative to the working directory.
        work_dir (str): The working directory.
        encoding (str): Text encoding to use.

    Returns:
        dict[str,str]:
            "type": "read_file"
            "result": "success" or "failure"
            "error": error message if there was an error reading the file
            "output": stdout output if the reading succeeded

    """
    # Normalize and validate the path
    abs_file_path = normalize_and_validate_path(file_path, work_dir)

    # Check if file exists and is a file (not a directory)
    validate_file_exists(abs_file_path)

    # Auto-detect binary if requested and we're not in binary mode already
    if is_binary_file(abs_file_path):
        return "<binary>"

    # Read and return file contents
    try:
        with codecs.open(str(abs_file_path), "r", encoding=encoding) as f:
            # contents = "".join(f"{i + 1}: {line}" for i, line in enumerate(f))
            contents = f.read()
            return {
                "type": "read_file",
                "result": "success",
                "output": contents,
            }
    except OSError as e:
        return {
            "type": "read_file",
            "result": "failure",
            "error": str(e),
        }
    except UnicodeDecodeError as e:
        msg = (
            f"Failed to decode '{file_path}' with encoding '{encoding}': "
            f"(object: {e.object}, start: {e.start}, end: {e.end}, reason: {e.reason}). "
            f"{e!s}"
        )
        return {
            "type": "read_file",
            "result": "failure",
            "error": msg,
        }
