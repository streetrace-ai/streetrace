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
