#!/usr/bin/env python3
"""Generate GitHub Actions job summary from review JSON."""

import json
import sys


def generate_summary(json_file: str) -> None:
    """Generate summary from review JSON file."""
    try:
        with open(json_file) as f:
            data = json.load(f)
        
        # Print summary
        print("## 📊 AI Code Review Summary")
        print("")
        
        # Check if this is a structured diff file instead of review file
        if "base_ref" in data and "files" in data:
            print("⚠️ This appears to be structured diff data, not review results")
            print("❌ AI review may have failed to generate proper output")
            # Show PR stats from structured diff
            if "summary" in data:
                summary = data["summary"]
                total_files = summary.get("total_files_in_pr", summary.get("total_files", 0))
                reviewed_files = summary.get("files_reviewed", 0)
                print(f"📊 PR has {total_files} files changed, {reviewed_files} were reviewed")
            return
            
        summary = data.get("summary", "No summary available")
        print(summary)
        print("")
        
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
            print("")
            
    except FileNotFoundError:
        print("❌ Review file not found")
    except json.JSONDecodeError:
        print("❌ Invalid JSON format")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 generate_summary.py <review_json_file>")
        sys.exit(1)
    
    generate_summary(sys.argv[1])