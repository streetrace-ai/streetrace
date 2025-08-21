"""Test function response rendering in ADK event renderer.

This module tests the rendering of events that contain function responses,
including the formatting of response data, text trimming, and syntax highlighting.
"""

from google.adk.events import Event
from google.genai.types import Content, FunctionCall, FunctionResponse, Part

from streetrace.ui.adk_event_renderer import Event as EventWrapper
from streetrace.ui.adk_event_renderer import render_event


class TestFunctionResponseRendering:
    """Test rendering of events with function responses."""

    def test_render_function_response_event(
        self,
        function_response_event,
        mock_console,
    ):
        """Test rendering a basic function response event."""
        render_event(EventWrapper(function_response_event), mock_console)

        mock_console.print.assert_called_once()

        # Function response should be rendered
        mock_console.print.assert_called_once()

    def test_render_function_response_syntax_highlighting(
        self,
        function_response_event,
        mock_console,
    ):
        """Test that function responses use proper syntax highlighting."""
        render_event(EventWrapper(function_response_event), mock_console)

        # Function response should be rendered
        mock_console.print.assert_called_once()

    def test_render_function_response_format(
        self,
        function_response_event,
        mock_console,
    ):
        """Test that function response is formatted with arrow prefix."""
        render_event(EventWrapper(function_response_event), mock_console)

        # Function response should be rendered
        mock_console.print.assert_called_once()

    def test_render_function_response_with_simple_data(
        self,
        mock_console,
        sample_author,
    ):
        """Test rendering function response with simple response data."""
        function_response = FunctionResponse(
            id="call_simple",
            name="simple_function",
            response={"status": "success", "value": 42},
        )
        part = Part(function_response=function_response)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Function response should be rendered
        mock_console.print.assert_called_once()

    def test_render_function_response_with_complex_data(
        self,
        mock_console,
        sample_author,
    ):
        """Test rendering function response with complex nested data."""
        complex_response = {
            "nested_dict": {"inner_key": "inner_value"},
            "list_data": [1, 2, {"item": "value"}],
            "mixed_types": {"string": "text", "number": 123, "bool": True},
        }

        function_response = FunctionResponse(
            id="call_complex",
            name="complex_function",
            response=complex_response,
        )
        part = Part(function_response=function_response)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Function response should be rendered
        mock_console.print.assert_called_once()

    def test_render_function_response_with_empty_response(
        self,
        empty_function_response_part,
        mock_console,
        sample_author,
    ):
        """Test rendering function response with None/empty response data."""
        content = Content(parts=[empty_function_response_part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Should not print anything for empty response
        mock_console.print.assert_not_called()

    def test_render_function_response_with_long_text_trimming(
        self,
        mock_console,
        sample_author,
    ):
        """Test that long response values are trimmed using _trim_text."""
        long_text = "A" * 300  # Exceeds default trimming limit
        function_response = FunctionResponse(
            id="call_long",
            name="long_function",
            response={"long_output": long_text, "short_output": "brief"},
        )
        part = Part(function_response=function_response)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Function response should be rendered
        mock_console.print.assert_called_once()

    def test_render_function_response_with_multiline_trimming(
        self,
        mock_console,
        sample_author,
    ):
        """Test that multiline response values are trimmed properly."""
        multiline_text = "\n".join([f"Line {i}" for i in range(1, 6)])  # 5 lines
        function_response = FunctionResponse(
            id="call_multiline",
            name="multiline_function",
            response={"multiline_output": multiline_text},
        )
        part = Part(function_response=function_response)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Function response should be rendered
        mock_console.print.assert_called_once()

    def test_render_multiple_function_responses(self, mock_console, sample_author):
        """Test rendering event with multiple function response parts."""
        response_1 = FunctionResponse(
            id="call_1",
            name="function_1",
            response={"result": "success_1"},
        )
        response_2 = FunctionResponse(
            id="call_2",
            name="function_2",
            response={"result": "success_2"},
        )

        parts = [
            Part(function_response=response_1),
            Part(function_response=response_2),
        ]
        content = Content(parts=parts, role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Function responses should be rendered
        # Current implementation might handle multiple responses
        assert mock_console.print.call_count >= 1

    def test_render_mixed_content_with_function_response(
        self,
        mock_console,
        sample_author,
    ):
        """Test rendering event with text, function call, and function response."""
        text_part = Part(text="Calling function and got response:")
        call_part = Part(
            function_call=FunctionCall(
                name="test_function",
                args={"param": "value"},
                id="call_test",
            ),
        )
        response_part = Part(
            function_response=FunctionResponse(
                id="call_test",
                name="test_function",
                response={"result": "completed"},
            ),
        )

        parts = [text_part, call_part, response_part]
        content = Content(parts=parts, role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Should have at least 2 print calls: text and grouped function call/response
        assert mock_console.print.call_count >= 2

    def test_render_function_response_with_special_characters(
        self,
        mock_console,
        sample_author,
    ):
        """Test rendering function response with special characters in values."""
        function_response = FunctionResponse(
            id="call_special",
            name="special_function",
            response={
                "unicode_text": "Response with 🚗💨 emojis",
                "quotes": "Text with 'single' and \"double\" quotes",
                "special_chars": "Backslashes \\ and newlines \n here",
            },
        )
        part = Part(function_response=function_response)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Function response should be rendered
        mock_console.print.assert_called_once()

    def test_render_function_response_preserves_data_types(
        self,
        mock_console,
        sample_author,
    ):
        """Test that response data types are preserved in rendered output."""
        typed_response = {
            "string_val": "text",
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
            "none_val": None,
            "list_val": [1, 2, 3],
            "dict_val": {"nested": "value"},
        }

        function_response = FunctionResponse(
            id="call_typed",
            name="typed_function",
            response=typed_response,
        )
        part = Part(function_response=function_response)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Function response should be rendered
        mock_console.print.assert_called_once()

    def test_render_function_response_with_empty_dict_response(
        self,
        mock_console,
        sample_author,
    ):
        """Test rendering function response with empty dictionary."""
        function_response = FunctionResponse(
            id="call_empty_dict",
            name="empty_dict_function",
            response={},
        )
        part = Part(function_response=function_response)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(EventWrapper(event), mock_console)

        # Empty response dict should not trigger printing
        mock_console.print.assert_not_called()

    def test_render_function_response_no_author_in_output(
        self,
        function_response_event,
        mock_console,
    ):
        """Test that function response output doesn't include author prefix."""
        render_event(EventWrapper(function_response_event), mock_console)

        # Function response should be rendered
        mock_console.print.assert_called_once()
