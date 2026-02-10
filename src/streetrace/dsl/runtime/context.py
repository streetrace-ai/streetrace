"""Workflow context for Streetrace DSL runtime.

Provide the execution context for generated DSL workflows.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from streetrace.dsl.runtime.errors import JSONParseError, SchemaValidationError
from streetrace.dsl.runtime.events import (
    EscalationEvent,
    FlowEvent,
    LlmCallEvent,
    LlmResponseEvent,
)
from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from google.adk.events import Event
    from pydantic import BaseModel

    from streetrace.dsl.runtime.workflow import (
        DslAgentWorkflow,
        EscalationSpec,
        PromptSpec,
    )
    from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)

MAX_SCHEMA_RETRIES = 3
"""Maximum number of retry attempts for schema validation."""

_CODE_BLOCK_FENCE = "```"
"""Markdown code block fence delimiter."""

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

        self._last_escalated: bool = False
        """Whether the last run_agent_with_escalation triggered escalation."""

        self._schemas: dict[str, type[BaseModel]] = {}
        """Schema definitions as Pydantic models."""

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
        Return empty string if not found (tolerant for prompt composition).

        Args:
            name: Variable or prompt name to resolve.

        Returns:
            String value of the resolved name.

        """
        if name in self.vars:
            return self.stringify(self.vars[name])

        prompt_spec = self._prompts.get(name)
        if prompt_spec is not None and hasattr(prompt_spec, "body"):
            body_fn = prompt_spec.body
            if callable(body_fn):
                return str(body_fn(self))
            return str(body_fn)

        return ""

    def resolve_property(self, name: str, *properties: str) -> str:
        """Resolve a dotted property path like ``$chunk.title``.

        Look up the base variable, coerce JSON strings to dicts if
        needed, then walk the property chain.  Return the stringified
        leaf value, or an empty string on any lookup failure.

        Args:
            name: Base variable name.
            *properties: Property names to traverse.

        Returns:
            String value of the resolved property.

        """
        value: object = self.vars.get(name)
        if value is None:
            return ""

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

    def set_schemas(self, schemas: dict[str, type[BaseModel]]) -> None:
        """Set the available schemas.

        Args:
            schemas: Dictionary of schema name to Pydantic model class.

        """
        self._schemas = schemas

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

        # Reset escalation state
        self._last_escalated = False
        last_adk_event: AdkEvent | None = None

        # Delegate to workflow's run_agent (yielding events)
        async for event in self._workflow.run_agent(agent_name, *args):
            if isinstance(event, AdkEvent):
                last_adk_event = event
            yield event

        # Check escalation after agent completes
        cond = self._get_escalation_condition(agent_name)
        self._last_escalated = self._check_escalation(
            agent_name,
            self._last_call_result,
        )

        # If escalation triggered, yield events to signal escalation
        if self._last_escalated and cond is not None:
            # Yield our DSL-specific EscalationEvent with full context
            yield EscalationEvent(
                agent_name=agent_name,
                result=str(self._last_call_result),
                condition_op=cond.op,
                condition_value=cond.value,
            )

            # Also yield ADK Event with actions.escalate=True for ADK integration
            author = last_adk_event.author if last_adk_event else agent_name
            yield AdkEvent(
                author=author,
                actions=EventActions(escalate=True),
            )

    def _check_escalation(self, agent_name: str, result: object) -> bool:
        """Check if result triggers escalation condition.

        Args:
            agent_name: Name of the agent that produced the result.
            result: The result to check against escalation condition.

        Returns:
            True if escalation is triggered, False otherwise.

        """
        # Get escalation condition from agent's prompt
        cond = self._get_escalation_condition(agent_name)
        if cond is None:
            return False

        # Evaluate the condition against the result
        return self._evaluate_escalation_condition(cond, result)

    def _get_escalation_condition(
        self,
        agent_name: str,
    ) -> EscalationSpec | None:
        """Get escalation condition for an agent's prompt.

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

    def _evaluate_escalation_condition(
        self,
        cond: EscalationSpec,
        result: object,
    ) -> bool:
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

    def _validate_array_schema(
        self,
        parsed: object,
        raw_response: str,
        schema_model: type[BaseModel],
    ) -> None:
        """Validate parsed response as array of schema objects.

        Args:
            parsed: Parsed JSON response.
            raw_response: Original response string for error reporting.
            schema_model: Pydantic model for validation.

        Raises:
            JSONParseError: If parsed is not a list.

        """
        if not isinstance(parsed, list):
            msg = f"Expected JSON array, got {type(parsed).__name__}"
            raise JSONParseError(
                raw_response=raw_response,
                parse_error=msg,
            )
        validated_items = []
        for item in parsed:
            validated = schema_model.model_validate(item)
            validated_items.append(validated.model_dump())
        self._last_call_result = validated_items

    def _parse_json_response(self, content: str) -> dict[str, object] | list[object]:
        """Parse JSON from LLM response, handling markdown code blocks.

        Extract JSON content from LLM responses which may include markdown
        formatting. Supports plain JSON and JSON wrapped in code blocks.

        Uses line-by-line scanning instead of regex for reliability and
        easier debugging.

        Args:
            content: Raw LLM response content.

        Returns:
            Parsed JSON as a dictionary.

        Raises:
            JSONParseError: If content cannot be parsed as JSON or contains
                multiple ambiguous code blocks.

        """
        code_blocks = self._extract_code_blocks(content)

        json_content = ""
        if len(code_blocks) == 0:
            # No code blocks - treat entire content as JSON
            json_content = content.strip()
        elif len(code_blocks) == 1:
            # Single code block - extract contents
            json_content = code_blocks[0].strip()
        else:
            # Multiple code blocks - ambiguous
            raise JSONParseError(
                raw_response=content,
                parse_error=(
                    "Response contains multiple code blocks. "
                    "Please return a single JSON object."
                ),
            )

        try:
            result: dict[str, object] | list[object] = json.loads(json_content)
        except json.JSONDecodeError as e:
            raise JSONParseError(
                raw_response=content,
                parse_error=str(e),
            ) from e
        return result

    def _extract_code_blocks(self, content: str) -> list[str]:
        """Extract code block contents from markdown text.

        Scan line-by-line to find fenced code blocks (```...```)
        and extract their contents. This approach is more reliable
        and debuggable than regex patterns.

        Args:
            content: Text potentially containing markdown code blocks.

        Returns:
            List of code block contents (without the fence delimiters).

        """
        lines = content.split("\n")
        blocks: list[str] = []
        current_block: list[str] = []
        in_block = False

        for line in lines:
            if line.startswith(_CODE_BLOCK_FENCE):
                if in_block:
                    # Closing a block
                    blocks.append("\n".join(current_block))
                    current_block = []
                    in_block = False
                else:
                    # Opening a block (language specifier after ``` is ignored)
                    in_block = True
            elif in_block:
                current_block.append(line)

        return blocks

    def _is_array_schema(self, prompt_spec: PromptSpec | None) -> bool:
        """Check if a prompt spec has an array schema (e.g., Finding[]).

        Args:
            prompt_spec: Prompt specification to check.

        Returns:
            True if schema ends with [], False otherwise.

        """
        if prompt_spec is None:
            return False
        schema_name = getattr(prompt_spec, "schema", None)
        if not schema_name or not isinstance(schema_name, str):
            return False
        return bool(schema_name.endswith("[]"))

    def _get_schema_model(
        self,
        prompt_spec: PromptSpec | None,
    ) -> type[BaseModel] | None:
        """Get the Pydantic model for a prompt's schema.

        Look up the schema name from the prompt spec and resolve it
        to the corresponding Pydantic model class. Strip [] suffix
        for array types.

        Args:
            prompt_spec: Prompt specification, may be None.

        Returns:
            Pydantic model class if schema exists, None otherwise.

        """
        if prompt_spec is None:
            return None

        schema_name = getattr(prompt_spec, "schema", None)
        if not schema_name:
            return None

        # Strip [] suffix for array types
        if isinstance(schema_name, str) and schema_name.endswith("[]"):
            schema_name = schema_name[:-2]

        return self._schemas.get(schema_name)

    def _enrich_prompt_with_schema(
        self,
        prompt_text: str,
        json_schema: dict[str, object],
        *,
        is_array: bool = False,
    ) -> str:
        """Append JSON format instructions to a prompt.

        Add instructions telling the LLM to respond with valid JSON
        that matches the provided schema.

        Args:
            prompt_text: Original prompt text.
            json_schema: JSON Schema dict from Pydantic model.
            is_array: If True, instruct LLM to return a JSON array of items.

        Returns:
            Enriched prompt with JSON instructions.

        """
        schema_str = json.dumps(json_schema, indent=2)
        if is_array:
            return (
                f"{prompt_text}\n\n"
                f"IMPORTANT: You MUST respond with a JSON array of objects, "
                f"where each element matches this schema:\n"
                f"```json\n{schema_str}\n```\n\n"
                f"Do NOT include any text outside the JSON array."
            )
        return (
            f"{prompt_text}\n\n"
            f"IMPORTANT: You MUST respond with valid JSON that matches this schema:\n"
            f"```json\n{schema_str}\n```\n\n"
            f"Do NOT include any text outside the JSON object."
        )

    def _evaluate_prompt_text(
        self,
        prompt_name: str,
        prompt_value: object,
    ) -> str | None:
        """Evaluate a prompt value to get the text.

        Args:
            prompt_name: Name of the prompt for error logging.
            prompt_value: The prompt value (PromptSpec, callable, or string).

        Returns:
            The evaluated prompt text, or None on failure.

        """
        from streetrace.dsl.runtime.workflow import PromptSpec

        if isinstance(prompt_value, PromptSpec):
            try:
                return str(prompt_value.body(self))
            except (TypeError, KeyError) as e:
                logger.warning("Failed to evaluate prompt '%s': %s", prompt_name, e)
                return None
        elif callable(prompt_value):
            try:
                return str(prompt_value(self))
            except (TypeError, KeyError) as e:
                logger.warning("Failed to evaluate prompt '%s': %s", prompt_name, e)
                return None
        return str(prompt_value)

    def _extract_llm_content(self, response: object) -> str:
        """Extract content string from LLM response.

        Args:
            response: The LLM response object from litellm.

        Returns:
            The content string, or empty string if not found.

        """
        choices = getattr(response, "choices", None)
        if choices and len(choices) > 0:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message:
                content = getattr(message, "content", None)
                if content is not None:
                    return str(content)
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

        When the prompt has a schema expectation, the response is validated
        against the schema with automatic retry on failure.

        Args:
            prompt_name: Name of the prompt to use.
            *args: Arguments for prompt interpolation (stored in context).
            model: Optional model override.

        Yields:
            LlmCallEvent when call initiates.
            LlmResponseEvent when call completes.

        Raises:
            SchemaValidationError: If schema validation fails after max retries.

        """
        from streetrace.dsl.runtime.workflow import PromptSpec

        model_info = f" using {model}" if model else ""
        logger.info(
            "Calling LLM with prompt: %s%s (%d args)",
            prompt_name,
            model_info,
            len(args),
        )

        # Look up and evaluate prompt
        prompt_value = self._prompts.get(prompt_name)
        if not prompt_value:
            logger.warning("Prompt '%s' not found in workflow context", prompt_name)
            self._last_call_result = None
            return

        prompt_text = self._evaluate_prompt_text(prompt_name, prompt_value)
        if prompt_text is None:
            self._last_call_result = None
            return

        # Get schema model if prompt has one
        prompt_spec = prompt_value if isinstance(prompt_value, PromptSpec) else None
        schema_model = self._get_schema_model(prompt_spec)

        # Enrich prompt with JSON instructions if schema expected
        is_array = self._is_array_schema(prompt_spec)
        if schema_model:
            json_schema = schema_model.model_json_schema()
            prompt_text = self._enrich_prompt_with_schema(
                prompt_text, json_schema, is_array=is_array,
            )

        # Resolve model and yield call event
        resolved_model = model or self._resolve_agent_model(prompt_name)
        yield LlmCallEvent(
            prompt_name=prompt_name,
            model=resolved_model,
            prompt_text=prompt_text,
        )

        # Execute LLM call with schema validation and retry
        async for event in self._execute_llm_with_validation(
            prompt_name=prompt_name,
            resolved_model=resolved_model,
            prompt_text=prompt_text,
            schema_model=schema_model,
            is_array=is_array,
        ):
            yield event

    async def _execute_llm_with_validation(
        self,
        *,
        prompt_name: str,
        resolved_model: str,
        prompt_text: str,
        schema_model: type[BaseModel] | None,
        is_array: bool = False,
    ) -> AsyncGenerator[FlowEvent, None]:
        """Execute LLM call with optional schema validation and retry.

        Args:
            prompt_name: Name of the prompt for events.
            resolved_model: Model identifier to use.
            prompt_text: The prompt text to send.
            schema_model: Pydantic model for validation, or None.
            is_array: True if expecting an array of schema items.

        Yields:
            LlmResponseEvent on success.

        Raises:
            SchemaValidationError: If validation fails after max retries.

        """
        import litellm
        from pydantic import ValidationError as PydanticValidationError

        messages: list[dict[str, str]] = [{"role": "user", "content": prompt_text}]
        last_content = ""
        last_error = ""

        for attempt in range(MAX_SCHEMA_RETRIES):
            validation_succeeded = False
            try:
                response = await litellm.acompletion(
                    model=resolved_model,
                    messages=messages,
                )
                last_content = self._extract_llm_content(response)

                # If no schema, return content directly
                if not schema_model:
                    self._last_call_result = last_content
                    if last_content:
                        yield LlmResponseEvent(
                            prompt_name=prompt_name,
                            content=last_content,
                        )
                    return

                # Parse and validate response
                parsed = self._parse_json_response(last_content)

                if is_array:
                    # Array schema: parse as list and validate each element
                    self._validate_array_schema(
                        parsed, last_content, schema_model,
                    )
                else:
                    validated = schema_model.model_validate(parsed)
                    self._last_call_result = validated.model_dump()
                validation_succeeded = True

            except (JSONParseError, PydanticValidationError) as e:
                last_error = str(e)
                logger.warning(
                    "Schema validation attempt %d/%d failed for '%s': %s",
                    attempt + 1,
                    MAX_SCHEMA_RETRIES,
                    prompt_name,
                    last_error,
                )
                self._add_retry_feedback(messages, last_content, last_error, attempt)

            except Exception:
                logger.exception("LLM call failed for prompt '%s'", prompt_name)
                self._last_call_result = None
                return

            if validation_succeeded:
                yield LlmResponseEvent(
                    prompt_name=prompt_name,
                    content=last_content,
                )
                return

        # Exhausted retries - raise SchemaValidationError
        # schema_model is guaranteed non-None here since we return early otherwise
        schema_name = schema_model.__name__ if schema_model else "Unknown"
        raise SchemaValidationError(
            schema_name=schema_name,
            errors=[last_error],
            raw_response=last_content,
        )

    def _add_retry_feedback(
        self,
        messages: list[dict[str, str]],
        last_content: str,
        last_error: str,
        attempt: int,
    ) -> None:
        """Add error feedback to messages for retry.

        Args:
            messages: Message list to append to.
            last_content: The assistant's last response.
            last_error: The error message.
            attempt: Current attempt number (0-indexed).

        """
        if attempt < MAX_SCHEMA_RETRIES - 1:
            messages.append({"role": "assistant", "content": last_content})
            error_feedback = (
                f"Error: {last_error}\n\n"
                f"Please fix the JSON and try again. "
                f"Ensure you return only valid JSON matching the schema."
            )
            messages.append({"role": "user", "content": error_feedback})

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
