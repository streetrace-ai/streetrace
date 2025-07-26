#!/usr/bin/env python3
"""Parse structured AI code review JSON and output GitHub annotations.

This script converts the structured JSON review format into GitHub Actions
annotation commands that will display inline in the PR diff view.
"""

import argparse
import json
import sys
from typing import Any


def load_review_json(file_path: str) -> dict[str, Any]:
    """Load and parse the review JSON file."""
    try:
        with open(file_path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Review file not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in review file: {e}")
        sys.exit(1)


def format_github_annotation(issue: dict[str, Any]) -> str:
    """Format an issue as a GitHub annotation command."""
    severity = issue.get("severity", "notice")
    file_path = issue.get("file", "")
    line = issue.get("line", 1)
    end_line = issue.get("end_line", line)
    title = issue.get("title", "Code Review Issue")
    message = issue.get("message", "")
    code_snippet = issue.get("code_snippet", "")
    category = issue.get("category", "general")

    # GitHub annotation format
    # ::severity file=path,line=X,endLine=Y,title=Title::Message

    # Add code snippet for debugging if available
    if code_snippet:
        message = f"Code: `{code_snippet}`\n\n{message}"

    # Escape special characters in title and message
    title = title.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    # Build the annotation
    annotation = f"::{severity} file={file_path},line={line}"

    if end_line != line:
        annotation += f",endLine={end_line}"

    annotation += f",title=[{category.upper()}] {title}::{message}"

    return annotation


def output_github_summary(review: dict[str, Any]) -> None:
    """Output a summary for the GitHub Actions job summary."""
    summary = review.get("summary", "No summary provided")
    stats = review.get("statistics", {})

    print("\n## 📊 Code Review Summary\n")
    print(f"{summary}\n")

    if stats:
        print("### Statistics")
        print(f"- Files changed: {stats.get('files_changed', 0)}")
        print(f"- Lines added: {stats.get('additions', 0)}")
        print(f"- Lines removed: {stats.get('deletions', 0)}")
        print(f"- Total issues: {stats.get('total_issues', 0)}")

        if stats.get("errors", 0) > 0:
            print(f"  - 🚨 Errors: {stats.get('errors', 0)}")
        if stats.get("warnings", 0) > 0:
            print(f"  - ⚠️  Warnings: {stats.get('warnings', 0)}")
        if stats.get("notices", 0) > 0:
            print(f"  - ℹ️  Notices: {stats.get('notices', 0)}")

    # Add positive feedback summary
    positive_feedback = review.get("positive_feedback", [])
    if positive_feedback:
        print("\n### ✅ Positive Observations")
        print(f"Found {len(positive_feedback)} examples of good practices")


def main():
    parser = argparse.ArgumentParser(
        description="Parse AI review and generate GitHub annotations",
    )
    parser.add_argument("review_file", help="Path to the structured review JSON file")
    parser.add_argument(
        "--summary-file", help="Path to output summary markdown (for job summary)",
    )
    parser.add_argument(
        "--annotations-only",
        action="store_true",
        help="Only output annotations, no summary",
    )

    args = parser.parse_args()

    # Load the review
    review = load_review_json(args.review_file)

    # Output annotations for each issue
    issues = review.get("issues", [])
    annotations_count = 0

    for issue in issues:
        # Skip "Review Failed" issues - they're not helpful annotations
        if issue.get('title') == "Review Failed":
            continue
            
        annotation = format_github_annotation(issue)
        print(annotation)
        annotations_count += 1

    # Output summary if requested
    if not args.annotations_only:
        if args.summary_file:
            # Redirect stdout to summary file
            original_stdout = sys.stdout
            with open(args.summary_file, "w") as f:
                sys.stdout = f
                output_github_summary(review)
            sys.stdout = original_stdout
        else:
            # Output to stderr so it doesn't interfere with annotations
            original_stdout = sys.stdout
            sys.stdout = sys.stderr
            output_github_summary(review)
            sys.stdout = original_stdout

    # Exit with non-zero if there are errors (excluding Review Failed issues)
    errors_count = sum(1 for issue in issues 
                      if issue.get("severity") == "error" and issue.get("title") != "Review Failed")
    if errors_count > 0:
        sys.stderr.write(f"\n❌ Found {errors_count} error(s) that must be fixed\n")
        sys.exit(1)
    elif annotations_count > 0:
        sys.stderr.write(f"\n✅ Review complete: {annotations_count} issue(s) found\n")
    else:
        sys.stderr.write("\n✅ Review complete: No issues found!\n")


if __name__ == "__main__":
    main()
