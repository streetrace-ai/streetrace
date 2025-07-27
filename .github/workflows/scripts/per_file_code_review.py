#!/usr/bin/env python3
"""Per-file AI code review implementation.

This module implements the per-file review architecture as outlined in the
IMPROVED_ARCHITECTURE_PROPOSAL.md document. Each file is reviewed individually
with full context, eliminating token limits and improving review quality.
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
    LANGUAGE_MAP,
    print_error,
    print_status,
    print_success,
    print_warning,
)


class FileReviewer:
    """Handles individual file reviews with {oldContent, newContent} format."""

    def __init__(self, project_root: Path, model: str = "openai/gpt-4o"):
        """Initialize the file reviewer."""
        self.project_root = project_root
        self.model = model
        self.review_template = self._load_per_file_template()

    def _load_per_file_template(self) -> str:
        """Load the per-file review template."""
        template_path = self.project_root / ".github/workflows/templates/per-file-review-prompt.md"
        if not template_path.exists():
            print_error(f"Template not found: {template_path}")
            sys.exit(1)

        with template_path.open() as f:
            return f.read()


    def get_file_content(self, file_path: str, ref: str = "HEAD") -> str | None:
        """Get file content at a specific git reference."""
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{file_path}"],
                check=False, capture_output=True,
                text=True,
                cwd=self.project_root,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except subprocess.CalledProcessError:
            return None

    def get_file_language(self, file_path: str) -> str:
        """Determine the programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        return LANGUAGE_MAP.get(ext, "text")

    def generate_changes_summary(self, old_content: str | None, new_content: str) -> str:
        """Generate a summary of what changed in the file."""
        if old_content is None:
            return "New file created"

        old_lines = old_content.splitlines() if old_content else []
        new_lines = new_content.splitlines()

        additions = len(new_lines) - len(old_lines)
        if additions > 0:
            return f"File modified: +{additions} lines"
        if additions < 0:
            return f"File modified: {additions} lines"
        return "File modified: content changed"

    def add_line_numbers(self, content: str) -> str:
        """Add line numbers to content for accurate review."""
        lines = content.splitlines()
        return "\n".join(f"{i:3d}: {line}" for i, line in enumerate(lines, 1))

    def review_file(self, file_path: str, old_content: str | None, new_content: str, reviews_dir: Path, timestamp: str, file_index: int) -> dict:
        """Review a single file and return the review JSON."""
        start_time = time.time()
        review_duration = 0  # Initialize to prevent unbound variable

        language = self.get_file_language(file_path)
        changes_summary = self.generate_changes_summary(old_content, new_content)

        # Add line numbers to content for accurate review
        numbered_new_content = self.add_line_numbers(new_content)
        numbered_old_content = self.add_line_numbers(old_content) if old_content else "null"

        # Format the prompt with file-specific content
        prompt = self.review_template.format(
            file_path=file_path,
            language=language,
            old_content=numbered_old_content,
            new_content=numbered_new_content,
            changes_summary=changes_summary,
        )

        # Create context file in reviews directory
        context_file = reviews_dir / f"{timestamp}_file_{file_index:03d}_context.md"
        with context_file.open("w") as f:
            f.write(prompt)

        # Create temp output file for streaming
        output_file = reviews_dir / f"{timestamp}_file_{file_index:03d}_output.txt"

        try:
            # Clean up any existing JSON files before review to avoid conflicts
            for pattern in JSON_CLEANUP_PATTERNS:
                for search_dir in [self.project_root, Path.cwd()]:
                    cleanup_file = search_dir / pattern
                    if cleanup_file.exists():
                        try:
                            cleanup_file.unlink()
                        except:
                            pass

            # Run StreetRace with streaming output using tee (like code_review.py)
            cmd = [
                "poetry", "run", "streetrace",
                f"--model={self.model}",
                "--agent=StreetRace_Code_Reviewer_Agent",                
                f"--prompt=Please follow the instructions in @{context_file.relative_to(self.project_root)} to review this single file and return ONLY valid JSON.",
            ]

            # Use shell tee command for real-time streaming like code_review.py
            shell_cmd = " ".join([f'"{arg}"' for arg in cmd]) + f' | tee "{output_file}"'

            print_status("  Reviewing with streaming output...")
            result_code = subprocess.call(
                shell_cmd,
                shell=True,
                cwd=self.project_root,
                timeout=300,  # 5 minute timeout per file
            )

            review_duration = int((time.time() - start_time) * 1000)

            # Read the captured output
            if output_file.exists():
                with output_file.open() as f:
                    output = f.read()
            else:
                print_warning(f"No output file for {file_path}")
                return self._create_error_review(file_path, language, review_duration, "No output file")

            if result_code != 0:
                print_warning(f"  Review process returned exit code {result_code}")
                # Continue anyway - check if we got JSON output

            # Look for JSON files created by StreetRace's write_json tool
            try:
                # Check for common JSON file names that StreetRace creates
                possible_json_files = list(JSON_CLEANUP_PATTERNS)

                # Also search for any *.json files in case AI creates custom names
                for search_dir in [self.project_root, Path.cwd()]:
                    try:
                        for json_file in search_dir.glob("*.json"):
                            if json_file.name not in possible_json_files:
                                possible_json_files.append(json_file.name)
                    except:
                        pass

                review_data = None
                json_file_found = None

                # Look in current directory and project root (AI creates files in working dir)
                search_dirs = [self.project_root, Path.cwd()]

                # Wait a moment for file system to flush
                time.sleep(0.5)

                for search_dir in search_dirs:
                    for json_filename in possible_json_files:
                        json_file_path = search_dir / json_filename
                        if json_file_path.exists():
                            try:
                                with json_file_path.open() as f:
                                    review_data = json.load(f)
                                json_file_found = json_file_path
                                print_status(f"  Found JSON review: {json_file_path}")
                                break
                            except (OSError, json.JSONDecodeError) as e:
                                print_warning(f"  Could not read {json_file_path}: {e}")
                                continue

                    if review_data:
                        break

                if review_data:
                    # Clean up the JSON file after reading
                    if json_file_found:
                        try:
                            json_file_found.unlink()
                        except:
                            pass

                    # Ensure the file path is set correctly
                    review_data["file"] = file_path

                    # Add metadata
                    review_data["metadata"] = review_data.get("metadata", {})
                    review_data["metadata"].update({
                        "review_duration_ms": review_duration,
                        "model": self.model,
                        "timestamp": datetime.now().isoformat(),
                        "source_file": str(json_file_found),
                    })

                    return review_data
                print_warning(f"  No JSON files created by StreetRace for {file_path}")
                return self._create_error_review(file_path, language, review_duration, "No JSON files found")

            except Exception as e:
                print_warning(f"  Error reading JSON files for {file_path}: {e}")
                return self._create_error_review(file_path, language, review_duration, str(e))

        except subprocess.TimeoutExpired:
            print_warning(f"  Review timeout for {file_path}")
            return self._create_error_review(file_path, language, 300000, "Review timeout")
        except Exception as e:
            print_error(f"  Review error for {file_path}: {e}")
            return self._create_error_review(file_path, language, review_duration, str(e))
        finally:
            # Keep output files for debugging if there were parsing issues
            debug_mode = os.getenv("DEBUG_JSON_PARSING", "false").lower() == "true"
            if not debug_mode:
                try:
                    if output_file.exists():
                        output_file.unlink()
                except:
                    pass
            else:
                print_status(f"  Debug mode: keeping output file {output_file}")

    def _create_error_review(self, file_path: str, language: str, duration: int, error: str) -> dict:
        """Create an error review when the review fails."""
        return {
            "file": file_path,
            "summary": f"Review failed: {error}",
            "issues": [{
                "severity": "warning",
                "line": 1,
                "title": "Review Failed",
                "message": f"Review could not be completed for this file: {error}",
                "category": "quality",
                "code_snippet": "",
            }],
            "positive_feedback": [],
            "metadata": {
                "language": language,
                "review_duration_ms": duration,
                "model": self.model,
                "timestamp": datetime.now().isoformat(),
                "error": error,
            },
        }


