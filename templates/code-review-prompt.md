# Code Review Instructions

You are conducting a code review for a GitHub pull request. You must analyze the git diff and provide feedback in a structured JSON format that can be parsed for GitHub annotations.

## Analysis Steps

1. First, run `git diff main...HEAD --unified=3` to see all changes in the PR with line numbers
2. For each changed file, also run `git diff main...HEAD <filename>` to get precise line context
3. Analyze each changed file for issues
4. For each issue found, identify the exact file path and line number from the NEW file (after changes)
5. Categorize issues by severity: error, warning, or notice

## Output Format

You MUST save your review in TWO files:

### 1. Structured JSON file: `code-reviews/{timestamp}_structured.json`

```json
{
  "summary": "Brief overview of the PR",
  "statistics": {
    "files_changed": 0,
    "additions": 0,
    "deletions": 0,
    "total_issues": 0,
    "errors": 0,
    "warnings": 0,
    "notices": 0
  },
  "issues": [
    {
      "severity": "error|warning|notice",
      "file": "path/to/file.py",
      "line": 42,
      "end_line": 45,
      "title": "Brief issue title",
      "message": "Detailed description of the issue and how to fix it",
      "category": "security|performance|quality|testing|style"
    }
  ],
  "positive_feedback": [
    {
      "file": "path/to/file.py",
      "line": 10,
      "message": "Good practice observed here"
    }
  ]
}
```

### 2. Human-readable markdown file: `code-reviews/{timestamp}.md`

Format the same information as a readable markdown report for developers.

## Issue Categories and Severities

### Error (Must fix before merge)
- Security vulnerabilities
- Breaking changes
- Critical bugs
- Memory leaks
- Data corruption risks

### Warning (Should fix)
- Performance issues
- Code quality problems
- Missing tests
- Technical debt
- Deprecated usage

### Notice (Consider fixing)
- Style violations
- Minor optimizations
- Documentation improvements
- Refactoring opportunities

## Important Requirements

1. **Line numbers must be from the NEW file** (after changes), not the old file
2. Use the actual file paths from the repository
3. Be specific about line numbers - if an issue spans multiple lines, provide both start and end
4. Each issue must have actionable feedback
5. Include positive feedback for good practices
6. Keep messages concise but informative

## Example Issue

```json
{
  "severity": "error",
  "file": "src/api/auth.py",
  "line": 127,
  "end_line": 130,
  "title": "SQL Injection Vulnerability",
  "message": "User input is directly concatenated into SQL query. Use parameterized queries instead: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
  "category": "security"
}
```