"""Flow events for non-ADK operations in DSL workflows.

Provide event classes for operations that don't use the ADK event system,
such as direct LLM calls via the `call llm` DSL statement.
"""

from dataclasses import dataclass, field


@dataclass
class FlowEvent:
    """Base class for all non-ADK flow events.

    Provide a common type for isinstance checks and a type discriminator
    for serialization.
    """

    type: str
    """Discriminator field for event type identification."""


@dataclass
class LlmCallEvent(FlowEvent):
    """Event emitted when a direct LLM call is initiated.

    Correspond to the DSL `call llm` statement.
    """

    prompt_name: str
    """Name of the prompt being called."""

    model: str
    """Model identifier for the LLM call."""

    prompt_text: str
    """Resolved prompt text sent to the LLM."""

    type: str = field(default="llm_call", init=False)


@dataclass
class LlmResponseEvent(FlowEvent):
    """Event emitted when a direct LLM call completes.

    Contain the response from the LLM.
    """

    prompt_name: str
    """Name of the prompt that was called."""

    content: str
    """Response content from the LLM."""

    is_final: bool = True
    """Whether this is the final response (always True for LLM calls)."""

    type: str = field(default="llm_response", init=False)


@dataclass
class FlowResultEvent(FlowEvent):
    """Event emitted when a flow returns a value.

    Provide the return value from the flow's `return` statement to the
    supervisor for capture as the final response.
    """

    result: object
    """The return value from the flow."""

    type: str = field(default="flow_result", init=False)


@dataclass
class EscalationEvent(FlowEvent):
    """Event emitted when escalation is triggered.

    Provide escalation signal to parent agents in a hierarchy through the
    event system, following ADK's escalation pattern.
    """

    agent_name: str
    """Name of the agent that triggered escalation."""

    result: str
    """The result that triggered escalation."""

    condition_op: str
    """The escalation operator that matched ('~', '==', '!=', 'contains')."""

    condition_value: str
    """The escalation condition value that was matched against."""

    type: str = field(default="escalation", init=False)
