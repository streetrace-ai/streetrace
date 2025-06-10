"""Test escalation handling in ADK event renderer.

This module tests the rendering of events that contain escalations,
including error messages, escalation indicators, and proper styling.
"""

from streetrace.ui.adk_event_renderer import render_event
from streetrace.ui.colors import Styles


class TestEscalationRendering:
    """Test rendering of events with escalations."""

    def test_render_escalation_event_with_message(
        self,
        escalation_event,
        mock_console,
        sample_author,
    ):
        """Test rendering an escalation event with error message."""
        render_event(escalation_event, mock_console)

        # Should have two print calls: one for escalation, one for content
        assert mock_console.print.call_count == 2

        # First call should be for escalation
        escalation_call = mock_console.print.call_args_list[0]
        expected_author = f"[bold]{sample_author}:[/bold]\n"
        assert escalation_call[0][0] == expected_author
        assert "Agent escalated: Something went wrong" in escalation_call[0][1]
        assert escalation_call[1]["style"] == Styles.RICH_ERROR

    def test_render_escalation_event_without_message(
        self,
        escalation_event_no_message,
        mock_console,
        sample_author,
    ):
        """Test rendering an escalation event without error message."""
        render_event(escalation_event_no_message, mock_console)

        # Should have two print calls: one for escalation, one for content
        assert mock_console.print.call_count == 2

        # First call should be for escalation with default message
        escalation_call = mock_console.print.call_args_list[0]
        expected_author = f"[bold]{sample_author}:[/bold]\n"
        assert escalation_call[0][0] == expected_author
        assert "Agent escalated: No specific message." in escalation_call[0][1]
        assert escalation_call[1]["style"] == Styles.RICH_ERROR

    def test_render_escalation_requires_final_response(
        self,
        mock_console,
        sample_author,
        escalation_actions,
    ):
        """Test that escalation only renders for final response events."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        # Create non-final response event with escalation actions
        # (partial=True makes it non-final)
        text_part = Part(text="Some content")
        content = Content(parts=[text_part], role="assistant")
        non_final_escalation_event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=True,  # This makes it non-final response
            actions=escalation_actions,
            error_message="Should not show this",
        )

        render_event(non_final_escalation_event, mock_console)

        # Should only have one print call for content, no escalation
        mock_console.print.assert_called_once()

        call_args = mock_console.print.call_args
        # Should not contain escalation message
        assert "Agent escalated" not in str(call_args)

    def test_render_escalation_requires_escalate_flag(
        self,
        mock_console,
        sample_author,
        non_escalation_actions,
    ):
        """Test that escalation doesn't render when escalate=False."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        text_part = Part(text="Some content")
        content = Content(parts=[text_part], role="assistant")
        final_non_escalation_event = Event(
            author=sample_author,
            content=content,
            turn_complete=True,  # Final response
            partial=False,
            actions=non_escalation_actions,  # escalate=False
            error_message="Should not show this",
        )

        render_event(final_non_escalation_event, mock_console)

        # Should only have one print call for content, no escalation
        mock_console.print.assert_called_once()

        call_args = mock_console.print.call_args
        # Should not contain escalation message
        assert "Agent escalated" not in str(call_args)

    def test_render_escalation_requires_actions(self, mock_console, sample_author):
        """Test that escalation doesn't render when actions has escalate=None."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        text_part = Part(text="Some content")
        content = Content(parts=[text_part], role="assistant")
        final_no_actions_event = Event(
            author=sample_author,
            content=content,
            turn_complete=True,  # Final response
            partial=False,
            # actions defaults to EventActions(escalate=None)
            error_message="Should not show this",
        )

        render_event(final_no_actions_event, mock_console)

        # Should only have one print call for content, no escalation
        mock_console.print.assert_called_once()

        call_args = mock_console.print.call_args
        # Should not contain escalation message
        assert "Agent escalated" not in str(call_args)

    def test_render_escalation_with_empty_error_message(
        self,
        mock_console,
        sample_author,
        escalation_actions,
    ):
        """Test rendering escalation with empty string error message."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        text_part = Part(text="Some content")
        content = Content(parts=[text_part], role="assistant")
        empty_message_event = Event(
            author=sample_author,
            content=content,
            turn_complete=True,
            partial=False,
            actions=escalation_actions,
            error_message="",  # Empty string
        )

        render_event(empty_message_event, mock_console)

        # Should have escalation with default message
        escalation_call = mock_console.print.call_args_list[0]
        assert "Agent escalated: No specific message." in escalation_call[0][1]

    def test_render_escalation_with_whitespace_error_message(
        self,
        mock_console,
        sample_author,
        escalation_actions,
    ):
        """Test rendering escalation with whitespace-only error message."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        text_part = Part(text="Some content")
        content = Content(parts=[text_part], role="assistant")
        whitespace_message_event = Event(
            author=sample_author,
            content=content,
            turn_complete=True,
            partial=False,
            actions=escalation_actions,
            error_message="   ",  # Whitespace only
        )

        render_event(whitespace_message_event, mock_console)

        # Should have escalation with actual whitespace message
        escalation_call = mock_console.print.call_args_list[0]
        assert "Agent escalated:    " in escalation_call[0][1]

    def test_render_escalation_with_multiline_error_message(
        self,
        mock_console,
        sample_author,
        escalation_actions,
    ):
        """Test rendering escalation with multiline error message."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        text_part = Part(text="Some content")
        content = Content(parts=[text_part], role="assistant")
        multiline_error = (
            "Error on line 1\nError details on line 2\nMore context on line 3"
        )
        multiline_message_event = Event(
            author=sample_author,
            content=content,
            turn_complete=True,
            partial=False,
            actions=escalation_actions,
            error_message=multiline_error,
        )

        render_event(multiline_message_event, mock_console)

        # Should have escalation with full multiline message
        escalation_call = mock_console.print.call_args_list[0]
        assert f"Agent escalated: {multiline_error}" in escalation_call[0][1]

    def test_render_escalation_with_special_characters(
        self,
        mock_console,
        sample_author,
        escalation_actions,
    ):
        """Test rendering escalation with special characters in error message."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        text_part = Part(text="Some content")
        content = Content(parts=[text_part], role="assistant")
        special_error = "Error with 'quotes' and \"double quotes\" and 🚗💨 emojis"
        special_message_event = Event(
            author=sample_author,
            content=content,
            turn_complete=True,
            partial=False,
            actions=escalation_actions,
            error_message=special_error,
        )

        render_event(special_message_event, mock_console)

        # Should handle special characters properly
        escalation_call = mock_console.print.call_args_list[0]
        assert f"Agent escalated: {special_error}" in escalation_call[0][1]

    def test_render_escalation_uses_error_style(self, escalation_event, mock_console):
        """Test that escalation messages use the error style."""
        render_event(escalation_event, mock_console)

        escalation_call = mock_console.print.call_args_list[0]
        assert escalation_call[1]["style"] == Styles.RICH_ERROR

    def test_render_escalation_with_content_still_renders_content(
        self,
        escalation_event,
        mock_console,
    ):
        """Test that escalation events still render their content."""
        render_event(escalation_event, mock_console)

        # Should have two calls: escalation and content
        assert mock_console.print.call_count == 2

        # Second call should be for content
        content_call = mock_console.print.call_args_list[1]
        assert content_call[1]["style"] == Styles.RICH_MODEL  # Final response style

    def test_render_escalation_only_without_content(
        self,
        mock_console,
        sample_author,
        escalation_actions,
    ):
        """Test rendering escalation event with no content."""
        from google.adk.events import Event

        escalation_only_event = Event(
            author=sample_author,
            content=None,  # No content
            turn_complete=True,
            partial=False,
            actions=escalation_actions,
            error_message="Critical error occurred",
        )

        render_event(escalation_only_event, mock_console)

        # Should only have one call for escalation
        mock_console.print.assert_called_once()

        call_args = mock_console.print.call_args
        assert "Agent escalated: Critical error occurred" in call_args[0][1]
        assert call_args[1]["style"] == Styles.RICH_ERROR

    def test_render_escalation_author_formatting(
        self,
        escalation_event,
        mock_console,
        sample_author,
    ):
        """Test that escalation author is formatted consistently."""
        render_event(escalation_event, mock_console)

        escalation_call = mock_console.print.call_args_list[0]
        expected_author = f"[bold]{sample_author}:[/bold]\n"
        assert escalation_call[0][0] == expected_author

    def test_render_escalation_with_long_error_message(
        self,
        mock_console,
        sample_author,
        escalation_actions,
    ):
        """Test rendering escalation with very long error message."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        text_part = Part(text="Some content")
        content = Content(parts=[text_part], role="assistant")
        long_error = "A" * 1000  # Very long error message
        long_message_event = Event(
            author=sample_author,
            content=content,
            turn_complete=True,
            partial=False,
            actions=escalation_actions,
            error_message=long_error,
        )

        render_event(long_message_event, mock_console)

        # Should handle long messages without truncation in escalation
        escalation_call = mock_console.print.call_args_list[0]
        assert f"Agent escalated: {long_error}" in escalation_call[0][1]
