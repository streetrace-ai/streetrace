# Code Review Instructions

You are conducting a code review for a pull request or code changes.

## MANDATORY FIRST STEPS

BEFORE doing anything else, you MUST:
1. **Read README.md** - Use read_file tool to read README.md first
2. **Read COMPONENTS.md** - Use read_file tool to read COMPONENTS.md second

Do not proceed until you have read both files!

## Your Task

After reading the documentation:
1. **Analyze the changes**: Use git commands to find what files have changed and review the differences
2. **Focus on key areas**:
   - Security vulnerabilities (hardcoded secrets, injection risks, unsafe operations)
   - Syntax errors and logic issues
   - Best practices violations
   - Code quality and maintainability

3. **Provide a summary**: At the end, print a clear summary of your findings

## Instructions

1. MANDATORY: First, read README.md using read_file tool
2. MANDATORY: Second, read COMPONENTS.md using read_file tool
3. Then, determine what changes need to be reviewed by running git commands to see:
   - What files have changed (`git diff --name-only main...HEAD` or similar)
   - The actual changes (`git diff main...HEAD`)

4. Review each changed file focusing on:
   - **Security**: Look for hardcoded API keys, passwords, unsafe operations
   - **Quality**: Check for proper error handling, code style, maintainability
   - **Logic**: Verify the code logic makes sense and handles edge cases

5. **Generate output**:
   - **MANDATORY**: Use write_file tool to save complete review as "code-review-result.md"

## Markdown File Format

Save the review as "code-review-result.md" using this format:

```markdown
# Code Review Results

## Summary
- **Files reviewed:** 3
- **Issues found:** 2 warnings, 1 notice
- **Overall assessment:** Needs minor improvements before merge

## Key Findings

### Warnings
- Hardcoded API endpoint in config.py
- Missing error handling in utils.py

## Detailed Analysis
[Provide detailed analysis of changes, security considerations, and recommendations]
```

## Important Notes

- Be thorough but concise
- Focus on actionable feedback
- Prioritize security issues  
- **CRITICAL**: You MUST use the write_file tool to save "code-review-result.md"