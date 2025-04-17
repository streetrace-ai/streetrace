import os
import queue
import subprocess
import threading
from typing import IO


def execute_cli_command(args: str | list[str], work_dir: str) -> dict:
    """
    Executes a CLI command and returns the output, error, and return code.

    The command's standard input/output/error are connected to the application's
    standard input/output/error, allowing for interactive use.

    Does not provide shell access.

    Args:
        command (list or str): The CLI command to execute.
        work_dir: The working directory to execute the command in.

    Returns:
        A dictionary containing:
        - stdout: The captured standard output of the command
        - stderr: The captured standard error of the command
        - return_code: The return code of the command
    """
    stdout_lines = []
    stderr_lines = []
    process = None

    # Validate work_dir exists and is a directory
    if not os.path.exists(work_dir):
        raise ValueError(f"Working directory '{work_dir}' does not exist")
    if not os.path.isdir(work_dir):
        raise ValueError(f"Path '{work_dir}' is not a directory")

    # Normalize the working directory
    abs_work_dir = os.path.abspath(os.path.normpath(work_dir))

    try:

        q = queue.Queue()

        def monitor(text_stream, lines_buffer):
            def pipe():
                while True:
                    line = text_stream.readline()
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
            cwd=abs_work_dir,
        )

        mt = [
            monitor(process.stdout, stdout_lines),
            monitor(process.stderr, stderr_lines),
        ]

        while any([t.is_alive() for t in mt]):
            # print everything into stdout
            # b/c our stderr is for our errors, not tool errors
            for line in iter(q.get, None):
                print(line, end="", flush=True)

    except Exception as e:
        stderr_lines.append("\n")
        stderr_lines.append(str(e))

    return {
        "stdout": "".join(stdout_lines),
        "stderr": "".join(stderr_lines),
        "return_code": process.returncode if process else 1,
    }, f"process completed ({process.returncode if process else 1})"
