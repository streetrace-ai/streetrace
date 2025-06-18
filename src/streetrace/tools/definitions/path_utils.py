"""File utils for fs tools."""

from pathlib import Path

import pathspec


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


def load_gitignore_for_directory(path: Path) -> pathspec.PathSpec:
    """Load and compile .gitignore patterns for a given directory.

    Walks up the directory tree from the given path to collect all .gitignore files,
    then compiles them into a single PathSpec object. Child .gitignore files can
    override parent patterns.

    Args:
        path (Path): The directory path to load .gitignore patterns from.

    Returns:
        pathspec.PathSpec: A compiled PathSpec object containing the ignore patterns.
        Returns an empty PathSpec if no .gitignore files are found.

    """
    gitignore_files: list[Path] = []
    current_path = path.resolve()

    # First, collect all gitignore paths from root to leaf
    while True:
        gitignore_path = current_path / ".gitignore"
        if gitignore_path.exists() and gitignore_path.is_file():
            gitignore_files.append(gitignore_path)
        parent_path = current_path.parent
        if current_path == parent_path:
            break
        current_path = parent_path

    # Reverse to process from root to leaf (so leaf patterns can override root patterns)
    gitignore_files.reverse()

    # Now read patterns from all files
    patterns = []
    for gitignore_path in gitignore_files:
        with gitignore_path.open() as f:
            for file_line in f:
                line = file_line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)

    # Create a single PathSpec from all collected patterns
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def is_ignored(path: Path, base_path: Path, spec: pathspec.PathSpec) -> bool:
    """Check if a file or directory is ignored based on the provided PathSpec.

    Args:
        path (Path): The path to check.
        base_path (Path): The base directory for relative path calculation.
        spec (pathspec.PathSpec): The PathSpec object containing ignore patterns.

    Returns:
        bool: True if the path is ignored, False otherwise.

    """
    if path.is_absolute():
        path = path.relative_to(base_path)
    # Consider it a directory if it ends with '/' or if it exists and is a directory
    str_path = str(path)
    if base_path.joinpath(path).is_dir():
        str_path += "/"
    return spec.match_file(str_path) if spec else False
