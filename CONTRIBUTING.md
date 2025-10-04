# Contributing to Streetrace

First off, thank you for considering contributing to Streetrace! We appreciate your help in making this tool better.

This document outlines the basic guidelines and steps for contributing to the project.

## How to Contribute

1.  **Find an Issue or Feature:** Look through the existing issues or propose a new feature/bug fix.
2.  **Discuss:** It's often best to discuss your proposed changes in an issue before starting significant work, especially for larger features.
3.  **Fork & Branch:** Fork the repository and create a new branch for your changes.
4.  **Code:** Make your changes, following the project's structure and style.
5.  **Add Tests:** Add unit tests for any new functionality or bug fixes.
6.  **Ensure Quality:** Before submitting your contribution, please run the code quality checks.
7.  **Submit a Pull Request:** Create a Pull Request (PR) from your branch to the main repository branch.

## Code Quality Checks

To maintain code quality and consistency, we use several tools: `ruff` for code linting and style, `mypy` for static type checking, `pytest` for unit tests, `bandit` for security analysis, `deptry` for dependency validation, and `vulture` for unused code detection.

**Before submitting a Pull Request, please run the following command from the project root directory:**

```bash
make check
make test
```

This command will run the complete quality check suite including:
- `pytest` for unit tests
- `ruff` for code linting and style checks
- `mypy` for static type checking
- `bandit` for security analysis
- `deptry` for dependency validation
- `vulture` for unused code detection

**Please fix any reported errors before submitting your PR.**

You can also run individual checks:
```bash
make test      # Run tests only
make lint      # Run linting only
make typed     # Run type checking only
make security  # Run security analysis only
```

_Note:_ A GitHub Actions workflow (`.github/workflows/quality-checks.yml`) is also configured to run these checks automatically on every push and pull request to the main branch. However, running the checks locally first helps catch issues earlier and speeds up the review process.

## Style and Conventions

- Follow the code style using `ruff` (automatically checked by running the commands above).
- Use type hints (`mypy` helps check these).
- Keep functions and classes focused (Single Responsibility Principle).
- Add docstrings to public modules, classes, and functions.
- Consult `project_overview.md` for architectural context.
- Refer to `.streetrace/rules.md` for more detailed development rules.

Thank you again for your contribution!
