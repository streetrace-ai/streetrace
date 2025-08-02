#!/usr/bin/env python3
"""Code review using StreetRace for GitHub Actions workflow."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Run code review."""
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: No OpenAI API key found. Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    # Run StreetRace
    model = os.getenv("STREETRACE_MODEL", "openai/gpt-4o")
    project_root = Path(__file__).parent.parent.parent.parent
    
    cmd = [
        "poetry", "run", "streetrace",
        f"--model={model}",
        "--agent=StreetRace_Code_Reviewer_Agent",
        "--prompt=Conduct a code review of recent changes. You MUST save the results to code-review-result.md using write_file tool. After saving, verify the file exists using read_file. Do not print the review to console.",
    ]

    result = subprocess.run(cmd, cwd=project_root)
    
    # Simple validation: check if file exists and has content
    review_file = project_root / "code-review-result.md"
    if result.returncode == 0 and review_file.exists() and review_file.stat().st_size > 0:
        print("SUCCESS: Code review completed and file saved!")
    else:
        print("ERROR: Code review failed or file not created")
        sys.exit(1)


if __name__ == "__main__":
    main()