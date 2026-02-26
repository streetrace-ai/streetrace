"""Schema validation for DSL runtime agent and LLM outputs.

Provide unified JSON parsing and Pydantic schema validation with
retry support. Used by both DslAgentWorkflow (agent outputs) and
PromptLlmCaller (direct LLM call outputs).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from streetrace.dsl.runtime.errors import JSONParseError, SchemaValidationError
from streetrace.dsl.runtime.response_parser import (
    deep_parse_json_strings,
    parse_json_response,
)
from streetrace.log import get_logger

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = get_logger(__name__)


@dataclass(frozen=True)
class SchemaInfo:
    """Resolved schema information for an agent's output."""

    schema_name: str | None
    """Full schema name (e.g., 'Finding[]')."""

    schema_model: type[BaseModel]
    """Pydantic model class for validation."""

    is_array: bool
    """True if expecting an array of schema items."""


def validate_response(
    raw_response: str,
    schema_model: type[BaseModel],
    *,
    is_array: bool,
) -> object:
    """Validate a raw response string against a Pydantic schema.

    Parse the response as JSON, pre-process nested JSON strings, and
    validate against the Pydantic model.

    Args:
        raw_response: The raw text response to validate.
        schema_model: Pydantic model class for validation.
        is_array: True if expecting an array of schema items.

    Returns:
        Validated result as dict or list of dicts.

    Raises:
        JSONParseError: If response cannot be parsed as JSON.
        SchemaValidationError: If parsed response fails validation.

    """
    from pydantic import ValidationError as PydanticValidationError

    # Parse JSON (let JSONParseError propagate)
    parsed = parse_json_response(raw_response)

    # Pre-process to handle JSON strings in nested fields
    parsed = deep_parse_json_strings(parsed)  # type: ignore[assignment]

    # Validate against schema
    try:
        if is_array:
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
            return validated_items
        validated = schema_model.model_validate(parsed)
        return validated.model_dump()
    except PydanticValidationError as e:
        raise SchemaValidationError(
            schema_name=schema_model.__name__,
            errors=[str(e)],
            raw_response=raw_response,
        ) from e


def resolve_agent_schema(
    agent_name: str,
    agents: dict[str, dict[str, object]],
    prompts: dict[str, object],
    schemas: dict[str, type[BaseModel]],
) -> SchemaInfo | None:
    """Resolve the expected schema from an agent's instruction prompt.

    Look up the agent's instruction prompt and extract its schema
    definition. Return schema metadata for validation.

    Args:
        agent_name: Name of the agent to resolve schema for.
        agents: Agent definitions dict.
        prompts: Prompt definitions dict.
        schemas: Schema name to Pydantic model mapping.

    Returns:
        SchemaInfo if schema is defined, None otherwise.

    """
    agent_def = agents.get(agent_name)
    if not agent_def:
        return None

    instruction_name = agent_def.get("instruction")
    if not instruction_name or not isinstance(instruction_name, str):
        return None

    prompt_spec = prompts.get(instruction_name)
    if not prompt_spec:
        return None

    schema_name = getattr(prompt_spec, "schema", None)
    if not schema_name or not isinstance(schema_name, str):
        return None

    # Check if array type
    is_array = schema_name.endswith("[]")
    base_name = schema_name[:-2] if is_array else schema_name

    schema_model = schemas.get(base_name)
    if not schema_model:
        return None

    return SchemaInfo(
        schema_name=schema_name,
        schema_model=schema_model,
        is_array=is_array,
    )
