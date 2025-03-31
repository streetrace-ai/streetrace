# Tools Module

This directory contains utility tools for file operations, searching, and command execution.

## Path Management

The `path_utils.py` module provides secure path handling for all tools:

- All paths are normalized to eliminate ambiguities like `..`, `.`, and redundant separators.
- Paths can be either absolute or relative to the work_dir.
- Security checks ensure paths cannot access files outside the work_dir.
- Consistent error handling across all tools.

## Available Tools

- `read_file.py` - Securely read file contents
- `write_file.py` - Securely write content to files
- `read_directory_structure.py` - List directory contents with .gitignore support
- `search.py` - Find text in files matching a glob pattern
- `cli.py` - Execute CLI commands in a secure manner

## Path Security

All tools now enforce path security constraints:
1. Paths are normalized to resolve any `.` or `..` references
2. Both absolute and relative paths are supported
3. Checks ensure no path accesses files outside the working directory
4. Meaningful error messages are provided when security constraints are violated