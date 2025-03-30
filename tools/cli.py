import queue
import subprocess
import threading

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
    try:
        def pipe_data(text_stream, msg_queue, lines_buffer):
            for line in iter(text_stream.readline, ''):
                msg_queue.put(line)
                lines_buffer.append(line)
            msg_queue.put(None)

        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        universal_newlines=True)
        
        stdout_queue = queue.Queue()
        stdout_thread = threading.Thread(target=pipe_data, args=(process.stdout, stdout_queue, stdout_lines))
        stdout_thread.daemon = True
        stdout_thread.start()
        
        stderr_queue = queue.Queue()
        stderr_thread = threading.Thread(target=pipe_data, args=(process.stderr, stderr_queue, stderr_lines))
        stderr_thread.daemon = True
        stderr_thread.start()

        while stdout_thread.is_alive() or stderr_thread.is_alive():
            for line in iter(stdout_queue.get, None):
                print(line, end='')
            for line in iter(stderr_queue.get, None):
                print(line, end='')
        
    except Exception as e:
        stderr_lines.append('\n')
        stderr_lines.append(str(e))

    return {
        "stdout": ''.join(stdout_lines),
        "stderr": ''.join(stderr_lines),
        "return_code": process.returncode if process else 1,
    }