"""Runtime errors for Streetrace DSL workflows.

Define exception classes used by generated DSL code.
"""


class DslRuntimeError(Exception):
    """Base exception for DSL runtime errors."""


class BlockedInputError(DslRuntimeError):
    """Raised when input is blocked by a guardrail.

    The guardrail system determined that the input should not
    be processed, typically due to security or policy reasons.
    """


class RetryInputError(DslRuntimeError):
    """Raised when input should be retried with modified message.

    The guardrail system requests that the user provide
    different input before processing can continue.
    """


class RetryStepError(DslRuntimeError):
    """Raised when a workflow step should be retried.

    A step within a flow encountered a condition that requires
    the step to be re-executed.
    """


class AbortError(DslRuntimeError):
    """Raised when a workflow should be aborted.

    The workflow cannot continue and should be terminated
    without completing normally.
    """


class JSONParseError(DslRuntimeError):
    """Raised when LLM response cannot be parsed as JSON.

    The LLM response does not contain valid JSON that can be extracted
    for schema validation.
    """

    def __init__(self, raw_response: str, parse_error: str) -> None:
        """Initialize JSON parse error.

        Args:
            raw_response: The raw LLM response that failed to parse.
            parse_error: Description of the parsing failure.

        """
        self.raw_response = raw_response
        self.parse_error = parse_error
        super().__init__(f"Failed to parse JSON from response: {parse_error}")


class SchemaValidationError(DslRuntimeError):
    """Raised when LLM response fails schema validation after retries.

    This error triggers escalation as the agent cannot reliably continue
    without a valid structured response.
    """

    def __init__(self, schema_name: str, errors: list[str], raw_response: str) -> None:
        """Initialize schema validation error.

        Args:
            schema_name: Name of the schema that failed validation.
            errors: List of validation error messages.
            raw_response: The raw LLM response that failed validation.

        """
        self.schema_name = schema_name
        self.errors = errors
        self.raw_response = raw_response
        super().__init__(
            f"Schema validation failed for '{schema_name}': {'; '.join(errors)}",
        )
