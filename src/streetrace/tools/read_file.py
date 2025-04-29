"""read_file tool implementation."""

import codecs
from pathlib import Path

from streetrace.tools.path_utils import (
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
) -> tuple[str, str]:
    """Securely read a file's contents, ensuring the path is within the allowed root path.

    Args:
        file_path (str): Path to the file to read. Can be relative to work_dir or absolute.
        work_dir (Path): The working directory.
        encoding (str, optional): Text encoding to use. Defaults to 'utf-8'.

    Returns:
        tuple[str, str]:
            str or bytes: Contents of the file as a string (in text mode) or bytes (in binary mode)
            str: UI view of the read data (X characters read)

    Raises:
        ValueError: If the file path is outside the allowed root path or doesn't exist
        IOError: If there are issues reading the file
        UnicodeDecodeError: If the file can't be decoded using the specified encoding in text mode

    """
    # Normalize and validate the path
    abs_file_path = normalize_and_validate_path(file_path, work_dir)

    # Check if file exists and is a file (not a directory)
    validate_file_exists(abs_file_path)

    # Auto-detect binary if requested and we're not in binary mode already
    if is_binary_file(abs_file_path):
        return "<binary>", "<binary>"

    # Read and return file contents
    try:
        with codecs.open(str(abs_file_path), "r", encoding=encoding) as f:
            data = f.read()
            return data, f"{len(data)} characters read"
    except OSError as e:
        msg = f"Error reading file '{file_path}': {e!s}"
        raise OSError(msg) from e
    except UnicodeDecodeError as e:
        msg = (
            f"Failed to decode '{file_path}' with encoding '{encoding}'. "
            f"Try opening in binary mode or specify a different encoding. Error: {e!s}"
        )
        raise UnicodeDecodeError(
            msg,
            e.object,
            e.start,
            e.end,
            e.reason,
        ) from e
