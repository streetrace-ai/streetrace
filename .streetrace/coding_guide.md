General rules for this codebase:

## **UI Layer: Be Tolerant**

- Always prioritize responsiveness and graceful degradation.
- Log and fallback when inputs are malformed or missing.
- Never crash the app due to external or user-provided data.
- For example, `if (format is expected) do what's needed, else show an error to the user`

## **Core/Internal Components: Be Fail-Fast**

- Enforce strict type checks and assumptions.
- Crash or raise on invalid or unexpected internal state.
- Bugs should surface early and loudly.
- For example, `assert(format is expected)`

## **Natural Language / Unstructured Parsing (e.g. Wikipedia, articles): Be Selectively Tolerant**

- Tolerate formatting and content variation.
- Enforce **critical fields** (e.g., `title`, `date`, `id`) — fail if they’re missing or invalid.
- Log and skip incomplete records rather than silently guessing.
- For example, `if (format is not expected) try all other ideas to parse, and if not, log report to user, and use a fall-back strategy`

## **Third-Party Integrations: Balance Carefully**

- Favor fail-fast if the API has strong guarantees (e.g., strictly typed API, API spec, clear docs).
- Use tolerant parsing if the schema is loose or inconsistently enforced.
- Always log deviations and enforce **minimum required fields**.
- Add validation layers to detect bugs early without rejecting recoverable inputs.
- For example, `if (format is not expected) log error, report to user immediately, fail fast`

## Code style

- First line of docstring should be in imperative mood.
- Keep functions mccabe complexity under 10.
- Use module-level logger instead of the root logger. Get logger using `streetrace.log.get_logger(__name__)`.
- Use logger's extra parameter to pass values as arguments to the logging method to defer string formatting until required.
- Use logging.exception when logging an exception.
- For tests, use regular `assert` statement instead of unittest's assertion methods.
- Use absolute namespaces in import statements, like 'from streetrace... import ...'
- Introduce descriptive constants instead of magic values in comparisons and document constants using a docstring.
- Use a single `with` statement with multiple contexts instead of nested `with` statements.
- Use double quotes for strings.
- Keep newline at end of file.
- When you change files, run `ruff` on the changed files.
- When raising exceptions, assign the message to a variable first.

## Environment

- I am using poetry for this project, so please use `poetry run` to run any python commands.
- See ./Makefile for static analysis and other prject workflows.
