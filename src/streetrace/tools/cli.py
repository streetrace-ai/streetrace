"""execute_cli_command tool implementation."""

import queue
import subprocess
import threading
from pathlib import Path
from typing import IO, Any, TypedDict


class CliResult(TypedDict):
    """Execute CLI result."""

    stdout: str
    stderr: str
    return_code: int | Any


def execute_cli_command(
    args: str | list[str],
    work_dir: Path,
) -> tuple[CliResult, str]:
    """Execute the CLI command and returns the output.

    The command's standard input/output/error are connected to the application's
    standard input/output/error, allowing for interactive use.

    Does not provide shell access.

    Args:
        args (list or str): The CLI command to execute.
        work_dir (Path): The working directory to execute the command in.

    Returns:
        tuple[CliResult, str]:
            CliResult: A dictionary containing:
                - stdout: The captured standard output of the command
                - stderr: The captured standard error of the command
                - return_code: The return code of the command
            str: UI view representation (rocess completed (return code))

    """
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    process = None

    # Normalize the working directory
    work_dir = work_dir.resolve()

    try:
        q: queue.Queue[str | None] = queue.Queue()

        def monitor(
            text_stream: IO[str] | None,
            lines_buffer: list[str],
        ) -> threading.Thread:
            def pipe() -> None:
                while True:
                    line = text_stream.readline() if text_stream else None
                    if not line:
                        break
                    q.put(line)
                    lines_buffer.append(line)
                q.put(None)

            t = threading.Thread(target=pipe, daemon=True)
            t.start()
            return t

        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=str(work_dir),
        )

        mt = [
            monitor(process.stdout, stdout_lines),
            monitor(process.stderr, stderr_lines),
        ]

        while any(t.is_alive() for t in mt):
            # print everything into stdout
            # b/c our stderr is for our errors, not tool errors
            for _line in iter(q.get, None):
                pass
    except Exception as e:  # noqa: BLE001 we want to report all exceptions to the agent
        stderr_lines.append("\n")
        stderr_lines.append(str(e))

    return (
        CliResult(
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
            return_code=process.returncode if process else 1,
        ),
        f"process completed ({process.returncode if process else 1})",
    )
