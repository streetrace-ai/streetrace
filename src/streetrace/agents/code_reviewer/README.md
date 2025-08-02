# Code Reviewer Agent

A comprehensive code reviewer agent that analyzes ALL file types in pull requests without filtering or discrimination.

## Purpose

This agent solves the issue where the default coder agent was only reviewing Python files and ignoring shell scripts, YAML files, and other configuration files. The code reviewer agent is specifically designed to:

1. **Review ALL file types** without any filtering
2. **Analyze security vulnerabilities** across different languages and formats
3. **Check syntax and best practices** for configuration files, scripts, and documentation
4. **Focus on actual changes** rather than performing full codebase audits

## Supported File Types

The agent reviews ALL changed files including:

- **Python files** (.py)
- **Shell scripts** (.sh, .bash, .zsh)
- **YAML files** (.yml, .yaml) - CI/CD configs, Docker Compose, etc.
- **JSON files** (.json) - Configuration, package files, etc.
- **Markdown files** (.md) - Documentation, README files
- **Configuration files** (.toml, .ini, .cfg, .conf)
- **Dockerfile** and containerization files
- **CI/CD pipeline files** (.github/workflows/*)
- **Any other text-based files** with logic or configuration

## Key Features

### No File Type Discrimination
Unlike the coder agent which focuses on traditional programming languages, this agent treats all file types as equally important for review.

### Comprehensive Security Analysis
- Scans for exposed API keys, tokens, and credentials
- Checks for command injection vulnerabilities in shell scripts
- Validates secure configurations in YAML and JSON files
- Reviews CI/CD pipeline security

### Multi-Language Expertise
- Shell script best practices and error handling
- YAML syntax validation and structure checking
- JSON schema validation
- Markdown accuracy and link validation
- Configuration file correctness

### Change-Focused Review
Only reviews lines that were actually changed (+ in git diff), avoiding unnecessary noise from existing code.

## Usage

The agent must be explicitly specified using the `--agent` parameter:

```bash
# Use the specific agent parameter
poetry run streetrace --model=<your-model> --agent=StreetRace_Code_Reviewer_Agent --prompt="Review all changes in this PR"
```

## Integration with GitHub Actions

This agent is designed to work with the existing GitHub Actions code review workflow, providing comprehensive analysis of all file types in pull requests.

## Fixes Issue #54

This agent specifically addresses [Issue #54](https://github.com/your-repo/issues/54) where the code reviewer was only analyzing Python files and ignoring shell scripts, YAML files, and other important configuration files.