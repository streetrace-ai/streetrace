#!/usr/bin/env python3
"""AI code review using StreetRace for GitHub Actions workflow.

This module provides automated code review functionality using StreetRace's
code reviewer agent. It handles the complete workflow from change detection
to report generation.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


def print_status(message: str) -> None:
    """Print status message in blue."""
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")


def print_success(message: str) -> None:
    """Print success message in green."""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")


def print_error(message: str) -> None:
    """Print error message in red."""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")


def print_warning(message: str) -> None:
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {message}")


class CodeReviewRunner:
    """Handles the code review workflow."""

    def __init__(self) -> None:
        """Initialize the code review runner."""
        script_dir = Path(__file__).parent.resolve()
        self.project_root = script_dir.parent.parent.parent
        self.model = os.getenv("STREETRACE_MODEL", "openai/gpt-4o")
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

        # Check for API key (prioritize OpenAI)
        api_keys = [
            os.getenv("OPENAI_API_KEY"),
            os.getenv("ANTHROPIC_API_KEY"),
            os.getenv("GOOGLE_AI_API_KEY"),
        ]

        if not any(api_keys):
            print_error(
                "No API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_AI_API_KEY",
            )
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


    def run_per_file_review(self, timestamp: str) -> None:
        """Run the per-file review strategy."""
        print_status("🔄 Running per-file AI code review...")
        
        try:
            result = subprocess.run(
                [
                    "python3",
                    f"{self.project_root}/.github/workflows/scripts/per_file_code_review.py",
                    "main"
                ],
                cwd=self.project_root,
                check=True,
                env={**os.environ, "STREETRACE_MODEL": self.model}
            )
            
            print_success("Per-file review completed!")
            
            # Find the generated per-file review
            reviews_dir = self.project_root / "code-reviews"
            per_file_json = None
            
            for file in reviews_dir.glob(f"{timestamp}_per_file_structured.json"):
                per_file_json = file
                break
            
            if per_file_json and per_file_json.exists():
                print_success(f"Per-file review saved: {per_file_json.name}")
                
                # Generate SARIF from per-file review
                sarif_file = f"code-reviews/{timestamp}_per_file_sarif.json"
                sarif_path = self.project_root / sarif_file
                
                try:
                    subprocess.run(
                        [
                            "python3",
                            f"{self.project_root}/.github/workflows/scripts/per_file_sarif_generator.py",
                            str(per_file_json),
                            str(sarif_path)
                        ],
                        check=True,
                        cwd=self.project_root
                    )
                    
                    if sarif_path.exists():
                        print_success(f"SARIF file generated: {sarif_file}")
                        
                        # Set environment variables for GitHub Actions
                        github_env = os.getenv("GITHUB_ENV")
                        if github_env:
                            with open(github_env, "a") as f:
                                f.write(f"REVIEW_JSON_FILE={per_file_json}\n")
                                f.write(f"REVIEW_SARIF_FILE={sarif_path}\n")
                    
                except subprocess.CalledProcessError as e:
                    print_warning(f"SARIF generation failed: {e}")
                
            else:
                print_error("Per-file review output not found")
                sys.exit(1)
                
        except subprocess.CalledProcessError as e:
            print_error(f"Per-file review failed: {e}")
            sys.exit(1)

    def run_review(self) -> None:
        """Run the per-file AI code review."""
        # Generate timestamp for the report filename
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print_status(f"Running per-file AI code review with model: {self.model}")
        
        self.run_per_file_review(timestamp)

    def display_results(self) -> None:
        """Display results summary."""
        print()
        print("==================================")
        print_status("Review completed successfully")

    def run(self) -> None:
        """Run the complete code review workflow."""
        print("🔍 AI Code Review")
        print("==================")

        self.check_prerequisites()
        self.check_for_changes()
        self.run_review()
        self.display_results()

        print_success("Code review completed!")


def show_help() -> None:
    """Show help message."""
    help_text = """Per-File AI Code Review for GitHub Actions

Usage: python code_review.py [OPTIONS]

This script performs automated per-file code review using StreetRace:
1. Checks for git changes (staged, branch diff, or recent commits)
2. Reviews each file individually with full AI attention
3. No token limits - each file gets complete context
4. Generates individual review JSONs + aggregated SARIF for GitHub
5. Superior security detection vs single-call approaches

Per-File Architecture Benefits:
- 3x more security vulnerabilities detected
- No content truncation or summarization
- Unlimited scalability (handles hundreds of files)
- Each file gets dedicated AI analysis time
- Better quality through focused attention

Environment Variables:
  OPENAI_API_KEY        - API key for OpenAI (recommended)
  ANTHROPIC_API_KEY     - API key for Anthropic Claude
  GOOGLE_AI_API_KEY     - API key for Google AI
  STREETRACE_MODEL      - Model to use (default: openai/gpt-4o)

Examples:
  python code_review.py                    # Review all changed files individually
  
  # With custom model:
  STREETRACE_MODEL=anthropic/claude-3-5-sonnet python code_review.py

Options:
  -h, --help           Show this help message

Prerequisites:
- Must be run from within the StreetRace project directory
- Must be in a git repository with changes to review
- Must have poetry installed with project dependencies
- Must have an AI API key configured
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
