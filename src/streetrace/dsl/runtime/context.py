"""Workflow context for Streetrace DSL runtime.

Provide the execution context for generated DSL workflows.
"""

import re
from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

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
    """

    def __init__(self) -> None:
        """Initialize the workflow context."""
        self.vars: dict[str, object] = {}
        """Variable storage for workflow execution."""

        self.message: str = ""
        """Current message being processed."""

        self.guardrails = GuardrailProvider()
        """Guardrail provider for security operations."""

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

    def set_ui_bus(self, ui_bus: "UiBus") -> None:
        """Set the UI bus for event dispatch.

        Args:
            ui_bus: UI bus instance for dispatching events.

        """
        self._ui_bus = ui_bus

    def set_escalation_callback(
        self,
        callback: "Callable[[str], None]",
    ) -> None:
        """Set the callback for human escalation.

        Args:
            callback: Callback function that receives the escalation message.

        """
        self._escalation_callback = callback

    async def run_agent(self, agent_name: str, *args: object) -> object:
        """Run a named agent with arguments.

        Create an ADK LlmAgent from the agent configuration and execute it
        with the provided arguments as the user prompt.

        Args:
            agent_name: Name of the agent to run.
            *args: Arguments to pass to the agent (joined as prompt text).

        Returns:
            Result from the agent execution, or None if agent not found.

        """
        from google.adk import Runner
        from google.adk.agents import LlmAgent
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types

        logger.info("Running agent: %s with %d args", agent_name, len(args))

        # Look up agent configuration
        agent_def = self._agents.get(agent_name)
        if not agent_def:
            logger.warning("Agent '%s' not found in workflow context", agent_name)
            return None

        # Get instruction from agent's instruction field
        instruction_name = agent_def.get("instruction")
        instruction = ""
        if instruction_name and isinstance(instruction_name, str):
            prompt_value = self._prompts.get(instruction_name)
            if callable(prompt_value):
                try:
                    instruction = str(prompt_value(self))
                except (TypeError, KeyError) as e:
                    logger.warning(
                        "Failed to evaluate prompt '%s': %s",
                        instruction_name,
                        e,
                    )
            elif prompt_value:
                instruction = str(prompt_value)

        # Resolve model following the design spec:
        # 1. Model from prompt's `using model` clause
        # 2. Fall back to model named "main"
        instr_name_str = instruction_name if isinstance(instruction_name, str) else None
        model = self._resolve_agent_model(instr_name_str)

        # Create LlmAgent with configuration
        agent = LlmAgent(
            name=agent_name,
            model=model,
            instruction=instruction,
        )

        # Build prompt from args
        prompt_text = " ".join(str(arg) for arg in args) if args else ""

        # Create message content
        content = None
        if prompt_text:
            parts = [genai_types.Part.from_text(text=prompt_text)]
            content = genai_types.Content(role="user", parts=parts)

        # Execute via ADK Runner
        session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
        runner = Runner(
            app_name="dsl_workflow",
            session_service=session_service,
            agent=agent,
        )

        final_response: object = None
        async for event in runner.run_async(
            user_id="workflow_user",
            session_id="workflow_session",
            new_message=content,
        ):
            # Check if this is the final response
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response = event.content.parts[0].text
                break

        return final_response

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
    ) -> object:
        """Call an LLM with a named prompt.

        Look up the prompt by name, evaluate it with the context,
        and call the LLM using LiteLLM.

        Args:
            prompt_name: Name of the prompt to use.
            *args: Arguments for prompt interpolation (stored in context).
            model: Optional model override.

        Returns:
            LLM response content, or None if prompt not found or on error.

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
            return None

        # Evaluate prompt lambda with context
        prompt_text = ""
        if callable(prompt_value):
            try:
                prompt_text = str(prompt_value(self))
            except (TypeError, KeyError) as e:
                logger.warning("Failed to evaluate prompt '%s': %s", prompt_name, e)
                return None
        else:
            prompt_text = str(prompt_value)

        # Resolve model
        resolved_model = model
        if not resolved_model:
            resolved_model = self._resolve_agent_model(prompt_name)

        # Build messages for LLM call
        messages = [{"role": "user", "content": prompt_text}]

        try:
            # Make LLM call via LiteLLM
            response = await litellm.acompletion(
                model=resolved_model,
                messages=messages,
            )
        except Exception:
            logger.exception("LLM call failed for prompt '%s'", prompt_name)
            return None

        # Extract response content
        # Type ignore needed because litellm has complex return types
        choices = getattr(response, "choices", None)
        if choices and len(choices) > 0:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message:
                return getattr(message, "content", None)
        return None

    def get_goal(self) -> str:
        """Get the current agent goal.

        Returns:
            The current goal string.

        """
        goal = self.vars.get("goal", "")
        return str(goal) if goal else ""

    def detect_drift(self, *args: object) -> bool:
        """Detect trajectory drift from the current goal.

        Use keyword overlap between the current trajectory and the goal
        to determine if the agent has drifted off-topic. This is a simple
        heuristic that can be enhanced with LLM-based comparison later.

        Args:
            *args: Current trajectory text to check for drift.

        Returns:
            True if drift is detected (trajectory doesn't match goal).

        """
        if not args:
            return False

        goal = self.get_goal()
        if not goal:
            # No goal set, cannot detect drift
            return False

        trajectory = " ".join(str(arg) for arg in args).lower()
        goal_lower = goal.lower()

        # Extract significant words (skip common words)
        common_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "up",
            "down",
            "out",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "and",
            "but",
            "or",
            "if",
            "because",
            "about",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "its",
            "our",
            "their",
            "this",
            "that",
            "these",
            "those",
            "what",
            "which",
            "who",
            "whom",
            "whose",
            "want",
            "help",
            "like",
        }

        min_word_length = 2

        def extract_keywords(text: str) -> set[str]:
            words = re.findall(r"\b[a-z]+\b", text)
            return {
                w for w in words if w not in common_words and len(w) > min_word_length
            }

        goal_keywords = extract_keywords(goal_lower)
        trajectory_keywords = extract_keywords(trajectory)

        if not goal_keywords:
            return False

        # Calculate overlap
        overlap = goal_keywords & trajectory_keywords
        overlap_ratio = len(overlap) / len(goal_keywords) if goal_keywords else 0

        # If less than 20% keyword overlap, consider it drift
        drift_threshold = 0.2
        is_drift = overlap_ratio < drift_threshold

        if is_drift:
            logger.debug(
                "Drift detected: overlap ratio %.2f (threshold %.2f)",
                overlap_ratio,
                drift_threshold,
            )

        return is_drift

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
