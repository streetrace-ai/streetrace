#!/usr/bin/env python3
"""Simple diff-based AI code review implementation.

This module implements a simplified holistic diff-based review that lets
the StreetRace agent handle git operations and analysis directly.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from utils import (
    JSON_CLEANUP_PATTERNS,
    print_error,
    print_status,
    print_success,
    print_warning,
)


def setup_environment(project_root: Path) -> None:
    """Set up environment variables and load .env file if present."""
    # Load environment variables from .env if it exists
    env_file = project_root / ".env"
    if env_file.exists():
        print_status("Loading environment variables from .env")
        with env_file.open() as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value

    # Set timeout for GitHub Actions environment
    os.environ.setdefault("HTTPX_TIMEOUT", "600")
    os.environ.setdefault("REQUEST_TIMEOUT", "600")
    os.environ.setdefault("LITELLM_REQUEST_TIMEOUT", "600")
    os.environ.setdefault("STREETRACE_TIMEOUT", "600000")


def run_simple_diff_review(project_root: Path, model: str, base_ref: str = "main") -> tuple[str, str]:
    """Run a simple diff-based review using StreetRace agent directly."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create reviews directory
    reviews_dir = project_root / "code-reviews"
    reviews_dir.mkdir(exist_ok=True)
    
    # Create output file for streaming
    output_file = reviews_dir / f"{timestamp}_diff_output.txt"
    
    try:
        # Clean up any existing JSON files before review
        for pattern in JSON_CLEANUP_PATTERNS:
            for search_dir in [project_root, Path.cwd()]:
                cleanup_file = search_dir / pattern
                if cleanup_file.exists():
                    try:
                        cleanup_file.unlink()
                    except:
                        pass

        # Simple prompt that lets the agent handle everything
        prompt = f"""Review this pull request using a holistic diff-based approach:

1. Use the execute_cli_command tool to run: git diff {base_ref}...HEAD
2. If the diff is very large (>100k chars), intelligently trim it while prioritizing security-critical files
3. If you trim the diff, include this exact warning: "The diff has been trimmed to fit into the context window, please keep the PRs smaller"
4. Review the entire diff for security vulnerabilities, code quality, and cross-file consistency
5. Use the write_json tool to save your review with this structure:

{{
  "summary": "Brief review summary of all changes",
  "issues": [
    {{
      "severity": "error|warning|notice",
      "line": 42,
      "title": "Issue Title",
      "message": "Detailed description", 
      "category": "security|performance|quality|testing|maintainability",
      "code_snippet": "problematic code",
      "file": "path/to/file"
    }}
  ],
  "positive_feedback": ["Good practices found"],
  "metadata": {{
    "review_focus": "holistic diff analysis",
    "review_type": "diff_based"
  }}
}}

Focus on security vulnerabilities (SQL injection, command injection, hardcoded secrets) and mark them as "error" severity.
Execute the review immediately using the available tools."""

        # Run StreetRace with the simple prompt
        cmd = [
            "poetry", "run", "streetrace",
            f"--model={model}",
            "--agent=StreetRace_Code_Reviewer_Agent",
            f"--prompt={prompt}",
        ]

        # Use shell tee command for real-time streaming
        shell_cmd = " ".join([f'"{arg}"' for arg in cmd]) + f' | tee "{output_file}"'

        print_status("Running holistic diff-based review...")
        start_time = time.time()
        
        result_code = subprocess.call(
            shell_cmd,
            shell=True,
            cwd=project_root,
            timeout=600,  # 10 minute timeout
        )

        review_duration = int((time.time() - start_time) * 1000)

        if result_code != 0:
            print_warning(f"Review process returned exit code {result_code}")

        # Look for JSON files created by the agent
        review_data = None
        json_file_found = None

        # Wait for file system to flush
        time.sleep(0.5)

        for search_dir in [project_root, Path.cwd()]:
            for json_filename in JSON_CLEANUP_PATTERNS:
                json_file_path = search_dir / json_filename
                if json_file_path.exists():
                    try:
                        with json_file_path.open() as f:
                            review_data = json.load(f)
                        json_file_found = json_file_path
                        print_status(f"Found JSON review: {json_file_path}")
                        break
                    except (OSError, json.JSONDecodeError) as e:
                        print_warning(f"Could not read {json_file_path}: {e}")
                        continue
            
            if review_data:
                break

        if not review_data:
            # Create a fallback error review
            review_data = {
                "summary": "Review could not be completed - no JSON output found",
                "issues": [{
                    "severity": "warning",
                    "line": 1,
                    "title": "Review Failed", 
                    "message": "Review could not be completed - no JSON output found",
                    "category": "quality",
                    "code_snippet": "",
                    "file": "review_system"
                }],
                "positive_feedback": [],
                "metadata": {
                    "review_focus": "holistic diff analysis",
                    "review_type": "diff_based",
                    "error": "No JSON output found"
                }
            }

        # Clean up the JSON file after reading
        if json_file_found:
            try:
                json_file_found.unlink()
            except:
                pass

        # Add metadata
        review_data["metadata"] = review_data.get("metadata", {})
        review_data["metadata"].update({
            "review_duration_ms": review_duration,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "review_type": "diff_based"
        })

        # Ensure proper statistics structure
        issues = review_data.get("issues", [])
        errors = sum(1 for issue in issues if issue.get("severity") == "error")
        warnings = sum(1 for issue in issues if issue.get("severity") == "warning") 
        notices = sum(1 for issue in issues if issue.get("severity") == "notice")

        review_data["statistics"] = {
            "total_issues": len(issues),
            "errors": errors,
            "warnings": warnings,
            "notices": notices,
            "total_review_time_ms": review_duration,
        }

        # Save the results
        json_file = f"code-reviews/{timestamp}_diff_based_structured.json"
        json_path = project_root / json_file

        with json_path.open("w") as f:
            json.dump(review_data, f, indent=2)

        # Show progress
        issues_count = len(issues)
        duration = review_duration / 1000
        if issues_count > 0:
            print_success(f"✅ Diff review completed ({duration:.1f}s) - {issues_count} issues found")
        else:
            print_success(f"✅ Diff review completed ({duration:.1f}s) - no issues")

        return json_file, timestamp

    except subprocess.TimeoutExpired:
        print_error("Review timeout")
        sys.exit(1)
    except Exception as e:
        print_error(f"Review error: {e}")
        sys.exit(1)
    finally:
        # Keep output files for debugging if enabled
        debug_mode = os.getenv("DEBUG_JSON_PARSING", "false").lower() == "true"
        if not debug_mode:
            try:
                if output_file.exists():
                    output_file.unlink()
            except:
                pass


def main():
    """Main entry point for simple diff-based code review."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("""Simple Diff-Based StreetRace Review

Usage: python simple_diff_review.py [base_ref]

Arguments:
  base_ref    Base git reference for comparison (default: main)

Environment Variables:
  STREETRACE_MODEL      Model to use (default: openai/gpt-4o)
  OPENAI_API_KEY        OpenAI API key
  ANTHROPIC_API_KEY     Anthropic API key

This script implements a simplified holistic diff-based review:
1. Calls StreetRace agent with a simple prompt
2. Agent uses its tools to get git diff and analyze it
3. Agent handles diff trimming and generates structured JSON output
4. Much simpler than the complex per-file orchestration
""")
        return

    project_root = Path(__file__).parent.parent.parent.parent
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "main"
    model = os.getenv("STREETRACE_MODEL", "openai/gpt-4o")

    print_status(f"Starting simple diff-based code review with model: {model}")

    setup_environment(project_root)
    
    try:
        json_file, timestamp = run_simple_diff_review(project_root, model, base_ref)
        print_success(f"✅ Simple diff-based review completed: {json_file}")
    except KeyboardInterrupt:
        print_warning("\n⚠️  Review interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"❌ Review failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()