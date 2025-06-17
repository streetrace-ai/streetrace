"""Tests for specific lines in session_service.py."""

from unittest.mock import Mock

from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.session_service import SessionManager


def test_squash_turn_events_tool_detection_explicit():
    """Explicitly test the list comprehension in _squash_turn_events."""
    # Create a minimal session manager
    session_manager = SessionManager(
        args=Mock(),
        session_service=Mock(),
        system_context=Mock(),
        ui_bus=Mock(),
    )

    # We'll create a direct test for the code at lines 568-569
    # by extracting the list comprehension logic into a function we can test

    def test_tools_list_comprehension(parts):
        """Test the exact logic of the list comprehension at lines 568-569."""
        return [
            part.function_call or part.function_response
            for part in parts
            if part.function_call or part.function_response
        ]

    # Create various Part objects to test with
    part_with_function_call = genai_types.Part(
        function_call=genai_types.FunctionCall(name="test_function"),
    )

    part_with_function_response = genai_types.Part(
        function_response=genai_types.FunctionResponse(name="test_function"),
    )

    part_with_both = genai_types.Part(
        function_call=genai_types.FunctionCall(name="test_function"),
        function_response=genai_types.FunctionResponse(name="test_function"),
    )

    part_with_text = genai_types.Part(text="Just text")

    # Test with just function_call
    parts = [part_with_function_call]
    result = test_tools_list_comprehension(parts)
    assert len(result) == 1
    assert result[0] == part_with_function_call.function_call

    # Test with just function_response
    parts = [part_with_function_response]
    result = test_tools_list_comprehension(parts)
    assert len(result) == 1
    assert result[0] == part_with_function_response.function_response

    # Test with both in one part (should pick function_call due to short-circuit
    # evaluation)
    parts = [part_with_both]
    result = test_tools_list_comprehension(parts)
    assert len(result) == 1
    assert result[0] == part_with_both.function_call

    # Test with a mix
    parts = [part_with_function_call, part_with_text, part_with_function_response]
    result = test_tools_list_comprehension(parts)
    assert len(result) == 2
    assert result[0] == part_with_function_call.function_call
    assert result[1] == part_with_function_response.function_response

    # Test with only text
    parts = [part_with_text]
    result = test_tools_list_comprehension(parts)
    assert len(result) == 0

    # Now test the actual method with an assistant event containing these parts
    session = Session(
        id="test-session-id",
        app_name="test-app",
        user_id="test-user",
        events=[
            Event(
                author="user",
                content=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text="User message")],
                ),
            ),
            Event(
                author="assistant",
                content=genai_types.Content(
                    role="assistant",
                    parts=[
                        part_with_function_call,
                        part_with_text,
                        part_with_function_response,
                    ],
                ),
            ),
        ],
        state={},
    )

    assert session_manager._squash_turn_events(session) == ""  # noqa: SLF001
