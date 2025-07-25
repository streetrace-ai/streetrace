# Code Review Instructions

You must complete this review quickly to avoid timeout. Analyze the git diff and provide structured JSON feedback.

## Quick Analysis Steps

1. Run `git diff main...HEAD --name-status` to see changed files
2. Skip test files, documentation, and minor changes
3. For TOP 3-5 most important files only, run `git diff main...HEAD <filename>`
4. Look ONLY for critical issues:
   - Security vulnerabilities (SQL injection, XSS, etc.)
   - Obvious bugs or breaking changes
   - Major code duplication (entire functions copied)
5. Get line numbers from the diff output
6. STOP analysis after 5 minutes to ensure completion

## Output Format

You MUST save your review in TWO files:

### 1. Structured JSON file: `code-reviews/{timestamp}_structured.json`

Keep it simple - focus on critical issues only:

```json
{
  "summary": "One sentence summary",
  "statistics": {
    "files_changed": 0,
    "total_issues": 0,
    "errors": 0,
    "warnings": 0
  },
  "issues": [
    {
      "severity": "error|warning",
      "file": "path/to/file.py",
      "line": 42,
      "title": "Brief issue title",
      "message": "What's wrong and how to fix it",
      "category": "security|quality|performance"
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
- Significant code duplication (e.g., copy-pasted functions)
- Violations of DRY principle

### Notice (Consider fixing)
- Style violations
- Minor optimizations
- Documentation improvements
- Refactoring opportunities
- Code that could be extracted into reusable functions
- Hard-coded values that should be parameterized
- Repeated patterns that could use loops or higher-order functions
- Similar code blocks that could be consolidated

## Important Requirements

1. **Be time-efficient** - This review has a 10-minute time limit
2. **Prioritize critical issues** - Focus on errors and significant warnings first
3. **Line numbers must be from the NEW file** (after changes), not the old file
4. Use the actual file paths from the repository
5. Keep feedback concise and actionable
6. Skip minor style issues unless they significantly impact readability

## Example Issues

### Security Issue
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

### Code Duplication Issue
```json
{
  "severity": "warning",
  "file": "src/utils/validators.py",
  "line": 45,
  "end_line": 67,
  "title": "Duplicate Validation Logic",
  "message": "This email validation logic is duplicated from lines 12-34. Extract into a shared validate_email() function to follow DRY principle",
  "category": "quality"
}
```

### Parameterization Opportunity
```json
{
  "severity": "notice",
  "file": "src/config/settings.py",
  "line": 89,
  "title": "Hard-coded Configuration Value",
  "message": "The timeout value '30' is hard-coded in multiple places (lines 89, 134, 201). Consider extracting to a DEFAULT_TIMEOUT constant",
  "category": "quality"
}
```