import codecs
import difflib
import os
from streetrace.tools.path_utils import normalize_and_validate_path, ensure_directory_exists

def write_file(file_path, content, work_dir, encoding='utf-8', binary_mode=False):
    """
    Securely write content to a file, ensuring the path is within the allowed root path.

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
        str: Path of the written file

    Raises:
        ValueError: If the file path is outside the allowed root path
        TypeError: If content type doesn't match the mode (str for text, bytes for binary)
        IOError: If there are issues writing the file
        OSError: If directory creation fails
    """
    # Normalize and validate the path
    abs_file_path = normalize_and_validate_path(file_path, work_dir)

    # Check content type
    if binary_mode and not isinstance(content, bytes):
        raise TypeError("Content must be bytes when binary_mode is True")
    if not binary_mode and not isinstance(content, str):
        raise TypeError("Content must be str when binary_mode is False")

    # Create directory if it doesn't exist
    ensure_directory_exists(abs_file_path)

    # Write the content to the file
    try:
        if binary_mode:
            with open(abs_file_path, 'wb') as f:
                f.write(content)
        else:
            written = content.splitlines(keepends=True)
            original = None
            if os.path.exists(abs_file_path):
                with codecs.open(abs_file_path, 'r', encoding=encoding) as f:
                    original = f.read()
            with codecs.open(abs_file_path, 'w', encoding=encoding) as f:
                f.write(content)
            if original:
                diff = difflib.unified_diff(original.splitlines(keepends=True), written, fromfile=file_path, tofile=file_path)
                diff = ''.join(diff)
            else:
                diff = f"File created: {file_path} ({len(written)} lines)"
        return file_path, diff
    except IOError as e:
        raise IOError(f"Error writing to file '{file_path}': {str(e)}")