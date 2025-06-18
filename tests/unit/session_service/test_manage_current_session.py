"""Tests for the manage_current_session function in SessionManager class."""

from typing import cast
from unittest.mock import AsyncMock

import pytest
from google.adk.events import Event
from google.genai import types as genai_types


class TestManageCurrentSession:
    """Tests for the manage_current_session method of SessionManager."""

    async def test_no_function_calls(
        self,
        session_manager,
        json_session_service,
        sample_session,
    ):
        """Test manage_current_session with a session that has no function calls."""
        # Setup a session with no function calls
        session = sample_session.model_copy(deep=True)
        session.events = [
            Event(
                author="user",
                content=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text="User message")],
                ),
            ),
            Event(
                author="assistant",
                content=genai_types.Content(
                    role="assistant",
                    parts=[genai_types.Part.from_text(text="Assistant response")],
                ),
            ),
        ]

        # Mock get_current_session to return our session
        json_session_service.get_session = AsyncMock(return_value=session)

        # Mock replace_events to verify it's not called
        json_session_service.replace_events = AsyncMock()

        # Call manage_current_session
        await session_manager.manage_current_session()

        # Verify get_session was called
        json_session_service.get_session.assert_called_once_with(
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            session_id=session_manager.current_session_id,
        )

        # Verify replace_events was not called since there are no function calls
        json_session_service.replace_events.assert_not_called()

    async def test_less_than_20_function_calls(
        self,
        session_manager,
        json_session_service,
        sample_session,
        function_call_event,
        function_response_event,
    ):
        """Test manage_current_session with a session that has less than 20 fn calls."""
        # Setup a session with 5 function call/response pairs
        session = sample_session.model_copy(deep=True)
        events = []
        for i in range(5):
            # Create unique function call/response pairs
            call = function_call_event.model_copy(deep=True)
            call.content.parts[0].function_call.name = f"test_function_{i}"

            response = function_response_event.model_copy(deep=True)
            response.content.parts[0].function_response.name = f"test_function_{i}"

            events.append(call)
            events.append(response)

        session.events = events

        # Mock get_current_session to return our session
        json_session_service.get_session = AsyncMock(return_value=session)

        # Mock replace_events to verify it's not called
        json_session_service.replace_events = AsyncMock()

        # Call manage_current_session
        await session_manager.manage_current_session()

        # Verify get_session was called
        json_session_service.get_session.assert_called_once_with(
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            session_id=session_manager.current_session_id,
        )

        # Verify replace_events was not called since there are fewer than 20 fn calls
        json_session_service.replace_events.assert_not_called()

    async def test_more_than_20_function_calls(
        self,
        session_manager,
        json_session_service,
        sample_session,
        function_call_event,
        function_response_event,
    ):
        """Test manage_current_session with a session that has more than 20 fn calls."""
        # Setup a session with 25 function call/response pairs
        session = sample_session.model_copy(deep=True)
        events = []
        for i in range(25):
            # Create unique function call/response pairs
            call = function_call_event.model_copy(deep=True)
            call.content.parts[0].function_call.name = f"test_function_{i}"

            response = function_response_event.model_copy(deep=True)
            response.content.parts[0].function_response.name = f"test_function_{i}"

            events.append(call)
            events.append(response)

        session.events = events

        # Mock get_current_session to return our session
        json_session_service.get_session = AsyncMock(return_value=session)

        # Mock replace_events
        json_session_service.replace_events = AsyncMock()

        # Call manage_current_session
        await session_manager.manage_current_session()

        # Verify get_session was called
        json_session_service.get_session.assert_called_once_with(
            app_name=session_manager.app_name,
            user_id=session_manager.user_id,
            session_id=session_manager.current_session_id,
        )

        # Verify replace_events was called
        json_session_service.replace_events.assert_called_once()

        # Check that the new events list contains only the last 20 call/response pairs
        # plus any non-function events
        args = json_session_service.replace_events.call_args
        new_events = cast("list[Event]", args.kwargs.get("new_events"))

        # Count function response events in the new list
        function_response_count = sum(
            1
            for event in new_events
            if (
                event.content
                and event.content.parts
                and any(part.function_response for part in event.content.parts)
            )
        )

        # Verify we have exactly 20 function responses
        assert function_response_count == 20

        # Verify the total number of events is 40 (20 pairs of call/response)
        assert len(new_events) == 40

        # Verify the last function call/response pair is preserved
        assert new_events[-2].content
        assert new_events[-2].content.parts
        assert new_events[-2].content.parts[0].function_call
        assert new_events[-2].content.parts[0].function_call.name == "test_function_24"
        assert new_events[-1].content
        assert new_events[-1].content.parts
        assert new_events[-1].content.parts[0].function_response
        assert (
            new_events[-1].content.parts[0].function_response.name == "test_function_24"
        )

    async def test_mixed_content_with_function_calls(
        self,
        session_manager,
        json_session_service,
        sample_session,
        function_call_event,
        function_response_event,
        text_only_event,
        user_event,
    ):
        """Test manage_current_session with a mix of fn calls and regular messages."""
        # Setup a session with 25 function call/response pairs and some regular messages
        session = sample_session.model_copy(deep=True)
        events = [user_event, text_only_event]  # Start with some regular messages

        for i in range(25):
            # Add a regular message every 5 iterations
            if i % 5 == 0:
                events.append(user_event.model_copy(deep=True))
                events.append(text_only_event.model_copy(deep=True))

            # Create unique function call/response pairs
            call = function_call_event.model_copy(deep=True)
            call.content.parts[0].function_call.name = f"test_function_{i}"

            response = function_response_event.model_copy(deep=True)
            response.content.parts[0].function_response.name = f"test_function_{i}"

            events.append(call)
            events.append(response)

        session.events = events

        # Mock get_current_session to return our session
        json_session_service.get_session = AsyncMock(return_value=session)

        # Mock replace_events
        json_session_service.replace_events = AsyncMock()

        # Call manage_current_session
        await session_manager.manage_current_session()

        # Verify replace_events was called
        json_session_service.replace_events.assert_called_once()

        # Check that the new events list contains all non-function events
        # plus the last 20 function call/response pairs
        args = json_session_service.replace_events.call_args
        new_events = cast("list[Event]", args.kwargs.get("new_events"))

        # Count function response events in the new list
        function_response_count = sum(
            1
            for event in new_events
            if (
                event.content
                and event.content.parts
                and any(part.function_response for part in event.content.parts)
            )
        )

        # Verify we have exactly 20 function responses
        assert function_response_count == 20

        # Verify all non-function events are preserved
        text_only_count = sum(
            1
            for event in new_events
            if (
                event.content
                and event.content.parts
                and all(
                    part.text is not None
                    for part in event.content.parts
                    if hasattr(part, "text")
                )
            )
        )

        # We should have all the original text-only events
        original_text_only_count = sum(
            1
            for event in session.events
            if (
                event.content
                and event.content.parts
                and all(
                    part.text is not None
                    for part in event.content.parts
                    if hasattr(part, "text")
                )
            )
        )

        assert text_only_count == original_text_only_count

    async def test_session_not_found(self, session_manager, json_session_service):
        """Test manage_current_session when session is not found."""
        # Mock get_current_session to return None
        json_session_service.get_session = AsyncMock(return_value=None)

        # Call manage_current_session and expect ValueError
        with pytest.raises(ValueError, match="Session not found"):
            await session_manager.manage_current_session()

    async def test_mismatched_function_call_response(
        self,
        session_manager,
        json_session_service,
        sample_session,
        function_call_event,
        function_response_event,
    ):
        """Test manage_current_session with mismatched function call/response pairs."""
        # Setup a session with mismatched function call/response
        session = sample_session.model_copy(deep=True)

        # Create a mismatched pair
        call = function_call_event.model_copy(deep=True)
        call.content.parts[0].function_call.name = "function_a"

        response = function_response_event.model_copy(deep=True)
        response.content.parts[
            0
        ].function_response.name = "function_b"  # Different name

        session.events = [call, response]

        # Mock get_current_session to return our session
        json_session_service.get_session = AsyncMock(return_value=session)

        # Call manage_current_session - the implementation doesn't actually check for
        # mismatched pairs so we just verify it runs without error
        await session_manager.manage_current_session()

    async def test_function_response_without_call(
        self,
        session_manager,
        json_session_service,
        sample_session,
        function_response_event,
    ):
        """Test manage_current_session with a fn response without a preceding call."""
        # Setup a session with a function response but no call
        session = sample_session.model_copy(deep=True)
        session.events = [function_response_event]

        # Mock get_current_session to return our session
        json_session_service.get_session = AsyncMock(return_value=session)

        # Call manage_current_session - the implementation doesn't actually check for
        # orphaned responses so we just verify it runs without error
        await session_manager.manage_current_session()

    async def test_missing_content_or_parts(
        self,
        session_manager,
        json_session_service,
        sample_session,
        empty_content_event,
        empty_parts_event,
    ):
        """Test manage_current_session with events missing content or parts."""
        # Setup a session with events missing content or parts
        session = sample_session.model_copy(deep=True)

        # Create a function call with missing content
        call_missing_content = empty_content_event.model_copy(deep=True)

        # Create a function response with empty parts
        response_empty_parts = empty_parts_event.model_copy(deep=True)

        session.events = [call_missing_content, response_empty_parts]

        # Mock get_current_session to return our session
        json_session_service.get_session = AsyncMock(return_value=session)

        # Mock replace_events
        json_session_service.replace_events = AsyncMock()

        # Call manage_current_session - should not raise an error
        # since these events don't have function calls/responses
        await session_manager.manage_current_session()

        # Verify replace_events was not called
        json_session_service.replace_events.assert_not_called()
