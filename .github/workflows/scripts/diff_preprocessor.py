#!/usr/bin/env python3
"""Preprocess git diff into structured format for accurate AI code review.

This script parses git diff output and creates structured JSON with accurate
line mappings, old/new content, and context - eliminating AI line number guessing.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DiffParser:
    """Parse git diff into structured format with accurate line mappings."""

    def __init__(self, project_root: str) -> None:
        """Initialize diff parser."""
        self.project_root = Path(project_root)

    def run_git_command(self, cmd: List[str]) -> str:
        """Run git command and return output."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Git command failed: {' '.join(cmd)}")
            print(f"Error: {e.stderr}")
            sys.exit(1)

    def get_file_content(self, file_path: str) -> List[str]:
        """Get current file content as list of lines."""
        try:
            full_path = self.project_root / file_path
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.readlines()
        except FileNotFoundError:
            return []
        except UnicodeDecodeError:
            # Skip binary files
            return []

    def parse_diff_header(self, line: str) -> Optional[Tuple[str, str]]:
        """Parse diff header to extract old and new file paths."""
        # Match: +++ b/path/to/file or +++ /dev/null
        if line.startswith('+++'):
            match = re.match(r'\+\+\+ (?:b/)?(.+)', line)
            if match and match.group(1) != '/dev/null':
                return 'new', match.group(1)
        # Match: --- a/path/to/file or --- /dev/null  
        elif line.startswith('---'):
            match = re.match(r'--- (?:a/)?(.+)', line)
            if match and match.group(1) != '/dev/null':
                return 'old', match.group(1)
        return None

    def parse_hunk_header(self, line: str) -> Optional[Tuple[int, int, int, int]]:
        """Parse hunk header: @@ -old_start,old_count +new_start,new_count @@"""
        match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        if match:
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1
            return old_start, old_count, new_start, new_count
        return None

    def extract_context(self, lines: List[str], line_num: int, context_size: int = 3) -> Tuple[List[str], List[str]]:
        """Extract context lines before and after a given line."""
        start_idx = max(0, line_num - context_size - 1)
        end_idx = min(len(lines), line_num + context_size)
        
        before = [line.rstrip() for line in lines[start_idx:line_num-1]]
        after = [line.rstrip() for line in lines[line_num:end_idx]]
        
        return before, after

    def parse_unified_diff(self, diff_output: str) -> List[Dict[str, Any]]:
        """Parse unified diff output into structured format."""
        lines = diff_output.split('\n')
        files = []
        current_file = None
        current_changes = []
        
        old_line_num = 0
        new_line_num = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # File header
            if line.startswith('diff --git'):
                # Save previous file if exists
                if current_file:
                    current_file['changes'] = current_changes
                    files.append(current_file)
                
                # Start new file
                current_file = {
                    'path': '',
                    'change_type': 'modified',
                    'changes': []
                }
                current_changes = []
                
            elif line.startswith('---') or line.startswith('+++'):
                if current_file:
                    header_info = self.parse_diff_header(line)
                    if header_info:
                        file_type, file_path = header_info
                        if file_type == 'new':
                            current_file['path'] = file_path
                            
            elif line.startswith('@@'):
                # Hunk header - reset line counters
                hunk_info = self.parse_hunk_header(line)
                if hunk_info:
                    old_start, old_count, new_start, new_count = hunk_info
                    old_line_num = old_start
                    new_line_num = new_start
                    
            elif line.startswith('+') and not line.startswith('+++'):
                # Added line
                content = line[1:]  # Remove + prefix
                file_lines = self.get_file_content(current_file['path']) if current_file else []
                
                # Get context around this line
                context_before, context_after = self.extract_context(file_lines, new_line_num)
                
                change = {
                    'type': 'addition',
                    'line_number': new_line_num,
                    'old_content': None,
                    'new_content': content.rstrip(),
                    'context_before': context_before[-2:],  # Last 2 lines (reduce context)
                    'context_after': context_after[:2],     # First 2 lines (reduce context)
                    'file_line_number': new_line_num  # Explicit reinforcement of line number
                }
                current_changes.append(change)
                new_line_num += 1
                
            elif line.startswith('-') and not line.startswith('---'):
                # Deleted line (we'll pair with additions for modifications)
                old_line_num += 1
                
            elif line.startswith(' '):
                # Context line
                old_line_num += 1
                new_line_num += 1
                
            i += 1
        
        # Save last file
        if current_file:
            current_file['changes'] = current_changes
            files.append(current_file)
            
        return files

    def detect_modifications(self, changes: List[Dict[str, Any]], file_path: str = '') -> List[Dict[str, Any]]:
        """Detect modifications by pairing deletions with additions."""
        additions = [change for change in changes if change['type'] == 'addition']
        deletions = [change for change in changes if change['type'] == 'deletion']
        
        # If we have only additions and many of them, this is likely a new file
        # For test files, show all content to enable security review
        # For other new files, summarize to avoid overwhelming the AI
        if len(additions) > 10 and len(deletions) == 0:
            # Check if this is a test file - if so, don't truncate
            is_test_file = 'test_' in file_path or '_test' in file_path or '/test' in file_path
            
            if is_test_file:
                # For test files, return all changes to enable security review
                return additions
            
            # This appears to be a new file - summarize it
            first_lines = additions[:5]  # Show first 5 lines for context
            last_lines = additions[-2:] if len(additions) > 5 else []
            
            summary_changes = first_lines.copy()
            if len(additions) > 7:  # If more than 7 lines, add summary
                summary_changes.append({
                    'type': 'summary',
                    'line_number': additions[5]['line_number'] if len(additions) > 5 else 1,
                    'old_content': None,
                    'new_content': f"... ({len(additions) - 7} more lines) ...",
                    'context_before': [],
                    'context_after': [],
                    'file_line_number': additions[5]['line_number'] if len(additions) > 5 else 1
                })
                summary_changes.extend(last_lines)
            
            return summary_changes
        
        # For actual modifications (mix of additions/deletions) or small files, return all additions
        return additions

    def should_skip_file(self, file_path: str) -> bool:
        """Determine if a file should be skipped for size/relevance reasons."""
        path = Path(file_path)
        
        # Skip only truly non-essential files for review
        skip_patterns = [
            # Generated/built files
            'package-lock.json', 'yarn.lock', 'poetry.lock', 'Pipfile.lock',
            '.pyc', '.pyo', '.so', '.dylib', '.dll',
            
            # Large data files (but keep small JSON configs)
            '.csv', '.xml', '.log',
            
            # Binary files
            '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip'
        ]
        
        # Check file extension
        if any(file_path.endswith(pattern) for pattern in skip_patterns):
            return True
            
        # Check file size (skip very large files)
        try:
            full_path = Path(file_path)
            if full_path.exists() and full_path.stat().st_size > 50000:  # 50KB limit
                return True
        except:
            pass
            
        return False

    def get_changed_files(self, base_ref: str = "main", max_files: int = 20) -> List[Dict[str, Any]]:
        """Get changed files with structured diff data, filtered for context size."""
        # Get the unified diff
        diff_cmd = ["git", "diff", f"{base_ref}...HEAD", "--unified=8"]
        diff_output = self.run_git_command(diff_cmd)
        
        if not diff_output.strip():
            return []
        
        # Parse the diff
        files = self.parse_unified_diff(diff_output)
        
        # Filter and enhance data
        enhanced_files = []
        total_changes = 0
        
        # Prioritize test files by sorting them first
        def sort_priority(file_data):
            path = file_data.get('path', '')
            # Test files get priority 0, others get priority 1  
            is_test = 'test_' in path or '_test' in path or '/test' in path
            return (0 if is_test else 1, path)
        
        files_sorted = sorted(files, key=sort_priority)
        
        for file_data in files_sorted:
            if file_data['path'] and file_data['changes']:
                # Skip non-essential files
                if self.should_skip_file(file_data['path']):
                    continue
                    
                # Detect file type
                file_path = Path(file_data['path'])
                file_data['language'] = self.detect_language(file_path)
                file_data['changes'] = self.detect_modifications(file_data['changes'], file_data['path'])
                
                if file_data['changes']:
                    # Limit changes per file to manage size
                    if len(file_data['changes']) > 100:
                        file_data['changes'] = file_data['changes'][:100]
                        file_data['truncated'] = True
                    
                    enhanced_files.append(file_data)
                    total_changes += len(file_data['changes'])
                    
                    # Stop if we have too many files or changes
                    if len(enhanced_files) >= max_files or total_changes > 500:
                        break
        
        return enhanced_files
    
    def get_total_files_changed(self, base_ref: str = "main") -> int:
        """Get total number of files changed in PR (before filtering)."""
        try:
            result = self.run_git_command(["git", "diff", "--name-only", f"{base_ref}...HEAD"])
            return len([f for f in result.strip().split('\n') if f.strip()])
        except:
            return 0

    def detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        extension_map = {
            '.py': 'python',
            '.js': 'javascript', 
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.rs': 'rust',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.sh': 'shell',
            '.bash': 'shell',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.md': 'markdown',
            '.sql': 'sql'
        }
        return extension_map.get(file_path.suffix.lower(), 'text')

    def generate_structured_diff(self, base_ref: str = "main", output_file: Optional[str] = None, max_files: int = 20) -> Dict[str, Any]:
        """Generate structured diff data with filtering for context size management."""
        # Get total files changed (before filtering)
        total_files_in_pr = self.get_total_files_changed(base_ref)
        
        files = self.get_changed_files(base_ref, max_files)
        
        # Calculate statistics
        total_changes = sum(len(f['changes']) for f in files)
        truncated_files = sum(1 for f in files if f.get('truncated', False))
        
        structured_data = {
            'summary': {
                'base_ref': base_ref,
                'total_files_in_pr': total_files_in_pr,  # Real number from git
                'files_reviewed': len(files),            # Number actually reviewed
                'total_changes': total_changes,
                'languages': list(set(f['language'] for f in files)),
                'truncated_files': truncated_files,
                'filtering_applied': True,
                'max_files_limit': max_files
            },
            'files': files
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(structured_data, f, indent=2)
            print(f"✅ Structured diff saved to: {output_file}")
            print(f"📊 Processed {len(files)} files with {total_changes} changes")
            if truncated_files > 0:
                print(f"⚠️  {truncated_files} files were truncated to manage size")
        
        return structured_data


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Parse git diff into structured format for AI code review"
    )
    parser.add_argument(
        "--base-ref", 
        default="main", 
        help="Base reference for diff (default: main)"
    )
    parser.add_argument(
        "--output", 
        help="Output file for structured diff JSON"
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=20,
        help="Maximum number of files to process (default: 20)"
    )
    
    args = parser.parse_args()
    
    processor = DiffParser(args.project_root)
    structured_data = processor.generate_structured_diff(args.base_ref, args.output, args.max_files)
    
    if not args.output:
        print(json.dumps(structured_data, indent=2))
    
    print(f"📊 Found {len(structured_data['files'])} files with {structured_data['summary']['total_changes']} changes")


if __name__ == "__main__":
    main()