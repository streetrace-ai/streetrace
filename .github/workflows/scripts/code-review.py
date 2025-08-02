#!/usr/bin/env python3
"""Code review using StreetRace for GitHub Actions workflow."""

import os
import subprocess
import sys
from pathlib import Path

from utils import print_error, print_success


def main() -> None:
    """Run code review."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("Usage: python code-review.py")
        print("Runs StreetRace code review.")
        return

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print_error("No OpenAI API key found. Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    # Get model and paths
    model = os.getenv("STREETRACE_MODEL", "openai/gpt-4o")
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent.parent
    template_path = project_root / ".github/workflows/templates/code-review-prompt.md"

    # Run StreetRace
    cmd = [
        "poetry", "run", "streetrace",
        f"--model={model}",
        "--agent=StreetRace_Code_Reviewer_Agent",
        f"--prompt=Follow the instructions in @{template_path.relative_to(project_root)} to conduct a code review of recent changes. Do not review the template file itself - use it as instructions only. At the end, use write_file to save the complete review in markdown format to code-review-result.md",
    ]

    result = subprocess.run(cmd, cwd=project_root)
    
    if result.returncode == 0:
        print_success("Code review completed!")
    else:
        print_error("Code review failed")
        sys.exit(1)


if __name__ == "__main__":
    main()