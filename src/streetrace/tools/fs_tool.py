"""File system tools."""

from pathlib import Path

import streetrace.tools.definitions.apply_unified_patch_content as apply_patch
import streetrace.tools.definitions.create_directory as c
import streetrace.tools.definitions.find_in_files as s
import streetrace.tools.definitions.read_directory_structure as rds
import streetrace.tools.definitions.read_file as rf
import streetrace.tools.definitions.write_file as wf


def _clean_path(input_str: str) -> str:
    """Clean the input paths from surrounding whitespace and quotes."""
    # Only strip whitespace, not quotes
    return input_str.strip("\"'\r\n\t ")


def list_directory(path: str, work_dir: Path) -> dict[str, list[str]]:
    """List all files and directories in a specified path.

    Honors .gitignore rules.

    Args:
        path (str): The path to scan, relative to the working directory.
        work_dir (str): The working directory.

    Returns:
        Dictionary with 'dirs' and 'files' lists containing paths relative to working directory.

    Raises:
        ValueError: If the requested path is outside the allowed root path.

    """
    return rds.read_directory_structure(_clean_path(path), work_dir)


def read_file(
    path: str,
    work_dir: Path,
    encoding: str = "utf-8",
) -> str:
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
    return rf.read_file(_clean_path(path), work_dir, encoding)


def write_file(path: str, content: str, work_dir: Path) -> str:
    """Create or overwrite a file with content encoded as utf-8.

    Always specify two parameters when calling this function: path to the file, and content to write.

    Args:
        path (str): The path to the file to write, relative to the working directory.
        content (str): Content to write to the file.
        work_dir (str): The working directory.

    Returns:
        Write operation status.

    """
    return wf.write_utf8_file(
        _clean_path(path),
        content,
        work_dir,
    )


def find_in_files(
    pattern: str,
    search_string: str,
    work_dir: Path,
) -> list[dict[str, str]]:
    """Recursively search for files and directories matching a pattern.

    Searches through all subdirectories from the starting path. The search
    is case-insensitive and matches partial names. Great for finding keywords
    and code symbols in files.

    Args:
        pattern (str): Glob pattern to match files within the working directory.
        search_string (str): The string to search for.
        work_dir (Path): The working directory for the glob pattern.

    Returns:
        A list of dictionaries, where each dictionary represents a match:
            - filepath: path of the found file
            - line_number: match line number
            - snippet: match snippet

    """
    return s.find_in_files(
        _clean_path(pattern),
        _clean_path(search_string),
        work_dir=work_dir,
    )


def create_directory(
    path: str,
    work_dir: Path,
) -> list[dict[str, str]]:
    """Create a new directory or ensure a directory exists.

    Can create multiple nested directories. If the directory exists,
    the operation succeeds silently.

    Args:
        path (str): Path to create under current working directory.
        work_dir (Path): Root path that restricts access.

    Returns:
        Operation status.

    """
    return c.create_directory(
        _clean_path(path),
        work_dir=work_dir,
    )


def apply_unified_patch_content(patch_content: str, work_dir: Path) -> dict[str,str]:
    r"""Apply a unified diff patch to local files in the working directory.

    Start all local paths with the current directory (./), e.g.:

    ```
    --- /dev/null
    +++ ./answer.txt
    @@ -0,0 +1 @@
    +42
    ```

    You should provide context lines before and after your changes to show where the
    modified section ends and what the unchanged code looks like afterward, e.g.:

    ```
    --- ./answer.txt
    +++ ./answer.txt
    @@ -4,6 +4,6 @@ and everything

    42

    -from the
    +quote from the
    "The Hitchhiker's Guide to the Galaxy"
    by Douglas Adams
    \ No newline at end of file
    ```

    This is a preferred way of applying changes to project files. It allows
    changing several files at once. All changes to all files can be applied
    at once following the GNU patch unified diff format.

    Never run bash scripts with apply_unified_patch_content. Use this function
    only to create or modify files in the working directory.

    Args:
        patch_content (str): The unified diff patch content.
        work_dir (Path): The directory where the patch should be applied.

    Returns:
        dict[str,str]:
            "result": success or failure
            "stderr": stderr output of the GNU patch command
            "stdout": stdout output of the GNU patch command

    """
    return apply_patch.apply_unified_patch_content(
        patch_content=patch_content,
        work_dir=work_dir,
    )
