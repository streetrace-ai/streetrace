"""Minimal context for prompt resolution during agent creation.

Provide a lightweight context that can be used to evaluate prompt lambdas
without requiring a full workflow reference.
"""

import json


class PromptResolutionContext:
    """Minimal context for resolving prompts during agent creation.

    Unlike WorkflowContext, this doesn't require a workflow reference
    because it's only used for prompt evaluation, not agent execution.
    This context provides the minimal interface needed to evaluate
    DSL prompt lambdas (access to vars, message, and resolve).
    """

    def __init__(self) -> None:
        """Initialize the prompt resolution context."""
        self.vars: dict[str, object] = {}
        """Variable storage for prompt evaluation."""

        self.message: str = ""
        """Current message being processed."""

    def resolve(self, name: str) -> str:
        """Resolve a name to its string value from variables.

        Args:
            name: Variable name to resolve.

        Returns:
            String value, or empty string if not found.

        """
        if name in self.vars:
            value = self.vars[name]
            if isinstance(value, (dict, list)):
                return json.dumps(value, default=str)
            return str(value)
        return ""

    def resolve_property(self, name: str, *properties: str) -> str:
        """Resolve a dotted property path like ``$chunk.title``.

        Look up the base variable, coerce JSON strings to dicts if
        needed, then walk the property chain.

        Args:
            name: Base variable name.
            *properties: Property names to traverse.

        Returns:
            String value of the resolved property.

        """
        value: object = self.vars.get(name)
        if value is None:
            return ""

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return str(value)

        for prop in properties:
            if isinstance(value, dict):
                value = value.get(prop)
            else:
                return ""
            if value is None:
                return ""

        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        return str(value)
