# Holistic Diff-Based Code Review Instructions

Review this pull request using a holistic diff-based approach:

## Tasks

1. Use the `execute_cli_command` tool to run: `git diff main...HEAD`
2. If the diff is very large (>100k chars), intelligently trim it while prioritizing security-critical files
3. If you trim the diff, include this exact warning: **"The diff has been trimmed to fit into the context window, please keep the PRs smaller"**
4. Review the entire diff for security vulnerabilities, code quality, and cross-file consistency
5. Use the `write_json` tool to save your review with this structure:

```json
{
  "summary": "Brief review summary of all changes",
  "issues": [
    {
      "severity": "error|warning|notice",
      "line": 42,
      "title": "Issue Title",
      "message": "Detailed description", 
      "category": "security|performance|quality|testing|maintainability",
      "code_snippet": "problematic code",
      "file": "path/to/file"
    }
  ],
  "positive_feedback": ["Good practices found"],
  "metadata": {
    "review_focus": "holistic diff analysis",
    "review_type": "diff_based"
  }
}
```

## Security Focus

Flag these patterns as **"error"** severity:
- SQL injection (string formatting in queries)
- Command injection (os.system, subprocess with user input)
- Hardcoded secrets (API keys, passwords)
- Path traversal (unvalidated file paths)
- Code injection (eval, exec with user data)

## Cross-File Analysis

Look for:
- Consistency across related changes
- API changes properly reflected in all files
- Import/export dependencies maintained
- Configuration changes applied consistently

Execute the review immediately using the available tools.