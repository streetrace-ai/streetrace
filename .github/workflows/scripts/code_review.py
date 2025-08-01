#!/usr/bin/env python3
"""Code review using StreetRace for GitHub Actions workflow.

This module provides automated code review functionality using StreetRace's
code reviewer agent. It handles the complete workflow from change detection
to report generation.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from utils import print_error, print_status, print_success, print_warning


class CodeReviewRunner:
    """Handles the code review workflow."""

    def __init__(self) -> None:
        """Initialize the code review runner."""
        script_dir = Path(__file__).parent.resolve()
        self.project_root = script_dir.parent.parent.parent
        self.model = os.getenv("STREETRACE_MODEL", "openai/gpt-4o")
        self.scripts_dir = self.project_root / ".github/workflows/scripts"
        self._setup_environment()

    def _setup_environment(self) -> None:
        """Set up environment variables and load .env file if present."""
        # Load environment variables from .env if it exists
        env_file = self.project_root / ".env"
        if env_file.exists():
            print_status("Loading environment variables from .env")
            with env_file.open() as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key] = value

        # Set timeout for GitHub Actions environment (in seconds)
        # LiteLLM uses this for HTTP client timeouts
        # Default to 10 minutes for complex reviews
        os.environ.setdefault("HTTPX_TIMEOUT", "600")
        os.environ.setdefault("REQUEST_TIMEOUT", "600")
        os.environ.setdefault("LITELLM_REQUEST_TIMEOUT", "600")

        # StreetRace specific timeout (in milliseconds)
        os.environ.setdefault("STREETRACE_TIMEOUT", "600000")

    def check_prerequisites(self) -> None:
        """Check if all prerequisites are met."""
        print_status("Checking prerequisites...")

        # Check if we're in a git repo
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                check=True,
                capture_output=True,
                cwd=self.project_root,
            )
        except subprocess.CalledProcessError:
            print_error("Not in a git repository")
            sys.exit(1)

        # Check if StreetRace is available
        try:
            subprocess.run(
                ["poetry", "run", "streetrace", "--help"],
                check=True,
                capture_output=True,
                cwd=self.project_root,
            )
        except subprocess.CalledProcessError:
            print_error(
                "StreetRace not available via poetry. Run 'poetry install' first.",
            )
            sys.exit(1)

        # Check for OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            print_error("No OpenAI API key found. Set OPENAI_API_KEY")
            print_status(
                "You can create a .env file in the project root with: OPENAI_API_KEY=your_key_here",
            )
            sys.exit(1)

        print_success("Prerequisites OK")

    def check_for_changes(self) -> None:
        """Check if there are changes to review."""
        print_status("Checking for changes to review...")

        try:
            # Check if we're in the correct branch context
            result = subprocess.run(
                ["git", "diff", "--quiet", "main...HEAD"],
                check=False,
                cwd=self.project_root,
                capture_output=True,
            )

            if result.returncode != 0:
                # There are differences, check if there are files
                result = subprocess.run(
                    ["git", "diff", "main...HEAD", "--name-only"],
                    check=False,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip():
                    print_success("Found changes to review")
                    return

            # Check for staged changes
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                check=False,
                cwd=self.project_root,
                capture_output=True,
            )

            if result.returncode != 0:
                print_success("Found staged changes to review")
                return

            # Check if we have any commits
            try:
                subprocess.run(
                    ["git", "log", "--oneline", "-1"],
                    check=True,
                    capture_output=True,
                    cwd=self.project_root,
                )
                print_success("Will review recent commits")
                return
            except subprocess.CalledProcessError:
                pass

            print_error("No changes found to review")
            sys.exit(1)

        except subprocess.CalledProcessError:
            print_error("Error checking for changes")
            sys.exit(1)


    def run_simple_diff_review(self, timestamp: str) -> None:
        """Run the simplified diff-based review strategy."""
        print_status("🔄 Running simple holistic diff-based AI code review...")

        try:
            # Run simple diff-based review
            subprocess.run(
                ["python3", str(self.scripts_dir / "simple_diff_review.py"), "main"],
                cwd=self.project_root,
                check=True,
                env={**os.environ, "STREETRACE_MODEL": self.model},
            )

            print_success("Simple diff-based review completed!")

            # Find the generated diff-based review
            reviews_dir = self.project_root / "code-reviews"
            diff_json = next(reviews_dir.glob(f"{timestamp}_diff_based_structured.json"), None)

            if not diff_json or not diff_json.exists():
                print_error("Diff-based review output not found")
                sys.exit(1)

            print_success(f"Diff-based review saved: {diff_json.name}")

            # Generate SARIF from diff-based review
            sarif_path = reviews_dir / f"{timestamp}_diff_based_sarif.json"

            try:
                subprocess.run(
                    ["python3", str(self.scripts_dir / "sarif_generator.py"),
                     str(diff_json), str(sarif_path)],
                    check=True,
                    cwd=self.project_root,
                )

                if sarif_path.exists():
                    print_success(f"SARIF file generated: {sarif_path.name}")
                    self._set_github_env_vars(diff_json, sarif_path)

            except subprocess.CalledProcessError as e:
                print_warning(f"SARIF generation failed: {e}")

        except subprocess.CalledProcessError as e:
            print_error(f"Simple diff-based review failed: {e}")
            sys.exit(1)

    def _set_github_env_vars(self, json_file: Path, sarif_file: Path) -> None:
        """Set GitHub Actions environment variables."""
        github_env = os.getenv("GITHUB_ENV")
        if github_env:
            with open(github_env, "a") as f:
                f.write(f"REVIEW_JSON_FILE={json_file}\n")
                f.write(f"REVIEW_SARIF_FILE={sarif_file}\n")

    def run_review(self) -> None:
        """Run the simple diff-based AI code review."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print_status(f"Running simple holistic diff-based AI code review with model: {self.model}")
        self.run_simple_diff_review(timestamp)

    def display_results(self) -> None:
        """Display results summary."""
        print()
        print("==================================")
        print_status("Review completed successfully")

    def run(self) -> None:
        """Run the complete code review workflow."""
        print("🔍 StreetRace Code Review")
        print("==================")

        self.check_prerequisites()
        self.check_for_changes()
        self.run_review()
        self.display_results()

        print_success("Code review completed!")


def show_help() -> None:
    """Show help message."""
    help_text = """Simple Holistic Diff-Based StreetRace Review for GitHub Actions

Usage: python code_review.py [OPTIONS]

Performs automated simple holistic diff-based code review using StreetRace 
with superior contextual understanding and elegant simplicity.

Environment Variables:
  OPENAI_API_KEY        - OpenAI API key (required)
  STREETRACE_MODEL      - Model to use (default: openai/gpt-4o)

Options:
  -h, --help           Show this help message
"""
    print(help_text)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        show_help()
        return

    if len(sys.argv) > 1:
        print_error(f"Unknown option: {sys.argv[1]}")
        show_help()
        sys.exit(1)

    runner = CodeReviewRunner()
    runner.run()


if __name__ == "__main__":
    main()
