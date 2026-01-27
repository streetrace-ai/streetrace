"""Minimal context for prompt resolution during agent creation.

Provide a lightweight context that can be used to evaluate prompt lambdas
without requiring a full workflow reference.
"""


class PromptResolutionContext:
    """Minimal context for resolving prompts during agent creation.

    Unlike WorkflowContext, this doesn't require a workflow reference
    because it's only used for prompt evaluation, not agent execution.
    This context provides the minimal interface needed to evaluate
    DSL prompt lambdas (access to vars and message).
    """

    def __init__(self) -> None:
        """Initialize the prompt resolution context."""
        self.vars: dict[str, object] = {}
        """Variable storage for prompt evaluation."""

        self.message: str = ""
        """Current message being processed."""
