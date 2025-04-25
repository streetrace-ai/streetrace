import os


def normalize_and_validate_path(path, work_dir):
    """Normalizes and validates a file or directory path to ensure it's within the working directory.

    This function performs the following:
    1. Normalizes both the path and work_dir (resolves '..', '.' etc.)
    2. Converts relative paths to absolute based on work_dir
    3. Validates that the resulting path is within work_dir

    Args:
        path (str): Path to normalize and validate. Can be relative or absolute.
        work_dir (str): The working directory that serves as the root for relative paths
                       and as a security boundary for all paths.

    Returns:
        str: The normalized absolute path.

    Raises:
        ValueError: If the normalized path is outside the working directory.

    """
    # Normalize and get absolute paths
    abs_work_dir = os.path.abspath(os.path.normpath(work_dir))

    # If path is relative, make it absolute relative to work_dir
    if not os.path.isabs(path):
        abs_path = os.path.abspath(os.path.join(abs_work_dir, os.path.normpath(path)))
    else:
        abs_path = os.path.abspath(os.path.normpath(path))

    # Security check: ensure the path is within the work_dir
    if not abs_path.startswith(abs_work_dir):
        msg = f"Security error: Path '{path}' resolves to a location outside the allowed working directory."
        raise ValueError(
            msg,
        )

    return abs_path


def validate_file_exists(abs_path) -> None:
    """Validates that a file exists at the given path.

    Args:
        abs_path (str): Absolute path to check.

    Raises:
        ValueError: If the file doesn't exist or is not a file.

    """
    if not os.path.exists(abs_path):
        msg = f"File not found: '{abs_path}'"
        raise ValueError(msg)

    if not os.path.isfile(abs_path):
        msg = f"Path is not a file: '{abs_path}'"
        raise ValueError(msg)


def validate_directory_exists(abs_path) -> None:
    """Validates that a directory exists at the given path.

    Args:
        abs_path (str): Absolute path to check.

    Raises:
        ValueError: If the directory doesn't exist or is not a directory.

    """
    if not os.path.exists(abs_path):
        msg = f"Directory not found: '{abs_path}'"
        raise ValueError(msg)

    if not os.path.isdir(abs_path):
        msg = f"Path is not a directory: '{abs_path}'"
        raise ValueError(msg)


def ensure_directory_exists(abs_path) -> None:
    """Ensures a directory exists at the given path, creating it if necessary.

    Args:
        abs_path (str): Absolute path to the directory.

    Raises:
        OSError: If the directory cannot be created.

    """
    directory = os.path.dirname(abs_path)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as e:
            msg = f"Failed to create directory '{directory}': {e!s}"
            raise OSError(msg)
