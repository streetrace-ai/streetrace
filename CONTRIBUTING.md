# Contributing to StreetRace

First off, thank you for considering contributing to StreetRace! We appreciate your help in making this tool better.

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

To maintain code quality and consistency, we use several tools: `isort` for import sorting, `black` for code formatting, `flake8` for linting, `mypy` for static type checking, and `pytest` for running unit tests.

**Before submitting a Pull Request, please run the following command chain from the project root directory:**

```bash
# 1. Fix import sorting
isort src tests && \
# 2. Fix code formatting
black src tests && \
# 3. Check for other linting issues (style, logic)
flake8 src tests && \
# 4. Check for static type errors
mypy --explicit-package-bases src tests && \
# 5. Run unit tests
pytest
```

This command sequence will automatically fix import sorting and formatting issues. It will then report any remaining linting errors (`flake8`), type errors (`mypy`), or test failures (`pytest`). **Please fix any reported errors before submitting your PR.**

*Note:* A GitHub Actions workflow (`.github/workflows/quality-checks.yml`) is also configured to run these checks automatically on every push and pull request to the main branch. However, running the checks locally first helps catch issues earlier and speeds up the review process.

## Style and Conventions

*   Follow the `black` code style (automatically enforced by running the command above).
*   Adhere to PEP 8 guidelines where `black` doesn't enforce them (checked by `flake8`).
*   Use type hints (`mypy` helps check these).
*   Keep functions and classes focused (Single Responsibility Principle).
*   Add docstrings to public modules, classes, and functions.
*   Consult `project_overview.md` for architectural context.
*   Refer to `.streetrace/rules.md` for more detailed development rules.

Thank you again for your contribution!
