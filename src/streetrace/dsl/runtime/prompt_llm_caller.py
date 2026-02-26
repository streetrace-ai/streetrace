"""Prompt-based LLM calling for DSL runtime.

Execute direct LLM calls with schema validation and retry
support for DSL workflow prompts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from streetrace.dsl.runtime.errors import JSONParseError, SchemaValidationError
from streetrace.dsl.runtime.events import LlmCallEvent, LlmResponseEvent
from streetrace.dsl.runtime.response_parser import (
    enrich_prompt_with_schema,
    get_schema_model,
    is_array_schema,
)
from streetrace.dsl.runtime.schema_validator import validate_response
from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pydantic import BaseModel

    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.events import FlowEvent

logger = get_logger(__name__)

MAX_SCHEMA_RETRIES = 3
"""Maximum number of retry attempts for schema validation."""


class PromptLlmCaller:
    """Execute direct LLM calls with schema validation and retry.

    Encapsulate prompt evaluation, model resolution, LLM invocation,
    and schema validation with retry for DSL ``call_llm`` operations.
    """

    def __init__(
        self,
        *,
        models: dict[str, str],
        prompts: dict[str, object],
        schemas: dict[str, type[BaseModel]],
        prompt_models: dict[str, str],
    ) -> None:
        """Initialize with DSL definitions.

        Args:
            models: Model name to identifier mapping.
            prompts: Prompt definitions from the workflow.
            schemas: Schema name to Pydantic model mapping.
            prompt_models: Prompt name to model name mapping.

        """
        self._models = models
        self._prompts = prompts
        self._schemas = schemas
        self._prompt_models = prompt_models
        self._last_result: object = None

    @property
    def last_result(self) -> object:
        """Get the result from the last LLM call."""
        return self._last_result

    def resolve_model(self, instruction_name: str | None) -> str:
        """Resolve the model for a prompt.

        Model resolution priority:
        1. Model from prompt's ``using model`` clause
        2. Fall back to model named "main"

        Args:
            instruction_name: Name of the instruction prompt.

        Returns:
            The resolved model identifier string.

        """
        if instruction_name and instruction_name in self._prompt_models:
            prompt_model_ref = self._prompt_models[instruction_name]
            if prompt_model_ref in self._models:
                return self._models[prompt_model_ref]
            return prompt_model_ref

        if "main" in self._models:
            return self._models["main"]

        return ""

    def evaluate_prompt_text(
        self,
        prompt_name: str,
        prompt_value: object,
        context: WorkflowContext,
    ) -> str | None:
        """Evaluate a prompt value to get the text.

        Args:
            prompt_name: Name of the prompt for error logging.
            prompt_value: The prompt value (PromptSpec, callable, or string).
            context: Workflow context for prompt interpolation.

        Returns:
            The evaluated prompt text, or None on failure.

        """
        from streetrace.dsl.runtime.workflow import PromptSpec

        if isinstance(prompt_value, PromptSpec):
            try:
                return str(prompt_value.body(context))
            except (TypeError, KeyError) as e:
                logger.warning(
                    "Failed to evaluate prompt '%s': %s", prompt_name, e,
                )
                return None
        elif callable(prompt_value):
            try:
                return str(prompt_value(context))
            except (TypeError, KeyError) as e:
                logger.warning(
                    "Failed to evaluate prompt '%s': %s", prompt_name, e,
                )
                return None
        return str(prompt_value)

    @staticmethod
    def extract_content(response: object) -> str:
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

    async def call(
        self,
        prompt_name: str,
        context: WorkflowContext,
        *,
        model: str | None = None,
    ) -> AsyncGenerator[FlowEvent, None]:
        """Call an LLM with a named prompt, yielding events.

        Look up the prompt by name, evaluate it with the context,
        and call the LLM using LiteLLM. Validate against schema
        with automatic retry on failure.

        Args:
            prompt_name: Name of the prompt to use.
            context: Workflow context for prompt interpolation.
            model: Optional model override.

        Yields:
            LlmCallEvent when call initiates.
            LlmResponseEvent when call completes.

        Raises:
            SchemaValidationError: If schema validation fails after retries.

        """
        from streetrace.dsl.runtime.workflow import PromptSpec

        self._last_result = None

        model_info = f" using {model}" if model else ""
        logger.info("Calling LLM with prompt: %s%s", prompt_name, model_info)

        prompt_value = self._prompts.get(prompt_name)
        if not prompt_value:
            logger.warning(
                "Prompt '%s' not found in workflow context", prompt_name,
            )
            return

        prompt_text = self.evaluate_prompt_text(prompt_name, prompt_value, context)
        if prompt_text is None:
            return

        # Resolve schema from prompt spec
        prompt_spec = prompt_value if isinstance(prompt_value, PromptSpec) else None
        schema_name = getattr(prompt_spec, "schema", None) if prompt_spec else None
        schema_model = get_schema_model(schema_name, self._schemas)
        is_array = is_array_schema(schema_name)

        if schema_model:
            json_schema = schema_model.model_json_schema()
            prompt_text = enrich_prompt_with_schema(
                prompt_text, json_schema, is_array=is_array,
            )

        resolved_model = model or self.resolve_model(prompt_name)
        yield LlmCallEvent(
            prompt_name=prompt_name,
            model=resolved_model,
            prompt_text=prompt_text,
        )

        async for event in self._execute_with_validation(
            prompt_name=prompt_name,
            resolved_model=resolved_model,
            prompt_text=prompt_text,
            schema_model=schema_model,
            is_array=is_array,
        ):
            yield event

    async def _execute_with_validation(
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

        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt_text},
        ]
        last_content = ""
        last_error = ""

        for attempt in range(MAX_SCHEMA_RETRIES):
            try:
                response = await litellm.acompletion(
                    model=resolved_model,
                    messages=messages,
                )
                last_content = self.extract_content(response)

                if not schema_model:
                    self._last_result = last_content
                    if last_content:
                        yield LlmResponseEvent(
                            prompt_name=prompt_name,
                            content=last_content,
                        )
                    return

                # Use unified validate_response from schema_validator
                self._last_result = validate_response(
                    last_content, schema_model, is_array=is_array,
                )

            except (JSONParseError, SchemaValidationError) as e:
                last_error = str(e)
                logger.warning(
                    "Schema validation attempt %d/%d failed for '%s': %s",
                    attempt + 1,
                    MAX_SCHEMA_RETRIES,
                    prompt_name,
                    last_error,
                )
                _add_retry_feedback(
                    messages, last_content, last_error, attempt,
                )

            except Exception:
                logger.exception(
                    "LLM call failed for prompt '%s'", prompt_name,
                )
                self._last_result = None
                return
            else:
                yield LlmResponseEvent(
                    prompt_name=prompt_name,
                    content=last_content,
                )
                return

        schema_name = schema_model.__name__ if schema_model else "Unknown"
        raise SchemaValidationError(
            schema_name=schema_name,
            errors=[last_error],
            raw_response=last_content,
        )


def _add_retry_feedback(
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
