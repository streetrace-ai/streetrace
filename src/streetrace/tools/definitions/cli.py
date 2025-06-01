"""execute_cli_command tool implementation."""

import queue
import subprocess  # nosec B404 see cli_safety.py
import threading
from pathlib import Path
from typing import IO

from streetrace.log import get_logger
from streetrace.tools.cli_safety import SafetyCategory, cli_safe_category
from streetrace.tools.definitions.result import CliResult, OpResultCode

logger = get_logger(__name__)

# Error message for risky commands
RISKY_COMMAND_ERROR = (
    "Command execution blocked: The command was flagged as potentially risky. "
    "Please use relative paths and avoid commands that may affect system state outside "
    "the current directory."
)


def execute_cli_command(
    args: str | list[str],
    work_dir: Path,
) -> CliResult:
    """Execute the CLI command and returns the output.

    The command's standard input/output/error are connected to the application's
    standard input/output/error, allowing for interactive use.

    Does not provide shell access.

    Args:
        args (list or str): The CLI command to execute.
        work_dir (Path): The working directory to execute the command in.

    Returns:
        dict[str,str]:
            "tool_name": "execute_cli_command"
            "result": "success" or "failure"
            "stderr": stderr output of the CLI command
            "stdout": stdout output of the CLI command

    """
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    process = None

    # Normalize the working directory
    work_dir = work_dir.resolve()

    # scripts should run in a jail, see: https://cwe.mitre.org/data/definitions/78.html
    # Check command safety
    safety_category = cli_safe_category(args)
    if safety_category == SafetyCategory.RISKY:
        logger.warning(
            "Attempted to execute risky command",
            extra={"command_input": args},
        )
        return CliResult(
            tool_name="execute_cli_command",
            result=OpResultCode.FAILURE,
            stdout="",
            stderr=RISKY_COMMAND_ERROR,
        )

    if safety_category == SafetyCategory.AMBIGUOUS:
        logger.info("Executing ambiguous command", extra={"command_input": args})
        # We still allow ambiguous commands, but log them for auditing

    completed_successfully = False

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

        process = subprocess.Popen(  # noqa: S603   # nosec B603 see cli_safety.py
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
        completed_successfully = True
    except Exception as e:
        error_message = str(e)
        logger.exception(
            "Error executing CLI command",
            extra={"error": error_message, "command_input": args},
        )
        stderr_lines.append("\n")
        stderr_lines.append(error_message)

    return CliResult(
        tool_name="execute_cli_command",
        result=OpResultCode.SUCCESS if completed_successfully else OpResultCode.FAILURE,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
    )