class PerFileCodeReviewer:
    """Main orchestrator for per-file code reviews."""

    def __init__(self, project_root: Path, model: str = "openai/gpt-4o"):
        """Initialize the per-file code reviewer."""
        self.project_root = project_root
        self.model = model
        self.file_reviewer = FileReviewer(project_root, model)
        self._setup_environment()

    def _setup_environment(self) -> None:
        """Set up environment variables and load .env file if present (from code_review.py)."""
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
        os.environ.setdefault("HTTPX_TIMEOUT", "600")
        os.environ.setdefault("REQUEST_TIMEOUT", "600")
        os.environ.setdefault("LITELLM_REQUEST_TIMEOUT", "600")

        # StreetRace specific timeout (in milliseconds)
        os.environ.setdefault("STREETRACE_TIMEOUT", "600000")

    def get_changed_files(self, base_ref: str = "main") -> list[dict]:
        """Get list of changed files with their content."""
        print_status("Discovering changed files...")

        try:
            # Get list of changed files
            result = subprocess.run(
                ["git", "diff", f"{base_ref}...HEAD", "--name-status"],
                check=False, capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode != 0:
                print_error(f"Failed to get changed files: {result.stderr}")
                return []

            files = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("\t")
                if len(parts) < 2:
                    continue

                status = parts[0]
                file_path = parts[1]

                # Skip deleted files
                if status == "D":
                    continue

                # Get old and new content
                old_content = None
                if status != "A":  # Not a new file
                    old_content = self.file_reviewer.get_file_content(file_path, base_ref)

                # Get new content
                new_file_path = self.project_root / file_path
                if new_file_path.exists():
                    with new_file_path.open("r", encoding="utf-8", errors="ignore") as f:
                        new_content = f.read()
                else:
                    print_warning(f"File not found: {file_path}")
                    continue

                files.append({
                    "path": file_path,
                    "status": status,
                    "old_content": old_content,
                    "new_content": new_content,
                    "size": len(new_content),
                })

            print_success(f"Found {len(files)} files to review")
            return files

        except Exception as e:
            print_error(f"Error getting changed files: {e}")
            return []

    def prioritize_files(self, files: list[dict]) -> list[dict]:
        """Sort files by review priority."""
        def get_priority(file_data: dict) -> tuple[int, int, str]:
            path = file_data["path"]
            size = file_data["size"]

            # Security-critical files first (priority 0)
            if any(keyword in path.lower() for keyword in ["auth", "security", "crypto", "secret", "password"]):
                return (0, size, path)

            # Test files next (priority 1)
            if "test" in path.lower() or path.startswith("tests/"):
                return (1, size, path)

            # Core application files (priority 2)
            if path.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs")):
                return (2, size, path)

            # Configuration and scripts (priority 3)
            if path.endswith((".yml", ".yaml", ".json", ".sh", ".bash")):
                return (3, size, path)

            # Everything else (priority 4)
            return (4, size, path)

        return sorted(files, key=get_priority)

    def review_files(self, files: list[dict], reviews_dir: Path, timestamp: str) -> list[Path]:
        """Review all files and save individual review JSONs."""
        review_files = []
        total_files = len(files)

        print_status(f"🔍 Reviewing {total_files} files...")

        for i, file_data in enumerate(files, 1):
            file_path = file_data["path"]
            old_content = file_data["old_content"]
            new_content = file_data["new_content"]

            print_status(f"[{i}/{total_files}] Reviewing {file_path}...")

            start_time = time.time()
            review_data = self.file_reviewer.review_file(
                file_path, old_content, new_content, reviews_dir, timestamp, i,
            )
            duration = time.time() - start_time

            # Save individual review
            review_filename = f"{timestamp}_file_{i:03d}_review.json"
            review_file_path = reviews_dir / review_filename

            with review_file_path.open("w") as f:
                json.dump(review_data, f, indent=2)

            review_files.append(review_file_path)

            # Show progress
            issues_count = len(review_data.get("issues", []))
            if issues_count > 0:
                print_success(f"✅ {file_path} ({duration:.1f}s) - {issues_count} issues found")
            else:
                print_success(f"✅ {file_path} ({duration:.1f}s) - no issues")

        return review_files

    def aggregate_reviews(self, review_files: list[Path]) -> dict:
        """Aggregate individual file reviews into final structured format."""
        print_status("Aggregating individual reviews...")

        all_issues = []
        positive_feedback = []
        file_stats = {}
        total_duration = 0

        for review_file in review_files:
            try:
                with review_file.open() as f:
                    review = json.load(f)

                file_path = review.get("file", "unknown")
                issues = review.get("issues", [])
                feedback = review.get("positive_feedback", [])
                metadata = review.get("metadata", {})

                # Add file path to each issue (excluding Review Failed issues)
                for issue in issues:
                    # Skip "Review Failed" issues from final aggregation
                    if issue.get("title") == "Review Failed":
                        continue
                    issue["file"] = file_path
                    all_issues.append(issue)

                positive_feedback.extend(feedback)

                file_stats[file_path] = {
                    "issues": len(issues),
                    "duration": metadata.get("review_duration_ms", 0),
                }

                total_duration += metadata.get("review_duration_ms", 0)

            except Exception as e:
                print_warning(f"Failed to process review file {review_file}: {e}")

        # Calculate statistics
        errors = sum(1 for issue in all_issues if issue.get("severity") == "error")
        warnings = sum(1 for issue in all_issues if issue.get("severity") == "warning")
        notices = sum(1 for issue in all_issues if issue.get("severity") == "notice")

        return {
            "summary": f"Per-file code review completed. Analyzed {len(file_stats)} files in {total_duration/1000:.1f} seconds, found {len(all_issues)} total issues across security, quality, and maintainability categories.",
            "statistics": {
                "files_changed": len(file_stats),
                "total_issues": len(all_issues),
                "errors": errors,
                "warnings": warnings,
                "notices": notices,
                "total_review_time_ms": total_duration,
            },
            "issues": all_issues,
            "positive_feedback": positive_feedback,
            "file_stats": file_stats,
        }

    def run_per_file_review(self, base_ref: str = "main", timestamp: str | None = None) -> tuple[str, str]:
        """Run the complete per-file review process."""
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create reviews directory
        reviews_dir = self.project_root / "code-reviews"
        reviews_dir.mkdir(exist_ok=True)

        # Get changed files
        files = self.get_changed_files(base_ref)
        if not files:
            print_error("No files to review")
            sys.exit(1)

        # Prioritize files
        files = self.prioritize_files(files)

        # Apply file limit if configured
        file_limit = os.getenv("STREETRACE_FILE_LIMIT")
        if file_limit is not None:
            try:
                limit = int(file_limit)
                if len(files) > limit:
                    print_status(f"File limit: Limiting review to {limit} files (found {len(files)} total)")
                    files = files[:limit]
            except ValueError:
                print_warning(f"Invalid STREETRACE_FILE_LIMIT value: {file_limit}. Ignoring limit.")

        # Review each file individually
        review_files = self.review_files(files, reviews_dir, timestamp)

        # Aggregate results
        aggregated_review = self.aggregate_reviews(review_files)

        # Save aggregated results
        json_file = f"code-reviews/{timestamp}_per_file_structured.json"
        json_path = self.project_root / json_file

        with json_path.open("w") as f:
            json.dump(aggregated_review, f, indent=2)

        print_success(f"Per-file review completed: {json_file}")
        print_status(f"Individual reviews saved: {len(review_files)} files")

        return json_file, timestamp


def main():
    """Main entry point for per-file code review."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("""Per-File StreetRace Review

Usage: python per_file_code_review.py [base_ref]

Arguments:
  base_ref    Base git reference for comparison (default: main)

Environment Variables:
  STREETRACE_MODEL      Model to use (default: openai/gpt-4o)
  STREETRACE_FILE_LIMIT Maximum files to review (default: unlimited)
  OPENAI_API_KEY        OpenAI API key
  ANTHROPIC_API_KEY     Anthropic API key

This script implements the per-file review architecture:
1. Each file is reviewed individually with full context
2. No token limits or content truncation
3. Individual review JSONs are saved
4. Results are aggregated into final structured format
""")
        return

    project_root = Path(__file__).parent.parent.parent.parent
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "main"
    model = os.getenv("STREETRACE_MODEL", "openai/gpt-4o")

    print_status(f"Starting per-file code review with model: {model}")

    reviewer = PerFileCodeReviewer(project_root, model)
    try:
        json_file, timestamp = reviewer.run_per_file_review(base_ref)
        print_success(f"✅ Per-file review completed: {json_file}")
    except KeyboardInterrupt:
        print_warning("\n⚠️  Review interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"❌ Review failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
