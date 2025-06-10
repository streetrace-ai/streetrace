"""Test text content rendering in ADK event renderer.

This module tests the rendering of events that contain text content,
including regular messages, markdown content, and different response types
(intermediate vs final responses).
"""

from rich.markdown import Markdown

from streetrace.ui.adk_event_renderer import render_event
from streetrace.ui.colors import Styles


class TestTextContentRendering:
    """Test rendering of events with text content."""

    def test_render_basic_text_event(self, mock_console, sample_author):
        """Test rendering a basic event with simple text content."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part

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

        render_event(event, mock_console)

        # Verify author and markdown content are printed with correct style
        expected_author = f"[bold]{sample_author}:[/bold]\n"
        # Should have 2 calls: one for text, one for function call
        assert mock_console.print.call_count == 2

        # First call should be text with RICH_INFO style (not final response)
        text_call = mock_console.print.call_args_list[0]
        assert text_call[0][0] == expected_author
        assert isinstance(text_call[0][1], Markdown)
        assert text_call[1]["style"] == Styles.RICH_INFO
        assert text_call[1]["end"] == " "

    def test_render_final_response_text_event(
        self,
        final_response_event,
        mock_console,
        sample_author,
    ):
        """Test rendering a final response event uses different styling."""
        render_event(final_response_event, mock_console)

        expected_author = f"[bold]{sample_author}:[/bold]\n"
        mock_console.print.assert_called_once()

        call_args = mock_console.print.call_args
        assert call_args[0][0] == expected_author
        assert isinstance(call_args[0][1], Markdown)
        assert (
            call_args[1]["style"] == Styles.RICH_MODEL
        )  # Different style for final response
        assert call_args[1]["end"] == " "

    def test_render_markdown_content(self, mock_console, sample_author, markdown_part):
        """Test rendering of markdown content with formatting."""
        from google.adk.events import Event
        from google.genai.types import Content

        content = Content(parts=[markdown_part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        call_args = mock_console.print.call_args
        markdown_obj = call_args[0][1]
        assert isinstance(markdown_obj, Markdown)
        assert markdown_obj.inline_code_theme == Styles.RICH_MD_CODE

    def test_render_event_with_multiple_text_parts(self, mock_console, sample_author):
        """Test rendering event with multiple text parts."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

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

        render_event(event, mock_console)

        # Should have 3 print calls, one for each text part
        assert mock_console.print.call_count == 3

        expected_author = f"[bold]{sample_author}:[/bold]\n"
        for call_args in mock_console.print.call_args_list:
            assert call_args[0][0] == expected_author
            assert isinstance(call_args[0][1], Markdown)
            assert (
                call_args[1]["style"] == Styles.RICH_MODEL
            )  # Final response (no function calls/responses)
            assert call_args[1]["end"] == " "

    def test_render_event_with_empty_text_part(self, mock_console, sample_author):
        """Test rendering event where text part has empty content."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

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

        render_event(event, mock_console)

        # Should only print the non-empty text part
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        markdown_obj = call_args[0][1]
        assert "Valid text" in markdown_obj.markup

    def test_render_event_with_none_text_part(self, mock_console, sample_author):
        """Test rendering event where text part has None content."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

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

        render_event(event, mock_console)

        # Should only print the non-None text part
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        markdown_obj = call_args[0][1]
        assert "Valid text" in markdown_obj.markup

    def test_render_event_no_content(self, empty_event, mock_console):
        """Test rendering event with no content."""
        render_event(empty_event, mock_console)

        # Should not print anything for content
        mock_console.print.assert_not_called()

    def test_render_event_empty_content_parts(self, event_empty_content, mock_console):
        """Test rendering event with content but no parts."""
        render_event(event_empty_content, mock_console)

        # Should not print anything for content
        mock_console.print.assert_not_called()

    def test_render_preserves_markdown_formatting(self, mock_console, sample_author):
        """Test that markdown formatting is preserved in rendering."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

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

        render_event(event, mock_console)

        call_args = mock_console.print.call_args
        markdown_obj = call_args[0][1]
        assert isinstance(markdown_obj, Markdown)
        # The actual markdown content is stored in the markup attribute
        assert markdown_text == markdown_obj.markup

    def test_render_author_formatting(self, basic_event, mock_console):
        """Test that author name is formatted with bold markup."""
        # Test with special characters in author name
        basic_event.author = "Agent-1_Test"

        render_event(basic_event, mock_console)

        call_args = mock_console.print.call_args
        expected_author = "[bold]Agent-1_Test:[/bold]\n"
        assert call_args[0][0] == expected_author

    def test_render_text_with_whitespace_handling(self, mock_console, sample_author):
        """Test rendering of text with various whitespace patterns."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        text_with_whitespace = "  Text with leading spaces\n\nText with empty lines\n  "
        part = Part(text=text_with_whitespace)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        # Should still render the text as-is through Markdown
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        markdown_obj = call_args[0][1]
        assert isinstance(markdown_obj, Markdown)
        assert text_with_whitespace == markdown_obj.markup

    def test_render_non_final_response_style(self, mock_console, sample_author):
        """Test that non-final responses use RICH_INFO style."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part

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

        render_event(event, mock_console)

        # Should have calls for both text and function call
        assert mock_console.print.call_count == 2

        # Text call should use RICH_INFO style (non-final response)
        text_call = mock_console.print.call_args_list[0]
        assert text_call[1]["style"] == Styles.RICH_INFO

    def test_render_final_response_style(self, mock_console, sample_author):
        """Test that final responses use RICH_MODEL style."""
        from google.adk.events import Event
        from google.genai.types import Content, Part

        # Create event with only text (no function calls/responses) to make it final
        text_part = Part(text="Final response text")
        content = Content(parts=[text_part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert call_args[1]["style"] == Styles.RICH_MODEL
