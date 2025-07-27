# Individual File Code Review

You are conducting a focused code review on a single file. Review the changes with full attention and context.

## Review Instructions

1. **Analyze the file content**: You have the complete old and new content for focused analysis
2. **Security First**: Look for critical vulnerabilities:
   - SQL injection (string formatting in queries)
   - Command injection (os.system, subprocess with user input)  
   - Code injection (eval, exec with user data)
   - Hardcoded credentials (API keys, passwords)
   - Path traversal (unvalidated file paths)
   - Unsafe deserialization
   - Missing input validation

3. **Quality Assessment**: Check for:
   - Logic errors and edge cases
   - Error handling and exception management
   - Code style and maintainability
   - Performance considerations
   - Testing coverage

4. **Output Format**: Use the write_json tool to save your review as a JSON file with this exact structure:
```json
{{
  "file": "path/to/file",
  "summary": "Brief review summary for this file",
  "issues": [
    {{
      "severity": "error|warning|notice",
      "line": 42,
      "title": "Issue Title",
      "message": "Detailed description",
      "category": "security|performance|quality|testing|maintainability",
      "code_snippet": "problematic code"
    }}
  ],
  "positive_feedback": ["Good practices found"],
  "metadata": {{
    "language": "python",
    "review_focus": "security and quality"
  }}
}}
```

## Security Vulnerability Examples

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

## File to Review

**File Path**: {file_path}
**Language**: {language}
**Changes Made**: {changes_summary}

---

## REVIEW THIS NEW CONTENT:

**IMPORTANT: Line numbers must match the exact line numbers below:**

{new_content}

---

## Context - Old Content (for reference only):
{old_content}

## CRITICAL REQUIREMENTS

- Use the write_json tool to save your review - do NOT print JSON to stdout
- Use exact field names and structure shown above
- Security vulnerabilities MUST be marked as "error" severity
- **IMPORTANT**: Line numbers must refer to the NEW CONTENT ONLY (ignore old content)
- **IMPORTANT**: Count line numbers starting from 1 in the NEW CONTENT section
- Include actual problematic code in code_snippet field  
- Use a descriptive filename like "review_output.json" or "file_review.json"

Please provide a thorough review focusing on security vulnerabilities and code quality issues. Save the results using the write_json tool.