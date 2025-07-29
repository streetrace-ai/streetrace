"""Tests for SessionService.validate method.

This module tests the validate method in JSONSessionService.
The validate method ensures that function calls have matching function responses in the
next event, removing orphaned calls or responses to prevent LLM call failures.

Key scenarios tested:
1. Valid sessions return the same instance
2. Invalid sessions return a corrected copy via replace_events
"""

from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.session.session_manager import SessionManager


class TestSessionValidation:
    """Test the validate method behavior."""

    async def test_validate_returns_same_instance_for_valid_sessions(
        self,
        shallow_session_manager: SessionManager,
        sample_session: Session,
        user_event: Event,
        text_only_event: Event,
    ) -> None:
        """Validate returns the same instance for sessions with no errors."""
        # Test with empty session
        empty_session = sample_session.model_copy(deep=True)
        empty_session.events = []
        result = await shallow_session_manager.validate_session(empty_session)
        assert result is empty_session

        # Test with text-only events
        text_session = sample_session.model_copy(deep=True)
        text_session.events = [user_event, text_only_event]
        result = await shallow_session_manager.validate_session(text_session)
        assert result is text_session

    async def test_validate_returns_same_instance_for_valid_function_pairs(
        self,
        shallow_session_manager: SessionManager,
        sample_session: Session,
        user_event: Event,
        function_call_event: Event,
        function_response_event: Event,
        text_only_event: Event,
    ) -> None:
        """Validate returns the same instance for sessions with valid pairs."""
        # Create session with valid function call followed by response
        session = sample_session.model_copy(deep=True)
        session.events = [
            user_event,
            function_call_event,
            function_response_event,
            text_only_event,
        ]

        result = await shallow_session_manager.validate_session(session)
        assert result is session

    async def test_validate_returns_corrected_copy_for_orphaned_function_call(
        self,
        shallow_session_manager: SessionManager,
        mock_json_session_service,
        sample_session: Session,
        user_event: Event,
        function_call_event: Event,
        text_only_event: Event,
    ) -> None:
        """Validate returns a corrected copy for sessions with orphaned calls."""
        # Create session with orphaned function call
        session = sample_session.model_copy(deep=True)
        session.events = [
            user_event,
            function_call_event,  # Orphaned call
            text_only_event,
        ]

        # Mock replace_events to verify it's called
        corrected_session = sample_session.model_copy(deep=True)
        corrected_session.events = [user_event, text_only_event]

        mock_json_session_service.replace_events.return_value = corrected_session
        result = await shallow_session_manager.validate_session(session)

        # Should call replace_events
        mock_json_session_service.replace_events.assert_called_once()

        # Should return corrected session, not original
        assert result is corrected_session
        assert result is not session

    async def test_validate_returns_corrected_copy_for_orphaned_function_response(
        self,
        shallow_session_manager: SessionManager,
        mock_json_session_service,
        sample_session: Session,
        user_event: Event,
        function_response_event: Event,
        text_only_event: Event,
    ) -> None:
        """Validate returns a corrected copy for sessions with orphaned responses."""
        # Create session with orphaned function response
        session = sample_session.model_copy(deep=True)
        session.events = [
            user_event,
            function_response_event,  # Orphaned response
            text_only_event,
        ]

        # Mock replace_events to verify it's called
        corrected_session = sample_session.model_copy(deep=True)
        corrected_session.events = [user_event, text_only_event]

        mock_json_session_service.replace_events.return_value = corrected_session
        result = await shallow_session_manager.validate_session(session)

        # Should call replace_events
        mock_json_session_service.replace_events.assert_called_once()

        # Should return corrected session, not original
        assert result is corrected_session
        assert result is not session

    async def test_validate_returns_corrected_copy_for_separated_call_response(
        self,
        shallow_session_manager: SessionManager,
        mock_json_session_service,
        sample_session: Session,
        user_event: Event,
        function_call_event: Event,
        function_response_event: Event,
        text_only_event: Event,
    ) -> None:
        """Validate returns a corrected copy when call and response are separated."""
        # Create session with function call and response separated by text
        session = sample_session.model_copy(deep=True)
        session.events = [
            user_event,
            function_call_event,  # Function call
            text_only_event,  # Intervening event
            function_response_event,  # Response separated from call
        ]

        # Mock replace_events to verify it's called
        corrected_session = sample_session.model_copy(deep=True)
        corrected_session.events = [user_event, text_only_event]

        mock_json_session_service.replace_events.return_value = corrected_session
        result = await shallow_session_manager.validate_session(session)

        # Should call replace_events
        mock_json_session_service.replace_events.assert_called_once()

        # Should return corrected session, not original
        assert result is corrected_session
        assert result is not session

    async def test_validate_handles_mixed_content_events(
        self,
        shallow_session_manager: SessionManager,
        sample_session: Session,
        user_event: Event,
        mixed_content_event: Event,
        function_response_event: Event,
        text_only_event: Event,
    ) -> None:
        """Validate handles events with both text and function calls correctly."""
        # Create session with mixed content event followed by response
        session = sample_session.model_copy(deep=True)
        session.events = [
            user_event,
            mixed_content_event,  # Contains both text and function call
            function_response_event,  # Matching response
            text_only_event,
        ]

        result = await shallow_session_manager.validate_session(session)
        assert result is session  # Should be valid

    async def test_validate_handles_empty_content_events(
        self,
        shallow_session_manager: SessionManager,
        sample_session: Session,
        user_event: Event,
        empty_content_event: Event,
        text_only_event: Event,
    ) -> None:
        """Test that validate handles events with empty content correctly."""
        # Create session with empty content events (should be ignored)
        session = sample_session.model_copy(deep=True)
        session.events = [
            empty_content_event,
            user_event,
            text_only_event,
            empty_content_event,
        ]

        result = await shallow_session_manager.validate_session(session)
        assert result is session  # Should be valid (no function calls to validate)

    async def test_validate_complex_scenario_with_multiple_errors(
        self,
        shallow_session_manager: SessionManager,
        mock_json_session_service,
        sample_session: Session,
        user_event: Event,
        function_call_event: Event,
        function_response_event: Event,
        text_only_event: Event,
    ) -> None:
        """Validate handles complex scenarios with multiple function call issues."""
        # Create a second orphaned function call
        orphaned_call = Event(
            author="assistant",
            content=genai_types.Content(
                role="assistant",
                parts=[
                    genai_types.Part(
                        function_call=genai_types.FunctionCall(
                            name="orphaned_function",
                            args={},
                        ),
                    ),
                ],
            ),
        )

        # Create complex session:
        # Valid pair (call->response), orphaned call, text, another orphaned call
        session = sample_session.model_copy(deep=True)
        session.events = [
            user_event,
            function_call_event,  # Valid call
            function_response_event,  # Matching response
            orphaned_call,  # Orphaned call
            text_only_event,  # Text event
            orphaned_call,  # Another orphaned call
        ]

        # Mock replace_events to verify it's called
        corrected_session = sample_session.model_copy(deep=True)
        corrected_session.events = [
            user_event,
            function_call_event,
            function_response_event,
            text_only_event,
        ]

        mock_json_session_service.replace_events.return_value = corrected_session
        result = await shallow_session_manager.validate_session(session)

        # Should call replace_events
        mock_json_session_service.replace_events.assert_called_once()

        # Should return corrected session, not original
        assert result is corrected_session
        assert result is not session
