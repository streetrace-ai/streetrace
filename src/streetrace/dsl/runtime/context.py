"""Workflow context for Streetrace DSL runtime.

Provide the execution context for generated DSL workflows.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from streetrace.dsl.runtime.events import FlowEvent, LlmCallEvent, LlmResponseEvent
from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from google.adk.events import Event

    from streetrace.dsl.runtime.workflow import DslAgentWorkflow
    from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)

# PII masking patterns
_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)
"""Pattern to match email addresses."""

_PHONE_PATTERN = re.compile(
    r"(?:\+?1[-.\s]?)?"  # Optional country code
    r"(?:\(?\d{3}\)?[-.\s]?)"  # Area code
    r"\d{3}[-.\s]?"  # First 3 digits
    r"\d{4}",  # Last 4 digits
)
"""Pattern to match phone numbers in various formats."""

_SSN_PATTERN = re.compile(
    r"\d{3}[-.\s]?\d{2}[-.\s]?\d{4}",
)
"""Pattern to match Social Security Numbers."""

_CREDIT_CARD_PATTERN = re.compile(
    r"\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}",
)
"""Pattern to match credit card numbers."""

# Jailbreak detection patterns (case insensitive)
_JAILBREAK_PATTERNS = [
    re.compile(r"ignore.*(?:previous|all).*instructions", re.IGNORECASE),
    re.compile(r"(?:you are|act as).*(?:DAN|do anything)", re.IGNORECASE),
    re.compile(r"pretend.*(?:no|without).*(?:restrictions|rules)", re.IGNORECASE),
    re.compile(
        r"(?:show|reveal|what is).*(?:system|initial).*(?:prompt|instruction)",
        re.IGNORECASE,
    ),
    re.compile(r"bypass.*(?:safety|security|restrictions)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"ignore.*(?:ethics|guidelines|policies)", re.IGNORECASE),
]
"""Patterns to detect common jailbreak attempts."""


class GuardrailProvider:
    """Provider for guardrail operations.

    Handle masking, checking, and other guardrail actions.
    """

    async def mask(self, guardrail: str, message: str) -> str:
        """Mask sensitive content in a message.

        Apply regex-based masking for common PII types including
        emails, phone numbers, SSNs, and credit card numbers.

        Args:
            guardrail: Name of the guardrail (e.g., 'pii').
            message: Message to mask.

        Returns:
            Message with sensitive content masked.

        """
        logger.debug("Masking %s in message", guardrail)

        if guardrail != "pii":
            logger.warning("Unknown guardrail type for masking: %s", guardrail)
            return message

        result = message

        # Mask credit cards first (16 digits can contain SSN/phone patterns)
        result = _CREDIT_CARD_PATTERN.sub("[CREDIT_CARD]", result)

        # Mask SSNs (before phones, as they have similar patterns)
        result = _SSN_PATTERN.sub("[SSN]", result)

        # Mask phone numbers
        result = _PHONE_PATTERN.sub("[PHONE]", result)

        # Mask emails
        return _EMAIL_PATTERN.sub("[EMAIL]", result)

    async def check(self, guardrail: str, message: str) -> bool:
        """Check if a message triggers a guardrail.

        Use pattern-based detection to identify common jailbreak
        attempts and other security concerns.

        Args:
            guardrail: Name of the guardrail (e.g., 'jailbreak').
            message: Message to check.

        Returns:
            True if the guardrail is triggered.

        """
        logger.debug("Checking %s guardrail", guardrail)

        if guardrail != "jailbreak":
            logger.warning("Unknown guardrail type for checking: %s", guardrail)
            return False

        # Check against jailbreak patterns
        for pattern in _JAILBREAK_PATTERNS:
            if pattern.search(message):
                logger.warning("Jailbreak attempt detected: pattern match")
                return True

        return False


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

        self.message: str = ""
        """Current message being processed."""

        self.guardrails = GuardrailProvider()
        """Guardrail provider for security operations."""

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

        logger.debug("Created WorkflowContext")

    def set_models(self, models: dict[str, str]) -> None:
        """Set the available models.

        Args:
            models: Dictionary of model name to model identifier.

        """
        self._models = models

    def set_prompts(self, prompts: dict[str, object]) -> None:
        """Set the available prompts.

        Args:
            prompts: Dictionary of prompt name to prompt template.

        """
        self._prompts = prompts

    def set_agents(self, agents: dict[str, dict[str, object]]) -> None:
        """Set the available agents.

        Args:
            agents: Dictionary of agent name to agent configuration.

        """
        self._agents = agents

    def set_prompt_models(self, prompt_models: dict[str, str]) -> None:
        """Set the prompt-to-model mapping.

        Args:
            prompt_models: Dictionary of prompt name to model name.

        """
        self._prompt_models = prompt_models

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

    async def run_agent(
        self,
        agent_name: str,
        *args: object,
    ) -> AsyncGenerator[Event, None]:
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

    async def run_flow(
        self,
        flow_name: str,
        *args: object,
    ) -> AsyncGenerator[Event | FlowEvent, None]:
        """Run a named flow with arguments, yielding events.

        Always delegates to the parent workflow.

        Args:
            flow_name: Name of the flow to run.
            *args: Arguments to pass to the flow.

        Yields:
            Events from flow execution.

        """
        async for event in self._workflow.run_flow(flow_name, *args):
            yield event

    def _resolve_agent_model(self, instruction_name: str | None) -> str:
        """Resolve the model for an agent based on its instruction.

        Model resolution priority:
        1. Model from prompt's `using model` clause
        2. Fall back to model named "main"

        Args:
            instruction_name: Name of the instruction prompt.

        Returns:
            The resolved model identifier string.

        """
        # Check if the prompt has a specific model
        if instruction_name and instruction_name in self._prompt_models:
            prompt_model_ref = self._prompt_models[instruction_name]
            # The prompt model ref is a model name, look it up in _models
            if prompt_model_ref in self._models:
                return self._models[prompt_model_ref]
            # Assume it's a direct model spec
            return prompt_model_ref

        # Fall back to "main" model
        if "main" in self._models:
            return self._models["main"]

        # Last resort: return empty string (will use provider default)
        return ""

    async def call_llm(
        self,
        prompt_name: str,
        *args: object,
        model: str | None = None,
    ) -> AsyncGenerator[FlowEvent, None]:
        """Call an LLM with a named prompt, yielding events.

        Look up the prompt by name, evaluate it with the context,
        and call the LLM using LiteLLM. Yield events for progress tracking.

        Args:
            prompt_name: Name of the prompt to use.
            *args: Arguments for prompt interpolation (stored in context).
            model: Optional model override.

        Yields:
            LlmCallEvent when call initiates.
            LlmResponseEvent when call completes.

        """
        import litellm

        model_info = f" using {model}" if model else ""
        logger.info(
            "Calling LLM with prompt: %s%s (%d args)",
            prompt_name,
            model_info,
            len(args),
        )

        # Look up prompt
        prompt_value = self._prompts.get(prompt_name)
        if not prompt_value:
            logger.warning("Prompt '%s' not found in workflow context", prompt_name)
            self._last_call_result = None
            return

        # Evaluate prompt lambda with context
        prompt_text = ""
        if callable(prompt_value):
            try:
                prompt_text = str(prompt_value(self))
            except (TypeError, KeyError) as e:
                logger.warning("Failed to evaluate prompt '%s': %s", prompt_name, e)
                self._last_call_result = None
                return
        else:
            prompt_text = str(prompt_value)

        # Resolve model
        resolved_model = model
        if not resolved_model:
            resolved_model = self._resolve_agent_model(prompt_name)

        # Yield call event
        yield LlmCallEvent(
            prompt_name=prompt_name,
            model=resolved_model,
            prompt_text=prompt_text,
        )

        # Build messages for LLM call
        messages = [{"role": "user", "content": prompt_text}]

        try:
            # Make LLM call via LiteLLM
            response = await litellm.acompletion(
                model=resolved_model,
                messages=messages,
            )

            # Extract response content
            # Type ignore needed because litellm has complex return types
            content: str | None = None
            choices = getattr(response, "choices", None)
            if choices and len(choices) > 0:
                first_choice = choices[0]
                message = getattr(first_choice, "message", None)
                if message:
                    content = getattr(message, "content", None)

            # Store result for flow retrieval
            self._last_call_result = content

            # Yield response event
            if content is not None:
                yield LlmResponseEvent(
                    prompt_name=prompt_name,
                    content=content,
                )

        except Exception:
            logger.exception("LLM call failed for prompt '%s'", prompt_name)
            self._last_call_result = None

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
