"""Test utilities for Gemini tests.

This module provides helper functions and classes for testing Gemini implementation.
"""

from dataclasses import dataclass
from typing import Any, List, Optional

from google.genai import types


@dataclass
class MockPart:
    """Mock for Gemini Part class."""

    text: Optional[str] = None
    function_call: Optional[dict] = None
    function_response: Optional[dict] = None

    @classmethod
    def from_text(cls, text: str) -> "MockPart":
        """Create a text part."""
        return cls(text=text)

    @classmethod
    def from_function_call(cls, name: str, args: dict) -> "MockPart":
        """Create a function call part."""
        return cls(function_call={"name": name, "args": args, "id": None})

    @classmethod
    def from_function_response(cls, name: str, response: dict) -> "MockPart":
        """Create a function response part."""
        return cls(function_response={"name": name, "response": response})


@dataclass
class MockContent:
    """Mock for Gemini Content class."""

    role: str
    parts: List[MockPart]


@dataclass
class MockCandidate:
    """Mock for Gemini candidate in response."""

    content: Any
    finish_reason: Optional[str] = None
    finish_message: Optional[str] = None


@dataclass
class MockUsageMetadata:
    """Mock for Gemini usage metadata."""

    prompt_token_count: int = 0
    candidates_token_count: int = 0
    tool_use_prompt_token_count: int = 0


def create_mock_response(
    text: Optional[str] = None,
    parts: Optional[List[MockPart]] = None,
    finish_reason: Optional[str] = None,
    finish_message: Optional[str] = None,
    prompt_tokens: int = 0,
    response_tokens: int = 0,
    tool_tokens: int = 0,
) -> Any:
    """Create a mock Gemini response for testing.

    Args:
        text: The text content of the response
        parts: Additional content parts
        finish_reason: The reason generation finished
        finish_message: Message explaining finish reason
        prompt_tokens: Number of prompt tokens
        response_tokens: Number of response tokens
        tool_tokens: Number of tool tokens

    Returns:
        Mock Gemini response object
    """
    content = MockContent(role="model", parts=parts or [])

    candidate = MockCandidate(
        content=content,
        finish_reason=finish_reason,
        finish_message=finish_message,
    )

    usage = MockUsageMetadata(
        prompt_token_count=prompt_tokens,
        candidates_token_count=response_tokens,
        tool_use_prompt_token_count=tool_tokens,
    )

    response = type("MockResponse", (), {
        "text": text,
        "candidates": [candidate],
        "usage_metadata": usage,
    })

    return response


def create_mock_tool_call_response(
    tool_name: str,
    tool_args: dict,
    tool_id: Optional[str] = None,
    finish_reason: str = "TOOL_CALL",
    finish_message: str = "Tool call requested",
) -> Any:
    """Create a mock Gemini response with a tool call.

    Args:
        tool_name: Name of the tool being called
        tool_args: Arguments for the tool call
        tool_id: Optional ID for the tool call
        finish_reason: The reason generation finished
        finish_message: Message explaining finish reason

    Returns:
        Mock Gemini response object with tool call
    """
    function_call = {
        "name": tool_name,
        "args": tool_args,
        "id": tool_id,
    }

    part = MockPart(function_call=function_call)

    content = MockContent(role="model", parts=[part])

    candidate = MockCandidate(
        content=content,
        finish_reason=finish_reason,
        finish_message=finish_message,
    )

    response = type("MockResponse", (), {
        "text": "",
        "candidates": [candidate],
        "usage_metadata": None,
    })

    return response