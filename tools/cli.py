
import subprocess

def execute_cli_command(command: str) -> dict:
    """Executes a CLI command and returns the output, error, and return code."""
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        return_code = process.returncode
        return {
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "return_code": 1,
        }
