## Python

### General code style

- Use type annotations.
- Provide docstrings for public symbols.
- When logging, pass additional values to be logged using the extra keyword argument.
- Use imperative mood for the first line of docstrings.
- Keep functions mccabe complexity under 10.
- Use module-level logger instead of the root logger. Get logger using
  `streetrace.log.get_logger(__name__)`.
- When logging, ensure deferred formatting by passing values as arguments to the logging
  method.
- Use logging.exception when logging exceptions.
- Use absolute namespaces in import statements, like 'from streetrace... import ...'
- Introduce descriptive constants instead of magic values in comparisons and document
  constants using a docstring.
- Use a single `with` statement with multiple contexts instead of nested `with`
  statements.
- Use double quotes for strings.
- Keep newline at end of file.
- When you change files, run `ruff` on the changed files.
- When raising exceptions, assign the message to a variable first.
- Create small clearly isolated and testable modules with dependency injection.
- Never add imports in method body, always add imports in the head of the file.

### Testing

- Use pytest for testing.
- When creating tests, break up up test files by user scenarios.
- Create tests for the core user scenarios, and analyze coverage gaps.
- Address the largest coverage gaps to achieve over 95% test coverage.
- Use regular `assert` statement instead of unittest's assertion methods.
- Keep tests small and easy to understand.
- Check ./tests/conftest.py and other relevant conftest.py files for existing fixtures.
- Create fixtures for all boilerblate code that is used in more than one test.
- Look for existing conftest.py in the current and parent directories, and leverage
  shared fixtures as much as possible.
- When a fixture is used more than in one file, add it to conftest.py.
- When accessing private members for testing, add `  # noqa: SLF001` to suppress warning.
