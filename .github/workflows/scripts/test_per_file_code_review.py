#!/usr/bin/env python3
"""Test version of per-file AI code review - limited to 3 files for testing.

This is a test version that limits the review to 3 files including test_problematic_code.py
to validate the per-file architecture quickly.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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

    def get_file_content(self, file_path: str, ref: str = "HEAD") -> Optional[str]:
        """Get file content at a specific git reference."""
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{file_path}"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except subprocess.CalledProcessError:
            return None

    def get_file_language(self, file_path: str) -> str:
        """Determine the programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.sh': 'bash',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.json': 'json',
            '.md': 'markdown'
        }
        return language_map.get(ext, 'text')

    def generate_changes_summary(self, old_content: Optional[str], new_content: str) -> str:
        """Generate a summary of what changed in the file."""
        if old_content is None:
            return "New file created"
        
        old_lines = old_content.splitlines() if old_content else []
        new_lines = new_content.splitlines()
        
        additions = len(new_lines) - len(old_lines)
        if additions > 0:
            return f"File modified: +{additions} lines"
        elif additions < 0:
            return f"File modified: {additions} lines"
        else:
            return "File modified: content changed"

    def review_file(self, file_path: str, old_content: Optional[str], new_content: str, reviews_dir: Path, timestamp: str, file_index: int) -> Dict:
        """Review a single file and return the review JSON."""
        start_time = time.time()
        
        language = self.get_file_language(file_path)
        changes_summary = self.generate_changes_summary(old_content, new_content)
        
        # Format the prompt with file-specific content
        prompt = self.review_template.format(
            file_path=file_path,
            language=language,
            old_content=old_content or "null",
            new_content=new_content,
            changes_summary=changes_summary
        )
        
        # Create context file in reviews directory
        context_file = reviews_dir / f"{timestamp}_file_{file_index:03d}_context.md"
        with context_file.open('w') as f:
            f.write(prompt)
        
        # Create temp output file for streaming
        output_file = reviews_dir / f"{timestamp}_file_{file_index:03d}_output.txt"
        
        try:
            # Run StreetRace with streaming output using tee (like code_review.py)
            cmd = [
                "poetry", "run", "streetrace",
                f"--model={self.model}",
                "--agent=StreetRace_Code_Reviewer_Agent",
                "--verbose",
                f"--prompt=Please follow the instructions in @{context_file.relative_to(self.project_root)} to review this single file and return ONLY valid JSON."
            ]
            
            # Use shell tee command for real-time streaming like code_review.py
            shell_cmd = " ".join([f'"{arg}"' for arg in cmd]) + f' | tee "{output_file}"'
            
            print_status(f"  Reviewing with streaming output...")
            result_code = subprocess.call(
                shell_cmd,
                shell=True,
                cwd=self.project_root,
                timeout=300  # 5 minute timeout per file
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
            
            # Try to extract JSON from the output
            try:
                # Look for JSON in the output - find the largest complete JSON block
                json_start = output.find('{')
                if json_start >= 0:
                    # Count braces to find the complete JSON
                    brace_count = 0
                    json_end = json_start
                    for i, char in enumerate(output[json_start:], json_start):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                    
                    if json_end > json_start:
                        json_str = output[json_start:json_end]
                        # Clean up any control characters
                        json_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')
                        review_data = json.loads(json_str)
                        
                        # Add metadata
                        review_data['metadata'] = review_data.get('metadata', {})
                        review_data['metadata'].update({
                            'review_duration_ms': review_duration,
                            'model': self.model,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        return review_data
                    else:
                        print_warning(f"  No complete JSON found in output for {file_path}")
                        return self._create_error_review(file_path, language, review_duration, "No complete JSON in output")
                else:
                    print_warning(f"  No JSON found in output for {file_path}")
                    return self._create_error_review(file_path, language, review_duration, "No JSON in output")
                    
            except json.JSONDecodeError as e:
                print_warning(f"  Failed to parse JSON for {file_path}: {e}")
                return self._create_error_review(file_path, language, review_duration, str(e))
                
        except subprocess.TimeoutExpired:
            print_warning(f"  Review timeout for {file_path}")
            return self._create_error_review(file_path, language, 300000, "Review timeout")
        except Exception as e:
            print_error(f"  Review error for {file_path}: {e}")
            return self._create_error_review(file_path, language, review_duration, str(e))
        finally:
            # Clean up temp files but keep context for debugging
            try:
                if output_file.exists():
                    output_file.unlink()
            except:
                pass

    def _create_error_review(self, file_path: str, language: str, duration: int, error: str) -> Dict:
        """Create an error review when the AI review fails."""
        return {
            "file": file_path,
            "summary": f"Review failed: {error}",
            "issues": [{
                "severity": "warning",
                "line": 1,
                "title": "Review Failed",
                "message": f"AI review could not be completed for this file: {error}",
                "category": "quality",
                "code_snippet": ""
            }],
            "positive_feedback": [],
            "metadata": {
                "language": language,
                "review_duration_ms": duration,
                "model": self.model,
                "timestamp": datetime.now().isoformat(),
                "error": error
            }
        }


class TestPerFileCodeReviewer:
    """Test version - main orchestrator for per-file code reviews (limited to 3 files)."""

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

    def get_changed_files(self, base_ref: str = "main") -> List[Dict]:
        """Get list of changed files with their content (LIMITED TO 3 FILES FOR TESTING)."""
        print_status("Discovering changed files...")
        
        try:
            # Get list of changed files
            result = subprocess.run(
                ["git", "diff", f"{base_ref}...HEAD", "--name-status"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode != 0:
                print_error(f"Failed to get changed files: {result.stderr}")
                return []
            
            all_files = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                parts = line.split('\t')
                if len(parts) < 2:
                    continue
                    
                status = parts[0]
                file_path = parts[1]
                
                # Skip deleted files
                if status == 'D':
                    continue
                
                # Get old and new content
                old_content = None
                if status != 'A':  # Not a new file
                    old_content = self.file_reviewer.get_file_content(file_path, base_ref)
                
                # Get new content
                new_file_path = self.project_root / file_path
                if new_file_path.exists():
                    with new_file_path.open('r', encoding='utf-8', errors='ignore') as f:
                        new_content = f.read()
                else:
                    print_warning(f"File not found: {file_path}")
                    continue
                
                all_files.append({
                    'path': file_path,
                    'status': status,
                    'old_content': old_content,
                    'new_content': new_content,
                    'size': len(new_content)
                })
            
            # TESTING: Limit to 3 files including test_problematic_code.py
            test_file = None
            other_files = []
            
            for file_data in all_files:
                if 'test_problematic_code.py' in file_data['path']:
                    test_file = file_data
                else:
                    other_files.append(file_data)
            
            # Take test file + 2 others
            limited_files = []
            if test_file:
                limited_files.append(test_file)
            limited_files.extend(other_files[:2])
            
            print_success(f"TEST MODE: Limited to {len(limited_files)} files (including test_problematic_code.py)")
            for f in limited_files:
                print_status(f"  - {f['path']}")
            
            return limited_files
            
        except Exception as e:
            print_error(f"Error getting changed files: {e}")
            return []

    def prioritize_files(self, files: List[Dict]) -> List[Dict]:
        """Sort files by review priority."""
        def get_priority(file_data: Dict) -> Tuple[int, int, str]:
            path = file_data['path']
            size = file_data['size']
            
            # Test files first (priority 0)
            if 'test' in path.lower():
                return (0, size, path)
            
            # Core application files (priority 1)
            if path.endswith(('.py', '.js', '.ts')):
                return (1, size, path)
            
            # Everything else (priority 2)
            return (2, size, path)
        
        return sorted(files, key=get_priority)

    def review_files(self, files: List[Dict], reviews_dir: Path, timestamp: str) -> List[Path]:
        """Review all files and save individual review JSONs."""
        review_files = []
        total_files = len(files)
        
        print_status(f"🔍 Reviewing {total_files} files...")
        
        for i, file_data in enumerate(files, 1):
            file_path = file_data['path']
            old_content = file_data['old_content']
            new_content = file_data['new_content']
            
            print_status(f"[{i}/{total_files}] Reviewing {file_path}...")
            
            start_time = time.time()
            review_data = self.file_reviewer.review_file(
                file_path, old_content, new_content, reviews_dir, timestamp, i
            )
            duration = time.time() - start_time
            
            # Save individual review
            review_filename = f"{timestamp}_file_{i:03d}_review.json"
            review_file_path = reviews_dir / review_filename
            
            with review_file_path.open('w') as f:
                json.dump(review_data, f, indent=2)
            
            review_files.append(review_file_path)
            
            # Show progress
            issues_count = len(review_data.get('issues', []))
            if issues_count > 0:
                print_success(f"✅ {file_path} ({duration:.1f}s) - {issues_count} issues found")
            else:
                print_success(f"✅ {file_path} ({duration:.1f}s) - no issues")
        
        return review_files

    def aggregate_reviews(self, review_files: List[Path]) -> Dict:
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
                
                file_path = review.get('file', 'unknown')
                issues = review.get('issues', [])
                feedback = review.get('positive_feedback', [])
                metadata = review.get('metadata', {})
                
                # Add file path to each issue
                for issue in issues:
                    issue['file'] = file_path
                    all_issues.append(issue)
                
                positive_feedback.extend(feedback)
                
                file_stats[file_path] = {
                    'issues': len(issues),
                    'duration': metadata.get('review_duration_ms', 0)
                }
                
                total_duration += metadata.get('review_duration_ms', 0)
                
            except Exception as e:
                print_warning(f"Failed to process review file {review_file}: {e}")
        
        # Calculate statistics
        errors = sum(1 for issue in all_issues if issue.get('severity') == 'error')
        warnings = sum(1 for issue in all_issues if issue.get('severity') == 'warning')
        notices = sum(1 for issue in all_issues if issue.get('severity') == 'notice')
        
        return {
            "summary": f"TEST: Per-file code review completed. Analyzed {len(file_stats)} files in {total_duration/1000:.1f} seconds, found {len(all_issues)} total issues across security, quality, and maintainability categories.",
            "statistics": {
                "files_changed": len(file_stats),
                "total_issues": len(all_issues),
                "errors": errors,
                "warnings": warnings,
                "notices": notices,
                "total_review_time_ms": total_duration
            },
            "issues": all_issues,
            "positive_feedback": positive_feedback,
            "file_stats": file_stats
        }

    def run_per_file_review(self, base_ref: str = "main", timestamp: Optional[str] = None) -> Tuple[str, str]:
        """Run the complete per-file review process (TEST VERSION - 3 FILES)."""
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create reviews directory
        reviews_dir = self.project_root / "code-reviews"
        reviews_dir.mkdir(exist_ok=True)
        
        # Get changed files (limited to 3)
        files = self.get_changed_files(base_ref)
        if not files:
            print_error("No files to review")
            sys.exit(1)
        
        # Prioritize files
        files = self.prioritize_files(files)
        
        # Review each file individually
        review_files = self.review_files(files, reviews_dir, timestamp)
        
        # Aggregate results
        aggregated_review = self.aggregate_reviews(review_files)
        
        # Save aggregated results
        json_file = f"code-reviews/{timestamp}_test_per_file_structured.json"
        json_path = self.project_root / json_file
        
        with json_path.open('w') as f:
            json.dump(aggregated_review, f, indent=2)
        
        print_success(f"TEST: Per-file review completed: {json_file}")
        print_status(f"Individual reviews saved: {len(review_files)} files")
        
        return json_file, timestamp


def main():
    """Main entry point for test per-file code review."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("""TEST Per-File AI Code Review

Usage: python test_per_file_code_review.py [base_ref]

Arguments:
  base_ref    Base git reference for comparison (default: main)

This is a TEST version that limits review to 3 files including test_problematic_code.py.
""")
        return
    
    project_root = Path(__file__).parent.parent.parent.parent
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "main"
    model = os.getenv("STREETRACE_MODEL", "openai/gpt-4o")
    
    print_status(f"Starting TEST per-file code review with model: {model}")
    
    reviewer = TestPerFileCodeReviewer(project_root, model)
    try:
        json_file, timestamp = reviewer.run_per_file_review(base_ref)
        print_success(f"✅ TEST per-file review completed: {json_file}")
    except KeyboardInterrupt:
        print_warning("\n⚠️  Review interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"❌ Review failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()