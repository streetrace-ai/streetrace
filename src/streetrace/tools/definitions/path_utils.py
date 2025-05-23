"""File utils for fs tools."""

from pathlib import Path


def normalize_and_validate_path(path: str | Path, work_dir: Path) -> Path:
    """Normalize and validate a file or directory path.

    This function performs the following:
    1. Normalizes both the path and work_dir (resolves '..', '.' etc.)
    2. Converts relative paths to absolute based on work_dir
    3. Validate that the resulting path is within work_dir

    Args:
        path (str or Path): Path to normalize and validate. Can be relative or absolute.
        work_dir (str): The working directory that serves as the root for relative paths
                       and as a security boundary for all paths.

    Returns:
        str: The normalized absolute path.

    Raises:
        ValueError: If the normalized path is outside the working directory.

    """
    if isinstance(path, str):
        path = Path(path)
    # If path is relative, make it absolute relative to work_dir
    abs_path = work_dir.joinpath(path).resolve()

    # Security check: ensure the path is within the work_dir
    if not str(abs_path).startswith(str(work_dir.resolve())):
        msg = (
            f"Security error: Path '{path}' resolves to a location outside the allowed "
            "working directory."
        )
        raise ValueError(
            msg,
        )

    return abs_path


def validate_file_exists(abs_path: Path) -> None:
    """Validate that a file exists at the given path.

    Args:
        abs_path (str): Absolute path to check.

    Raises:
        ValueError: If the file doesn't exist or is not a file.

    """
    if not abs_path.exists():
        msg = f"File not found: '{abs_path}'"
        raise ValueError(msg)

    if not abs_path.is_file():
        msg = f"Path is not a file: '{abs_path}'"
        raise ValueError(msg)


def validate_directory_exists(abs_path: Path) -> None:
    """Validate that a directory exists at the given path.

    Args:
        abs_path (str): Absolute path to check.

    Raises:
        ValueError: If the directory doesn't exist or is not a directory.

    """
    if not abs_path.exists():
        msg = f"Directory not found: '{abs_path}'"
        raise ValueError(msg)

    if not abs_path.is_dir():
        msg = f"Path is not a directory: '{abs_path}'"
        raise ValueError(msg)


def ensure_parent_directory_exists(abs_path: Path) -> None:
    """Ensure parent directory of the given path exists, creating it if necessary.

    Args:
        abs_path (str): Absolute path to the directory.

    Raises:
        OSError: If the directory cannot be created.

    """
    directory = abs_path.parent
    if directory and not directory.exists():
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Failed to create directory '{directory}': {e!s}"
            raise OSError(msg) from e
