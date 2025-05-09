import subprocess
import sys

def run_ruff_check(file_path):
    try:
        result = subprocess.run(
            ["ruff", "check", file_path, "--verbose"],
            capture_output=True,
            text=True,
            check=False,
        )
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running ruff: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    file_path = "src/streetrace/llm_interface.py"
    run_ruff_check(file_path)