"""Test text content rendering in ADK event renderer.

This module tests the rendering of events that contain text content,
including regular messages, markdown content, and different response types
(intermediate vs final responses).
"""

from google.adk.events import Event
from google.genai.types import Content, FunctionCall, Part

from streetrace.ui.adk_event_renderer import Event as EventWrapper
from streetrace.ui.adk_event_renderer import render_event


class TestTextContentRendering:
    """Test rendering of events with text content."""

    def test_render_basic_text_event(self, mock_console, sample_author):
        """Test rendering a basic event with simple text content."""
        # Create event that is NOT a final response
        # (has function calls makes it non-final)
        text_part = Part(text="Sample text content")
        function_call_part = Part(
            function_call=FunctionCall(name="test", args={}, id="1"),
        )
        content = Content(parts=[text_part, function_call_part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Text content (author + markdown) and function call should be rendered
        assert mock_console.print.call_count == 3

    def test_render_final_response_text_event(
        self,
        final_response_event,
        mock_console,
    ):
        """Test rendering a final response event uses different styling."""
        render_event(EventWrapper(final_response_event), mock_console)

        # Text content should be rendered: author line + markdown content
        assert mock_console.print.call_count == 2

    def test_render_markdown_content(self, mock_console, sample_author, markdown_part):
        """Test rendering of markdown content with formatting."""
        content = Content(parts=[markdown_part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

    def test_render_event_with_multiple_text_parts(self, mock_console, sample_author):
        """Test rendering event with multiple text parts."""
        parts = [
            Part(text="First text part"),
            Part(text="Second text part"),
            Part(text="Third text part"),
        ]
        content = Content(parts=parts, role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Should have 6 print calls: author + content for each of 3 text parts
        assert mock_console.print.call_count == 6

    def test_render_event_with_empty_text_part(self, mock_console, sample_author):
        """Test rendering event where text part has empty content."""
        parts = [
            Part(text=""),  # Empty text
            Part(text="Valid text"),
        ]
        content = Content(parts=parts, role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Should print author + content for the non-empty text part only
        assert mock_console.print.call_count == 2

    def test_render_event_with_none_text_part(self, mock_console, sample_author):
        """Test rendering event where text part has None content."""
        parts = [
            Part(text=None),  # None text
            Part(text="Valid text"),
        ]
        content = Content(parts=parts, role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Should print author + content for the non-None text part only
        assert mock_console.print.call_count == 2

    def test_render_event_no_content(self, empty_event, mock_console):
        """Test rendering event with no content."""
        render_event(EventWrapper(empty_event), mock_console)

        # Should not print anything for content
        mock_console.print.assert_not_called()

    def test_render_event_empty_content_parts(self, event_empty_content, mock_console):
        """Test rendering event with content but no parts."""
        render_event(EventWrapper(event_empty_content), mock_console)

        # Should not print anything for content
        mock_console.print.assert_not_called()

    def test_render_preserves_markdown_formatting(self, mock_console, sample_author):
        """Test that markdown formatting is preserved in rendering."""
        markdown_text = (
            "# Header\n\n"
            "**Bold text** and *italic text*\n\n"
            "```python\ncode_block()\n```"
        )
        part = Part(text=markdown_text)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

    def test_render_author_formatting(self, basic_event, mock_console):
        """Test that author name is formatted with bold markup."""
        # Test with special characters in author name
        basic_event.author = "Agent-1_Test"

        render_event(EventWrapper(basic_event), mock_console)

    def test_render_displays_author_before_text(self, mock_console, sample_author):
        """Test that author is displayed before text content."""
        text_part = Part(text="Sample message")
        content = Content(parts=[text_part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # First call should be the author line
        first_call = mock_console.print.call_args_list[0]
        assert sample_author in first_call[0][0]
        assert "[bold]" in first_call[0][0]

    def test_render_text_with_whitespace_handling(self, mock_console, sample_author):
        """Test rendering of text with various whitespace patterns."""
        text_with_whitespace = "  Text with leading spaces\n\nText with empty lines\n  "
        part = Part(text=text_with_whitespace)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Should render author + markdown content
        assert mock_console.print.call_count == 2

    def test_render_non_final_response_style(self, mock_console, sample_author):
        """Test that non-final responses use RICH_INFO style."""
        # Create event with function call to make it non-final
        text_part = Part(text="Some text")
        function_part = Part(function_call=FunctionCall(name="test", args={}, id="1"))
        content = Content(parts=[text_part, function_part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Should have calls for text (author + content) and function call
        assert mock_console.print.call_count == 3

    def test_render_final_response_style(self, mock_console, sample_author):
        """Test that final responses use RICH_MODEL style."""
        # Create event with only text (no function calls/responses) to make it final
        text_part = Part(text="Final response text")
        content = Content(parts=[text_part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Should render author + markdown content
        assert mock_console.print.call_count == 2
