"""Workflow context for Streetrace DSL runtime.

Provide the execution context for generated DSL workflows.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from streetrace.dsl.runtime.events import (
    EscalationEvent,
    FlowEvent,
)
from streetrace.dsl.runtime.guardrail_provider import (
    GuardrailContent,
    GuardrailProvider,
)
from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from google.adk.events import Event
    from google.adk.sessions import Session
    from pydantic import BaseModel

    from streetrace.dsl.runtime.escalation_handler import EscalationHandler
    from streetrace.dsl.runtime.prompt_llm_caller import PromptLlmCaller
    from streetrace.dsl.runtime.workflow import (
        DslAgentWorkflow,
    )
    from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class WorkflowContext:
    """Execution context for DSL workflows.

    Provide access to variables, agents, LLM calls, and other
    runtime services needed by generated workflow code.

    The workflow reference is REQUIRED - there are no fallback code paths.
    """

    def __init__(self, workflow: DslAgentWorkflow) -> None:
        """Initialize the workflow context.

        Args:
            workflow: Parent workflow for delegation. REQUIRED.

        """
        self.vars: dict[str, object] = {}
        """Variable storage for workflow execution."""

        self.message: GuardrailContent = ""
        """Current message being processed."""

        self.event_phase: str = ""
        """Current event phase for OTEL span attribution."""

        self.guardrails = GuardrailProvider()
        """Guardrail provider for security operations."""

        self.guardrails._parent_ctx = self  # noqa: SLF001

        self._workflow = workflow
        """Reference to parent workflow for delegation."""

        self._models: dict[str, str] = {}
        """Model definitions from the workflow."""

        self._prompts: dict[str, object] = {}
        """Prompt definitions from the workflow."""

        self._agents: dict[str, dict[str, object]] = {}
        """Agent definitions from the workflow."""

        self._prompt_models: dict[str, str] = {}
        """Mapping from prompt name to model name."""

        self._ui_bus: UiBus | None = None
        """Optional UI bus for event dispatch."""

        self._escalation_callback: Callable[[str], None] | None = None
        """Optional callback for human escalation."""

        self._last_call_result: object = None
        """Result from last run_agent or call_llm operation."""

        self._last_escalated: bool = False
        """Whether the last run_agent_with_escalation triggered escalation."""

        self._schemas: dict[str, type[BaseModel]] = {}
        """Schema definitions as Pydantic models."""

        self._llm_caller: PromptLlmCaller | None = None
        """Lazy-initialized LLM caller for call_llm delegation."""

        self._escalation_handler: EscalationHandler | None = None
        """Lazy-initialized escalation handler."""

        self._parent_session: Session | None = None
        """Parent session for deriving child session identifiers."""

        self._current_flow_name: str | None = None
        """Current flow name for session ID derivation."""

        self._invocation_counter: int = 0
        """Counter for generating unique session IDs within a flow."""

        logger.debug("Created WorkflowContext")

    def stringify(self, value: object) -> str:
        """Convert a value to a string for prompt interpolation.

        Serialize dicts and lists as JSON so that structured data appears
        with double-quoted keys and JSON-standard booleans/nulls.
        All other types use Python's built-in ``str()``.

        Args:
            value: The value to convert.

        Returns:
            A string representation suitable for embedding in prompt text.

        """
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        return str(value)

    def resolve(self, name: str) -> str:
        """Resolve a name to its string value.

        Check ctx.vars first, then fall back to prompt definitions.
        Raise ``UndefinedVariableError`` if the name cannot be found.

        Args:
            name: Variable or prompt name to resolve.

        Returns:
            String value of the resolved name.

        Raises:
            UndefinedVariableError: If the name is not in vars or prompts.

        """
        if name in self.vars:
            return self.stringify(self.vars[name])

        prompt_spec = self._prompts.get(name)
        if prompt_spec is not None and hasattr(prompt_spec, "body"):
            body_fn = prompt_spec.body
            if callable(body_fn):
                return str(body_fn(self))
            return str(body_fn)

        from streetrace.dsl.runtime.errors import UndefinedVariableError

        raise UndefinedVariableError(name)

    def resolve_property(self, name: str, *properties: str) -> str:
        """Resolve a dotted property path like ``${chunk.title}``.

        Look up the base variable, coerce JSON strings to dicts if
        needed, then walk the property chain.

        Args:
            name: Base variable name.
            *properties: Property names to traverse.

        Returns:
            String value of the resolved property.

        Raises:
            UndefinedVariableError: If the base variable is not in vars.

        """
        if name not in self.vars:
            from streetrace.dsl.runtime.errors import UndefinedVariableError

            raise UndefinedVariableError(name)

        value: object = self.vars[name]

        # Coerce JSON strings to dicts/lists so property access works
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return self.stringify(value)

        for prop in properties:
            if isinstance(value, dict):
                value = value.get(prop)
            else:
                return ""
            if value is None:
                return ""

        return self.stringify(value)

    def _invalidate_cached_delegates(self) -> None:
        """Reset cached delegate instances when definitions change."""
        self._llm_caller = None
        self._escalation_handler = None

    def set_models(self, models: dict[str, str]) -> None:
        """Set the available models.

        Args:
            models: Dictionary of model name to model identifier.

        """
        self._models = models
        self._invalidate_cached_delegates()

    def set_prompts(self, prompts: dict[str, object]) -> None:
        """Set the available prompts.

        Args:
            prompts: Dictionary of prompt name to prompt template.

        """
        self._prompts = prompts
        self._invalidate_cached_delegates()

    def set_agents(self, agents: dict[str, dict[str, object]]) -> None:
        """Set the available agents.

        Args:
            agents: Dictionary of agent name to agent configuration.

        """
        self._agents = agents
        self._invalidate_cached_delegates()

    def set_prompt_models(self, prompt_models: dict[str, str]) -> None:
        """Set the prompt-to-model mapping.

        Args:
            prompt_models: Dictionary of prompt name to model name.

        """
        self._prompt_models = prompt_models
        self._invalidate_cached_delegates()

    def set_schemas(self, schemas: dict[str, type[BaseModel]]) -> None:
        """Set the available schemas.

        Args:
            schemas: Dictionary of schema name to Pydantic model class.

        """
        self._schemas = schemas
        self._invalidate_cached_delegates()

    def set_ui_bus(self, ui_bus: UiBus) -> None:
        """Set the UI bus for event dispatch.

        Args:
            ui_bus: UI bus instance for dispatching events.

        """
        self._ui_bus = ui_bus

    def set_escalation_callback(
        self,
        callback: Callable[[str], None],
    ) -> None:
        """Set the callback for human escalation.

        Args:
            callback: Callback function that receives the escalation message.

        """
        self._escalation_callback = callback

    def set_parent_session(self, session: Session) -> None:
        """Set the parent session for deriving child session identifiers.

        Args:
            session: Parent ADK session to use as reference.

        """
        self._parent_session = session

    @property
    def parent_session(self) -> Session | None:
        """Get the parent session, if set."""
        return self._parent_session

    def set_current_flow(self, flow_name: str) -> None:
        """Set the current flow name for session ID derivation.

        Args:
            flow_name: Name of the currently executing flow.

        """
        self._current_flow_name = flow_name

    @property
    def current_flow_name(self) -> str | None:
        """Get the current flow name."""
        return self._current_flow_name

    def next_invocation_id(self) -> int:
        """Get the next invocation ID for session uniqueness.

        Returns:
            Unique incrementing ID for this context's invocations.

        """
        self._invocation_counter += 1
        return self._invocation_counter

    async def run_agent(
        self,
        agent_name: str,
        *args: object,
    ) -> AsyncGenerator[Event | FlowEvent, None]:
        """Run a named agent with arguments, yielding events.

        Always delegates to the parent workflow.

        Args:
            agent_name: Name of the agent to run.
            *args: Arguments to pass to the agent (joined as prompt text).

        Yields:
            ADK events from agent execution.

        """
        async for event in self._workflow.run_agent(agent_name, *args):
            yield event

    async def run_agent_with_escalation(
        self,
        agent_name: str,
        *args: object,
    ) -> AsyncGenerator[Event | FlowEvent, None]:
        """Run agent and check for escalation.

        Similar to run_agent() but tracks escalation state based on
        the agent's prompt escalation condition. When escalation triggers,
        yields an EscalationEvent after all agent events to signal to
        parent agents via the event system.

        Additionally, sets ADK Event.actions.escalate = True on a final
        event to integrate with ADK's native escalation mechanism.

        Args:
            agent_name: Name of the agent to run.
            *args: Arguments to pass to the agent.

        Yields:
            ADK events from agent execution, followed by EscalationEvent
            and an ADK Event with actions.escalate=True if triggered.

        """
        from google.adk.events import Event as AdkEvent
        from google.adk.events.event_actions import EventActions

        handler = self._get_escalation_handler()

        # Reset escalation state
        self._last_escalated = False
        last_adk_event: AdkEvent | None = None

        # Delegate to workflow's run_agent (yielding events)
        async for event in self._workflow.run_agent(agent_name, *args):
            if isinstance(event, AdkEvent):
                last_adk_event = event
            yield event

        # Check escalation after agent completes
        cond = handler.get_condition(agent_name)
        self._last_escalated = handler.check(
            agent_name, self._last_call_result,
        )

        # If escalation triggered, yield events to signal escalation
        if self._last_escalated and cond is not None:
            yield EscalationEvent(
                agent_name=agent_name,
                result=str(self._last_call_result),
                condition_op=cond.op,
                condition_value=cond.value,
            )

            author = last_adk_event.author if last_adk_event else agent_name
            yield AdkEvent(
                author=author,
                actions=EventActions(escalate=True),
            )

    def get_last_result_with_escalation(self) -> tuple[object, bool]:
        """Get the last result and escalation flag.

        Returns:
            Tuple of (result, escalated) where result is the last call result
            and escalated is whether escalation was triggered.

        """
        return self._last_call_result, self._last_escalated

    async def run_flow(
        self,
        flow_name: str,
        *args: object,
    ) -> AsyncGenerator[Event | FlowEvent, None]:
        """Run a named flow with arguments, yielding events.

        Delegates to the parent workflow, passing this context so the
        sub-flow shares the same variable scope as the caller.

        Args:
            flow_name: Name of the flow to run.
            *args: Arguments to pass to the flow.

        Yields:
            Events from flow execution.

        """
        async for event in self._workflow.run_flow(
            flow_name, *args, caller_ctx=self,
        ):
            yield event

    async def call_llm(
        self,
        prompt_name: str,
        *_args: object,
        model: str | None = None,
    ) -> AsyncGenerator[FlowEvent, None]:
        """Call an LLM with a named prompt, yielding events.

        Delegate to PromptLlmCaller for prompt evaluation, LLM
        invocation, and schema validation with retry.

        Args:
            prompt_name: Name of the prompt to use.
            *_args: Positional args accepted for API compatibility.
            model: Optional model override.

        Yields:
            LlmCallEvent when call initiates.
            LlmResponseEvent when call completes.

        Raises:
            SchemaValidationError: If schema validation fails after retries.

        """
        caller = self._get_llm_caller()
        async for event in caller.call(prompt_name, self, model=model):
            yield event
        self._last_call_result = caller.last_result

    def _get_llm_caller(self) -> PromptLlmCaller:
        """Get or create the PromptLlmCaller instance.

        Returns:
            The PromptLlmCaller for LLM call delegation.

        """
        if self._llm_caller is None:
            from streetrace.dsl.runtime.prompt_llm_caller import (
                PromptLlmCaller as Caller,
            )

            self._llm_caller = Caller(
                models=self._models,
                prompts=self._prompts,
                schemas=self._schemas,
                prompt_models=self._prompt_models,
            )
        return self._llm_caller

    def _get_escalation_handler(self) -> EscalationHandler:
        """Get or create the EscalationHandler instance.

        Returns:
            The EscalationHandler for escalation condition evaluation.

        """
        if self._escalation_handler is None:
            from streetrace.dsl.runtime.escalation_handler import (
                EscalationHandler as Handler,
            )

            self._escalation_handler = Handler(
                agents=self._agents,
                prompts=self._prompts,
            )
        return self._escalation_handler

    def get_last_result(self) -> object:
        """Get the result from the last run_agent or call_llm operation.

        Returns:
            The result from the most recent operation, or None if no
            operation has been executed or the last operation failed.

        """
        return self._last_call_result

    def process(
        self,
        *args: object,
        pipeline: str | None = None,
    ) -> object:
        """Process input through a pipeline.

        Apply a named transformation pipeline to the input data.
        If no pipeline is specified, return the first argument unchanged.

        Args:
            *args: Arguments to process.
            pipeline: Optional name of a pipeline function stored in vars.

        Returns:
            Processed result, or first arg if no pipeline specified.

        """
        if not args:
            return None

        first_arg = args[0]

        if pipeline:
            # Look up pipeline function in vars
            pipeline_func = self.vars.get(pipeline)
            if callable(pipeline_func):
                try:
                    return pipeline_func(first_arg)
                except (TypeError, ValueError) as e:
                    logger.warning(
                        "Pipeline '%s' failed: %s",
                        pipeline,
                        e,
                    )
                    return first_arg
            else:
                logger.warning("Pipeline '%s' not found or not callable", pipeline)

        return first_arg

    def log(self, message: str) -> None:
        """Log a message from the workflow.

        Args:
            message: Message to log.

        """
        logger.info("[Workflow] %s", message)

    def warn(self, message: str) -> None:
        """Log a warning from the workflow.

        Args:
            message: Warning message.

        """
        logger.warning("[Workflow] %s", message)

    def notify(self, message: str) -> None:
        """Send a notification.

        Args:
            message: Notification message.

        """
        logger.info("[Notification] %s", message)

    async def escalate_to_human(self, message: str | None = None) -> None:
        """Escalate to human operator.

        Log the escalation, call any registered callback, and dispatch
        a UI event if a UI bus is configured.

        Args:
            message: Optional message for the human.

        """
        from streetrace.ui import ui_events

        escalation_message = message or "Escalating to human"
        logger.info("[Escalate] %s", escalation_message)

        # Call registered callback if present
        if self._escalation_callback:
            try:
                self._escalation_callback(escalation_message)
            except (TypeError, ValueError) as e:
                logger.warning("Escalation callback failed: %s", e)

        # Dispatch UI event if UI bus is configured
        if self._ui_bus:
            self._ui_bus.dispatch_ui_update(
                ui_events.Warn(f"[Escalation] {escalation_message}"),
            )
