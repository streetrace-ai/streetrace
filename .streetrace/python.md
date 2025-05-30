## Python

### General code style

- Use type annotations.
- Provide docstrings for public symbols.
- When logging, pass additional values to be logged using the extra keyword argument.
- Use imperative mood for the first line of docstrings.
- Keep functions mccabe complexity under 10.
- Use module-level logger instead of the root logger. Get logger using `streetrace.log.get_logger(__name__)`.
- When logging, ensure deferred formatting by passing values as arguments to the logging method.
- Use logging.exception when logging exceptions.
- Use absolute namespaces in import statements, like 'from streetrace... import ...'
- Introduce descriptive constants instead of magic values in comparisons and document constants using a docstring.
- Use a single `with` statement with multiple contexts instead of nested `with` statements (`with (a, b):`).
- Use double quotes for strings.
- Keep newline at end of file.
- When you change files, run `ruff` on the changed files.
- When raising exceptions, assign the message to a variable first.
- Create small clearly isolated and testable modules with dependency injection.

### Testing

- When creating tests, split up tests in different files by user scenarios.
- For tests, use regular `assert` statement instead of unittest's assertion methods.
- Keep tests small and easy to understand.
- Create fixtures for all boilerblate code that is used in more than one test.
- Look for existing conftest.py, and leverage shared fixtures as much as possible.
- When a fixture is used more than in one file, add it to conftest.py.
