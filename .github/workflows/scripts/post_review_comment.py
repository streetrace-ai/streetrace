#!/usr/bin/env python3
"""Posts AI code review results as GitHub PR comments.

This module handles posting code review results to GitHub PR comments,
with support for updating existing comments and truncating long content.
"""

import os
import subprocess
import sys
from pathlib import Path


class GitHubCommentPoster:
    """Handles posting and updating GitHub PR comments."""

    def __init__(self) -> None:
        """Initialize the comment poster with environment variables."""
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.pr_number = os.getenv("PR_NUMBER", "")
        self.github_repository = os.getenv("GITHUB_REPOSITORY", "")

        # Optional context variables
        self.pr_title = os.getenv("PR_TITLE", "")
        self.pr_author = os.getenv("PR_AUTHOR", "")
        self.base_branch = os.getenv("BASE_BRANCH", "main")
        self.head_branch = os.getenv("HEAD_BRANCH", "")

        # Configuration
        self.comment_prefix = "🤖 **AI Code Review**"
        self.max_comment_length = 65000  # GitHub comment limit is ~65k characters

    def validate_environment(self) -> None:
        """Validate required environment variables."""
        missing_vars = []

        if not self.github_token:
            missing_vars.append("GITHUB_TOKEN")

        if not self.pr_number:
            missing_vars.append("PR_NUMBER")

        if not self.github_repository:
            missing_vars.append("GITHUB_REPOSITORY")

        if missing_vars:
            print(
                f"Error: Missing required environment variables: {', '.join(missing_vars)}",
                file=sys.stderr,
            )
            print(file=sys.stderr)
            self.show_usage()
            sys.exit(1)

        # Validate GitHub CLI is available
        try:
            subprocess.run(["gh", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(
                "Error: GitHub CLI (gh) is not installed or not in PATH",
                file=sys.stderr,
            )
            print("Please install GitHub CLI: https://cli.github.com/", file=sys.stderr)
            sys.exit(1)

    def validate_review_file(self, review_file: str) -> bool:
        """Validate that the review file exists and is readable."""
        file_path = Path(review_file)

        if not file_path.exists():
            print(f"Error: Review file '{review_file}' does not exist", file=sys.stderr)
            sys.exit(1)

        if not file_path.is_file():
            print(f"Error: '{review_file}' is not a file", file=sys.stderr)
            sys.exit(1)

        try:
            file_path.read_text(encoding="utf-8")
        except (PermissionError, UnicodeDecodeError) as e:
            print(
                f"Error: Review file '{review_file}' is not readable: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

        if file_path.stat().st_size == 0:
            print(f"Warning: Review file '{review_file}' is empty", file=sys.stderr)
            return False

        return True

    def format_review_comment(self, review_file: str) -> str:
        """Format the review content for a GitHub comment."""
        # Read the review content
        review_content = Path(review_file).read_text(encoding="utf-8")

        # Start building the comment
        comment_body = f"{self.comment_prefix}\n\n"

        # Add PR context if available
        context_parts = []
        if self.pr_title:
            context_parts.append(f"- **Title:** {self.pr_title}")
        if self.pr_author:
            context_parts.append(f"- **Author:** @{self.pr_author}")
        if self.base_branch and self.head_branch:
            context_parts.append(
                f"- **Branch:** `{self.base_branch}` ← `{self.head_branch}`",
            )

        if context_parts:
            comment_body += "**Pull Request Context:**\n"
            comment_body += "\n".join(context_parts) + "\n\n"

        # Add the AI review content
        comment_body += f"**Review Results:**\n\n{review_content}\n\n"
        comment_body += "---\n"
        comment_body += "*This review was generated automatically using StreetRace AI. Please use your judgment when addressing the feedback.*"

        # Check comment length and truncate if necessary
        if len(comment_body) > self.max_comment_length:
            print(
                f"Warning: Comment length ({len(comment_body)} chars) exceeds GitHub limit ({self.max_comment_length} chars)",
                file=sys.stderr,
            )
            print("Truncating comment...", file=sys.stderr)

            # Preserve footer
            footer = (
                "\n\n---\n"
                "*This review was generated automatically using StreetRace AI. Please use your judgment when addressing the feedback.*\n"
                "*Note: Review was truncated due to length limits.*"
            )

            available_length = self.max_comment_length - len(footer)
            comment_body = comment_body[:available_length] + footer

        return comment_body

    def find_existing_comment(self) -> str | None:
        """Find existing AI review comment ID."""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    self.pr_number,
                    "--json",
                    "comments",
                    "--jq",
                    f'.comments[] | select(.body | startswith("{self.comment_prefix}")) | .id',
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            comment_ids = result.stdout.strip().split("\n")
            return comment_ids[0] if comment_ids and comment_ids[0] else None

        except subprocess.CalledProcessError:
            return None

    def create_new_comment(self, comment_body: str) -> None:
        """Create a new PR comment."""
        try:
            process = subprocess.run(
                ["gh", "pr", "comment", self.pr_number, "--body-file", "-"],
                input=comment_body,
                text=True,
                check=True,
            )

            print(
                f"Successfully posted AI review comment to PR #{self.pr_number}",
                file=sys.stderr,
            )

        except subprocess.CalledProcessError:
            print(
                f"Error: Failed to post comment to PR #{self.pr_number}",
                file=sys.stderr,
            )
            sys.exit(1)

    def update_existing_comment(self, comment_id: str, comment_body: str) -> bool:
        """Update an existing comment. Returns True if successful."""
        try:
            process = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{self.github_repository}/issues/comments/{comment_id}",
                    "--method",
                    "PATCH",
                    "--field",
                    "body=-",
                ],
                input=comment_body,
                text=True,
                check=True,
                capture_output=True,
            )

            print(
                f"Successfully updated AI review comment (ID: {comment_id})",
                file=sys.stderr,
            )
            return True

        except subprocess.CalledProcessError:
            print(
                "Error: Failed to update existing comment. Creating new comment...",
                file=sys.stderr,
            )
            return False

    def post_comment(self, comment_body: str) -> None:
        """Post or update a comment."""
        # Check if there's an existing AI review comment
        existing_comment_id = self.find_existing_comment()

        if existing_comment_id:
            print(
                f"Updating existing AI review comment (ID: {existing_comment_id})...",
                file=sys.stderr,
            )
            if not self.update_existing_comment(existing_comment_id, comment_body):
                # Fall back to creating new comment
                self.create_new_comment(comment_body)
        else:
            print("Creating new AI review comment...", file=sys.stderr)
            self.create_new_comment(comment_body)

    def authenticate_github(self) -> None:
        """Authenticate with GitHub CLI."""
        print("Authenticating with GitHub...", file=sys.stderr)

        try:
            # Check if already authenticated
            subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Authenticate using token
            process = subprocess.run(
                ["gh", "auth", "login", "--with-token"],
                input=self.github_token,
                text=True,
                check=True,
            )

    def post_review(self, review_file: str) -> None:
        """Main method to post review comment."""
        # Validate environment and inputs
        self.validate_environment()

        # Handle empty review file
        if not self.validate_review_file(review_file):
            print("Creating placeholder comment for empty review...", file=sys.stderr)
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".txt",
            ) as f:
                f.write("No significant issues found in the code changes.")
                review_file = f.name

        # Authenticate with GitHub
        self.authenticate_github()

        # Format and post the comment
        comment_body = self.format_review_comment(review_file)

        print(f"Posting review comment to PR #{self.pr_number}...", file=sys.stderr)
        self.post_comment(comment_body)

        print("AI code review comment posted successfully!", file=sys.stderr)

    @staticmethod
    def show_usage() -> None:
        """Show usage information."""
        usage_text = """Usage: python post_review_comment.py <review_file>

Posts AI code review results as GitHub PR comments.

Arguments:
    review_file    Path to file containing the AI review results

Environment Variables (required):
    GITHUB_TOKEN   GitHub token with pull request write permissions
    PR_NUMBER      Pull request number
    GITHUB_REPOSITORY  Repository in format owner/repo

Environment Variables (optional):
    PR_TITLE       Pull request title
    PR_AUTHOR      Pull request author
    BASE_BRANCH    Base branch name
    HEAD_BRANCH    Head branch name

Examples:
    python post_review_comment.py /tmp/review-results.txt
    GITHUB_TOKEN=${{secrets.GITHUB_TOKEN}} PR_NUMBER=123 python post_review_comment.py review.txt
"""
        print(usage_text)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Error: Exactly one argument (review file) is required", file=sys.stderr)
        print(file=sys.stderr)
        GitHubCommentPoster.show_usage()
        sys.exit(1)

    review_file = sys.argv[1]

    # Show help if requested
    if review_file in ["-h", "--help"]:
        GitHubCommentPoster.show_usage()
        return

    poster = GitHubCommentPoster()
    poster.post_review(review_file)


if __name__ == "__main__":
    main()
