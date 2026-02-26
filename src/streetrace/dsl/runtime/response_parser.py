"""Response parsing utilities for DSL runtime.

Provide pure functions for extracting JSON from LLM responses,
enriching prompts with schema instructions, and resolving schema
models from prompt specs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from streetrace.dsl.runtime.errors import JSONParseError

if TYPE_CHECKING:
    from pydantic import BaseModel

_CODE_BLOCK_FENCE = "```"
"""Markdown code block fence delimiter."""


def deep_parse_json_strings(data: object) -> object:
    """Recursively parse JSON strings in nested data structures.

    LLMs sometimes return nested lists/objects as JSON strings instead of
    actual arrays/objects. Recursively traverse the data and parse any
    string values that look like JSON arrays or objects.

    Args:
        data: Data structure to process.

    Returns:
        Data with JSON strings parsed into native Python types.

    """
    if isinstance(data, dict):
        return {key: deep_parse_json_strings(val) for key, val in data.items()}

    if isinstance(data, list):
        return [deep_parse_json_strings(item) for item in data]

    if isinstance(data, str):
        text = data.strip()
        # Only try to parse strings that look like JSON arrays or objects
        if (text.startswith("[") and text.endswith("]")) or (
            text.startswith("{") and text.endswith("}")
        ):
            try:
                parsed = json.loads(text)
                # Recursively parse in case of nested JSON strings
                return deep_parse_json_strings(parsed)
            except (json.JSONDecodeError, ValueError):
                pass

    return data


def extract_code_blocks(content: str) -> list[str]:
    """Extract code block contents from markdown text.

    Scan line-by-line to find fenced code blocks and extract their
    contents. This approach is more reliable and debuggable than regex.

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


def parse_json_response(content: str) -> dict[str, object] | list[object]:
    """Parse JSON from LLM response, handling markdown code blocks.

    Extract JSON content from LLM responses which may include markdown
    formatting. Supports plain JSON and JSON wrapped in code blocks.

    Args:
        content: Raw LLM response content.

    Returns:
        Parsed JSON as a dictionary or list.

    Raises:
        JSONParseError: If content cannot be parsed as JSON or contains
            multiple ambiguous code blocks.

    """
    code_blocks = extract_code_blocks(content)

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


def enrich_prompt_with_schema(
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


def is_array_schema(schema_name: str | None) -> bool:
    """Check if a schema name indicates an array type (e.g., Finding[]).

    Args:
        schema_name: Schema name to check, or None.

    Returns:
        True if schema ends with [], False otherwise.

    """
    if not schema_name or not isinstance(schema_name, str):
        return False
    return bool(schema_name.endswith("[]"))


def get_schema_model(
    schema_name: str | None,
    schemas: dict[str, type[BaseModel]],
) -> type[BaseModel] | None:
    """Get the Pydantic model for a schema name.

    Look up the schema name and resolve it to the corresponding
    Pydantic model class. Strip [] suffix for array types.

    Args:
        schema_name: Schema name, may be None.
        schemas: Available schema name to Pydantic model mapping.

    Returns:
        Pydantic model class if schema exists, None otherwise.

    """
    if not schema_name:
        return None

    # Strip [] suffix for array types
    base_name = schema_name
    if isinstance(schema_name, str) and schema_name.endswith("[]"):
        base_name = schema_name[:-2]

    return schemas.get(base_name)
