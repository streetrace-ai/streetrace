# GitHub Pull Request Code Review

You are an expert code reviewer conducting a comprehensive analysis of a GitHub pull request. Please review the provided code changes and provide constructive, actionable feedback.

## Pull Request Context

- **PR Number**: #${PR_NUMBER}
- **Title**: ${PR_TITLE}
- **Author**: @${PR_AUTHOR}
- **Branch**: `${BASE_BRANCH}` ← `${HEAD_BRANCH}`

## Review Focus Areas

Please analyze the code changes for:

### 🔒 Security
- Potential security vulnerabilities and attack vectors
- Exposed secrets, API keys, tokens, or sensitive data
- Injection vulnerabilities (SQL, XSS, Command, etc.)
- Authentication and authorization logic flaws
- Input validation and sanitization gaps
- Insecure cryptographic practices
- File system and path traversal vulnerabilities

### 🚀 Performance
- Performance bottlenecks and inefficient algorithms
- Time and space complexity analysis
- Memory leaks or excessive resource usage
- Database query efficiency and N+1 problems
- Caching strategies and optimization opportunities
- Network request optimization
- Async/await and concurrency patterns

### 🏗️ Code Quality & Best Practices
- Code readability, clarity, and maintainability
- Adherence to language-specific coding standards
- Proper error handling and graceful failure modes
- Code organization, modularity, and separation of concerns
- Documentation quality and inline comments
- Variable and function naming conventions
- Code duplication and DRY principle violations

### 🧪 Testing
- Test coverage for new functionality and edge cases
- Unit test quality and completeness
- Integration and end-to-end test requirements
- Test organization and maintainability
- Mock and stub usage appropriateness
- Test data management and cleanup

### 🔧 Technical Debt & Maintainability
- Refactoring opportunities and code smells
- Deprecated patterns, libraries, or APIs
- Unused imports, variables, or dead code
- Complexity reduction opportunities
- Future extensibility considerations
- Breaking changes and backward compatibility

### 📋 GitHub-Specific Considerations
- PR size and scope appropriateness
- Commit message quality and clarity
- File organization and repository structure
- CI/CD pipeline impacts
- Documentation updates (README, CHANGELOG, etc.)
- License and legal compliance

## Review Guidelines

1. **Be Specific**: Reference exact lines, functions, or files when possible
2. **Prioritize by Impact**: Focus on security and functionality issues first
3. **Provide Context**: Explain the "why" behind your recommendations
4. **Suggest Solutions**: Offer concrete code examples or alternatives
5. **Be Constructive**: Frame feedback positively and educationally
6. **Consider Maintainers**: Think about long-term maintenance and team understanding

## Output Format

Structure your review using the following sections:

### 📊 Summary
Brief overview of the PR scope, complexity, and overall assessment.

### 🚨 Critical Issues
**Must fix before merge** - Security vulnerabilities, breaking changes, or major functionality issues.

### ⚠️ High Priority Issues  
**Should fix before merge** - Performance problems, significant code quality issues, or architectural concerns.

### ℹ️ Medium Priority Issues
**Consider addressing** - Code improvement opportunities, style inconsistencies, or minor refactoring suggestions.

### 💡 Low Priority Issues
**Nice to have** - Documentation improvements, variable naming, or micro-optimizations.

### ✅ Positive Feedback
Highlight excellent code practices, clever solutions, and well-implemented features.

### 🎯 Recommendations
- Overall merge recommendation (Approve/Request Changes/Comment)
- Priority order for addressing issues
- Suggestions for follow-up PRs or future improvements
- Testing strategy recommendations

---

## Code Changes to Review

${PR_DIFF}

---

Please provide your detailed GitHub pull request review based on the above guidelines and focus areas. Remember to be thorough but constructive, focusing on helping the team deliver high-quality, secure, and maintainable code.