"""Escalation handling for DSL runtime agent execution.

Provide escalation condition resolution and evaluation for
agents that support escalation based on result matching.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from streetrace.dsl.runtime.workflow import EscalationSpec

logger = get_logger(__name__)


class EscalationHandler:
    """Resolve and evaluate escalation conditions for agents.

    Encapsulate the logic for looking up escalation specs from
    agent/prompt definitions and evaluating conditions against
    agent execution results.
    """

    def __init__(
        self,
        *,
        agents: dict[str, dict[str, object]],
        prompts: dict[str, object],
    ) -> None:
        """Initialize with DSL definitions.

        Args:
            agents: Agent definitions dict.
            prompts: Prompt definitions from the workflow.

        """
        self._agents = agents
        self._prompts = prompts

    def get_condition(self, agent_name: str) -> EscalationSpec | None:
        """Get the escalation condition for an agent's prompt.

        Args:
            agent_name: Name of the agent.

        Returns:
            EscalationSpec if found, None otherwise.

        """
        from streetrace.dsl.runtime.workflow import EscalationSpec, PromptSpec

        agent_def = self._agents.get(agent_name)
        if not agent_def:
            return None

        prompt_name = agent_def.get("instruction")
        if not prompt_name or not isinstance(prompt_name, str):
            return None

        prompt_spec = self._prompts.get(prompt_name)
        if not prompt_spec or not isinstance(prompt_spec, PromptSpec):
            return None

        escalation = prompt_spec.escalation
        if not isinstance(escalation, EscalationSpec):
            return None
        return escalation

    def check(self, agent_name: str, result: object) -> bool:
        """Check if a result triggers escalation for an agent.

        Args:
            agent_name: Name of the agent that produced the result.
            result: The result to check against escalation condition.

        Returns:
            True if escalation is triggered, False otherwise.

        """
        cond = self.get_condition(agent_name)
        if cond is None:
            return False

        return self.evaluate(cond, result)

    @staticmethod
    def evaluate(cond: EscalationSpec, result: object) -> bool:
        """Evaluate an escalation condition against a result.

        Args:
            cond: EscalationSpec condition to evaluate.
            result: The result to check.

        Returns:
            True if condition is met, False otherwise.

        """
        from streetrace.dsl.runtime.utils import normalized_equals

        result_str = str(result)
        op_handlers: dict[str, Callable[[str, str], bool]] = {
            "~": lambda r, v: normalized_equals(r, v),
            "==": lambda r, v: r == v,
            "!=": lambda r, v: r != v,
            "contains": lambda r, v: v in r,
        }

        handler = op_handlers.get(cond.op)
        if handler:
            return handler(result_str, cond.value)
        return False
