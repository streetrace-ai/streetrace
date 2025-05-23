"""CLI tools."""

from pathlib import Path
from typing import Any

from streetrace.tools.definitions import cli


def execute_cli_command(
    command: list[str],
    work_dir: Path,
) -> dict[str, Any]:
    """Execute a CLI command interactively. Does not provide shell access.

    Args:
        command (list[str]): The command to execute.
        work_dir (Path): The working directory.

    Returns:
        A dictionary containing:
            - stdout: The captured standard output of the command
            - stderr: The captured standard error of the command
            - return_code: The return code of the command

    """
    return dict(cli.execute_cli_command(command, work_dir))
