#!/usr/bin/env python3
"""Generate GitHub Actions job summary from review JSON."""

import json
import sys
from pathlib import Path

from utils import print_error, print_status


def generate_summary(json_file: str) -> None:
    """Generate summary from review JSON file."""
    file_path = Path(json_file)
    
    if not file_path.exists():
        print_error("Review file not found")
        return
        
    try:
        with file_path.open() as f:
            data = json.load(f)

        # Print summary
        print("## 📊 StreetRace Review Summary")
        print()

        # Check if this is a structured diff file instead of review file
        if "base_ref" in data and "files" in data:
            print_status("⚠️ This appears to be structured diff data, not review results")
            print_error("Review may have failed to generate proper output")
            # Show PR stats from structured diff
            if "summary" in data:
                summary = data["summary"]
                total_files = summary.get("total_files_in_pr", summary.get("total_files", 0))
                reviewed_files = summary.get("files_reviewed", 0)
                print_status(f"📊 PR has {total_files} files changed, {reviewed_files} were reviewed")
            return

        summary = data.get("summary", "No summary available")
        print(summary)
        print()

        # Print statistics
        stats = data.get("statistics", {})
        if stats:
            print("### Statistics")
            print(f"- Files changed: {stats.get('files_changed', 0)}")
            print(f"- Total issues: {stats.get('total_issues', 0)}")

            if stats.get("errors", 0) > 0:
                print(f"  - 🚨 Errors: {stats.get('errors', 0)}")
            if stats.get("warnings", 0) > 0:
                print(f"  - ⚠️ Warnings: {stats.get('warnings', 0)}")
            if stats.get("notices", 0) > 0:
                print(f"  - ℹ️ Notices: {stats.get('notices', 0)}")
            print()

    except json.JSONDecodeError:
        print_error("Invalid JSON format")
    except Exception as e:
        print_error(f"Error: {e}")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 2:
        print_error("Usage: python3 generate_summary.py <review_json_file>")
        sys.exit(1)

    # Show help if requested
    if sys.argv[1] in ["-h", "--help"]:
        print("Generate GitHub Actions job summary from review JSON.")
        print("Usage: python3 generate_summary.py <review_json_file>")
        return

    generate_summary(sys.argv[1])


if __name__ == "__main__":
    main()
