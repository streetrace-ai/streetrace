import codecs
import difflib
import os

from streetrace.tools.path_utils import (
    ensure_directory_exists,
    normalize_and_validate_path,
)


def write_file(file_path, content, work_dir, encoding="utf-8", binary_mode=False):
    """Securely write content to a file, ensuring the path is within the allowed root path.

    Args:
        file_path (str): Path to the file to write. Can be relative to work_dir or absolute.
        content (str or bytes): Content to write to the file.
        work_dir (str): Root path that restricts access.
            The file_path must be within this work_dir for security.
        encoding (str, optional): Text encoding to use when writing text. Defaults to 'utf-8'.
            This is ignored if binary_mode is True.
        binary_mode (bool, optional): If True, write the file in binary mode. Defaults to False.
            In binary mode, content must be bytes.

    Returns:
        tuple[str, str]: A tuple containing the path of the written file (relative to work_dir)
                         and a diff string (or creation message).

    Raises:
        ValueError: If the file path is outside the allowed root path
        TypeError: If content type doesn't match the mode (str for text, bytes for binary)
        IOError: If there are issues writing the file
        OSError: If directory creation fails

    """
    # Normalize and validate the path
    abs_file_path = normalize_and_validate_path(file_path, work_dir)
    rel_file_path = os.path.relpath(
        abs_file_path,
        work_dir,
    )  # Get relative path for return

    # Check content type
    if binary_mode and not isinstance(content, bytes):
        msg = "Content must be bytes when binary_mode is True"
        raise TypeError(msg)
    if not binary_mode and not isinstance(content, str):
        msg = "Content must be str when binary_mode is False"
        raise TypeError(msg)

    # Create directory if it doesn't exist
    ensure_directory_exists(abs_file_path)

    # Initialize diff message
    diff = ""

    # Write the content to the file
    try:
        if binary_mode:
            with open(abs_file_path, "wb") as f:
                bytes_written = f.write(content)
            diff = f"Binary file written: {rel_file_path} ({bytes_written} bytes)"
        else:
            written = content.splitlines(keepends=True)
            original = None
            if os.path.exists(abs_file_path):
                with codecs.open(abs_file_path, "r", encoding=encoding) as f:
                    original = f.read()

            with codecs.open(abs_file_path, "w", encoding=encoding) as f:
                f.write(content)

            if original is not None:
                diff_lines = difflib.unified_diff(
                    original.splitlines(keepends=True),
                    written,
                    fromfile=rel_file_path,
                    tofile=rel_file_path,
                )
                diff = "".join(diff_lines)
                if not diff:  # Handle case where content is identical
                    diff = f"File content unchanged: {rel_file_path}"
            else:
                diff = f"File created: {rel_file_path} ({len(written)} lines)"

        return rel_file_path, diff
    except OSError as e:
        msg = f"Error writing to file '{rel_file_path}': {e!s}"
        raise OSError(msg)
