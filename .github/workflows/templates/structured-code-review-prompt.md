# StreetRace Code Review Instructions

I need you to conduct a comprehensive code review using the StreetRace Code Reviewer Agent specifically (not the default coder agent). This agent is designed to review ALL file types without filtering.

## IMPORTANT: Use Structured Diff Data

Instead of using git diff commands, I have prepared structured diff data for you to review. This eliminates line number confusion and provides accurate mappings.

## Your Tasks

1. Read the structured diff data from: @{structured_diff_file}
2. This file contains pre-processed changes with accurate line numbers, old/new content, and context
3. Check the 'summary' section for total_files_in_pr (actual PR size) and files_reviewed (filtered for review)
4. Review EVERY file in the structured data regardless of type (Python, shell scripts, YAML, JSON, Markdown, etc.)
5. Focus on meaningful issues: logic errors, security problems, style violations, missing error handling
6. **SECURITY FOCUS**: Actively look for these critical vulnerabilities:
   - SQL injection (string formatting in queries)
   - Command injection (os.system, subprocess with user input)
   - Code injection (eval, exec with user data)
   - Hardcoded credentials (API keys, passwords in code)
   - Path traversal (unvalidated file paths)
   - Unsafe deserialization (pickle.loads, etc.)
   - Missing input validation
   - Broad exception handling hiding errors
7. For new files (many line additions), review the overall purpose, structure, and quality rather than every line
8. For each change, you have:
   - Exact line number in the final file (use the 'line_number' field)
   - The new content that was added/modified  
   - Context lines before and after
   - File path and language information
9. Focus your review on the 'new_content' field of each change
10. **CRITICAL**: Use the provided 'line_number' field EXACTLY as given (do NOT recalculate or guess)
11. Include the exact 'new_content' as the code_snippet in your JSON output
12. **MANDATORY**: The 'line_number' field gives you the accurate line in the final file - use this EXACT number
13. **NEVER** count lines yourself or estimate based on context - always use the provided 'line_number'
14. In your statistics, use total_files_in_pr for 'files_changed' to show the real PR scope
15. Create both output files with proper validation:
   - Structured JSON file: {json_file} (use write_json tool)
   - Markdown report: {markdown_file} (use write_file tool)

## CRITICAL JSON FORMAT REQUIREMENTS

- MANDATORY: Use the write_json tool (NOT write_file) for the structured JSON output
- The write_json tool automatically validates JSON syntax and provides detailed error messages
- NEVER use write_file for JSON files - always use write_json
- Follow this EXACT JSON structure (no missing commas, no trailing commas):

```json
{{
  "summary": "Your review summary text",
  "statistics": {{
    "files_changed": 0,
    "total_issues": 0,
    "errors": 0,
    "warnings": 0,
    "notices": 0
  }},
  "issues": [
    {{
      "severity": "error",
      "file": "path/to/file.py",
      "line": 123,
      "title": "Issue title",
      "message": "Detailed message with escaped quotes if needed",
      "code_snippet": "actual code from new_content field",
      "category": "security"
    }}
  ],
  "positive_feedback": []
}}
```

## VALIDATION RULES

- Severity: ONLY "error", "warning", "notice"
- Category: ONLY "security", "performance", "quality", "testing", "maintainability"  
- Escape quotes in strings: Use \\" not "
- No trailing commas after last array/object elements
- All strings must be properly quoted

## SECURITY VULNERABILITY EXAMPLES

**Always flag these patterns as HIGH SEVERITY ERRORS:**

1. **SQL Injection**: 
   ```python
   query = f"SELECT * FROM users WHERE id = '{{user_id}}'"  # ERROR
   ```

2. **Command Injection**:
   ```python
   os.system(user_input)  # ERROR
   subprocess.call(shell=True, args=user_data)  # ERROR
   ```

3. **Code Injection**:
   ```python
   eval(user_data)  # ERROR
   exec(user_input)  # ERROR
   ```

4. **Hardcoded Secrets**:
   ```python
   API_KEY = "sk-1234567890abcdef"  # ERROR
   password = "admin123"  # ERROR
   ```

5. **Path Traversal**:
   ```python
   open(user_filename, 'r')  # ERROR without validation
   ```

## IMPORTANT GUIDELINES

- Do not skip any file types. Review shell scripts, YAML files, configuration files, and documentation just as thoroughly as Python files.
- The structured diff format eliminates the need for git commands and provides precise line mappings. Use the line_number field directly in your output.
- **PRIORITIZE SECURITY**: Security vulnerabilities should always be marked as "error" severity, not "warning" or "notice".

## TOOL USAGE INSTRUCTIONS

1. For JSON output ({json_file}): Use write_json tool - it validates syntax and prevents errors
2. For Markdown output ({markdown_file}): Use write_file tool - regular text file
3. If write_json fails with validation errors, read the error message carefully and fix the JSON syntax
4. Common JSON errors: missing commas, trailing commas, unescaped quotes, unclosed brackets