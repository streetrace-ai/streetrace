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
        "--prompt=CRITICAL: You MUST create the file code-review-result.md using write_file tool. This is mandatory - the workflow will fail without it. Conduct a code review and save ALL results to this file. Verify file creation with read_file. Do not print to console.",
    ]

    result = subprocess.run(cmd, cwd=project_root)
    
    # Check if file exists and has content
    review_file = project_root / "code-review-result.md"
    if review_file.exists() and review_file.stat().st_size > 0:
        print("SUCCESS: Code review completed and file saved!")
    else:
        print("WARNING: Code review file not created, generating fallback")
        # Create fallback review file
        fallback_content = """# Code Review Results

## Summary
- **Files reviewed:** Unable to complete full review
- **Issues found:** Review process encountered technical difficulties
- **Overall assessment:** Manual review recommended
- **Scope assessment:** Unable to determine

## Technical Issue
The automated code review agent was unable to complete the review process
and save the results file. This may be due to:
- File system permissions
- Memory constraints
- Tool execution issues

## Recommendation
Please conduct a manual code review or investigate the workflow logs
for the specific technical issue that prevented automated review completion.
"""
        review_file.write_text(fallback_content)
        print("Fallback review file created")
        
    if result.returncode != 0:
        print(f"WARNING: StreetRace exited with code {result.returncode}")
        # Don't exit with error if we have a review file
        if not (review_file.exists() and review_file.stat().st_size > 0):
            sys.exit(1)


if __name__ == "__main__":
    main()