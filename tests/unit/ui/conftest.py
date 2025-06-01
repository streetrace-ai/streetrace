"""Shared fixtures for UI module tests."""

from typing import Any
from unittest.mock import Mock

import pytest
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai.types import Content, FunctionCall, FunctionResponse, Part
from rich.console import Console


@pytest.fixture
def mock_console() -> Console:
    """Create a mock Rich Console for testing rendering output."""
    return Mock(spec=Console)


@pytest.fixture
def sample_author() -> str:
    """Provide a sample author name for events."""
    return "TestAgent"


@pytest.fixture
def sample_text_content() -> str:
    """Provide sample text content for testing."""
    return "This is a test message from the AI assistant."


@pytest.fixture
def sample_markdown_content() -> str:
    """Provide sample markdown content for testing."""
    return "Here is some **bold** text and `code` snippet."


@pytest.fixture
def sample_long_text() -> str:
    """Provide long text that exceeds trimming limits."""
    return (
        "This is a very long line that exceeds the maximum length limit and should"
        + " be trimmed with ellipsis" * 10
    )


@pytest.fixture
def sample_multiline_text() -> str:
    """Provide multiline text for testing line trimming."""
    lines = [f"Line {i}: Some content here" for i in range(1, 11)]
    return "\n".join(lines)


@pytest.fixture
def sample_function_call_data() -> dict[str, Any]:
    """Provide sample function call data."""
    return {
        "name": "test_function",
        "args": {"param1": "value1", "param2": 42},
        "id": "call_123",
    }


@pytest.fixture
def sample_function_response_data() -> dict[str, Any]:
    """Provide sample function response data."""
    return {
        "id": "call_123",
        "name": "test_function",
        "response": {
            "result": "success",
            "output": "Function executed successfully",
            "data": {"key": "value"},
        },
    }


@pytest.fixture
def text_part(sample_text_content: str) -> Part:
    """Create a Part with text content."""
    return Part(text=sample_text_content)


@pytest.fixture
def markdown_part(sample_markdown_content: str) -> Part:
    """Create a Part with markdown content."""
    return Part(text=sample_markdown_content)


@pytest.fixture
def function_call_part(sample_function_call_data: dict[str, Any]) -> Part:
    """Create a Part with function call."""
    function_call = FunctionCall(**sample_function_call_data)
    return Part(function_call=function_call)


@pytest.fixture
def function_response_part(sample_function_response_data: dict[str, Any]) -> Part:
    """Create a Part with function response."""
    function_response = FunctionResponse(**sample_function_response_data)
    return Part(function_response=function_response)


@pytest.fixture
def empty_function_response_part() -> Part:
    """Create a Part with empty function response."""
    function_response = FunctionResponse(
        id="call_456",
        name="empty_function",
        response=None,
    )
    return Part(function_response=function_response)


@pytest.fixture
def content_with_text(text_part: Part) -> Content:
    """Create Content with text parts."""
    return Content(parts=[text_part], role="assistant")


@pytest.fixture
def content_with_function_call(function_call_part: Part) -> Content:
    """Create Content with function call."""
    return Content(parts=[function_call_part], role="assistant")


@pytest.fixture
def content_with_function_response(function_response_part: Part) -> Content:
    """Create Content with function response."""
    return Content(parts=[function_response_part], role="assistant")


@pytest.fixture
def content_with_mixed_parts(
    text_part: Part,
    function_call_part: Part,
    function_response_part: Part,
) -> Content:
    """Create Content with mixed part types."""
    return Content(
        parts=[text_part, function_call_part, function_response_part],
        role="assistant",
    )


@pytest.fixture
def escalation_actions() -> EventActions:
    """Create EventActions with escalation enabled."""
    return EventActions(escalate=True)


@pytest.fixture
def non_escalation_actions() -> EventActions:
    """Create EventActions without escalation."""
    return EventActions(escalate=False)


@pytest.fixture
def basic_event(sample_author: str, content_with_text: Content) -> Event:
    """Create a basic Event with text content."""
    return Event(
        author=sample_author,
        content=content_with_text,
        turn_complete=False,
        partial=False,
    )


@pytest.fixture
def final_response_event(sample_author: str, content_with_text: Content) -> Event:
    """Create a final response Event."""
    return Event(
        author=sample_author,
        content=content_with_text,
        turn_complete=True,
        partial=False,
    )


@pytest.fixture
def escalation_event(
    sample_author: str,
    content_with_text: Content,
    escalation_actions: EventActions,
) -> Event:
    """Create an Event with escalation."""
    return Event(
        author=sample_author,
        content=content_with_text,
        turn_complete=True,
        partial=False,
        actions=escalation_actions,
        error_message="Something went wrong",
    )


@pytest.fixture
def escalation_event_no_message(
    sample_author: str,
    content_with_text: Content,
    escalation_actions: EventActions,
) -> Event:
    """Create an Event with escalation but no error message."""
    return Event(
        author=sample_author,
        content=content_with_text,
        turn_complete=True,
        partial=False,
        actions=escalation_actions,
        error_message=None,
    )


@pytest.fixture
def function_call_event(
    sample_author: str,
    content_with_function_call: Content,
) -> Event:
    """Create an Event with function call."""
    return Event(
        author=sample_author,
        content=content_with_function_call,
        turn_complete=False,
        partial=False,
    )


@pytest.fixture
def function_response_event(
    sample_author: str,
    content_with_function_response: Content,
) -> Event:
    """Create an Event with function response."""
    return Event(
        author=sample_author,
        content=content_with_function_response,
        turn_complete=False,
        partial=False,
    )


@pytest.fixture
def empty_event(sample_author: str) -> Event:
    """Create an Event with no content."""
    return Event(
        author=sample_author,
        content=None,
        turn_complete=False,
        partial=False,
    )


@pytest.fixture
def event_empty_content(sample_author: str) -> Event:
    """Create an Event with empty content (no parts)."""
    empty_content = Content(parts=[], role="assistant")
    return Event(
        author=sample_author,
        content=empty_content,
        turn_complete=False,
        partial=False,
    )
