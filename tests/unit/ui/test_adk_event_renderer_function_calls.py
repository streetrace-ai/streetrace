"""Test function call rendering in ADK event renderer.

This module tests the rendering of events that contain function calls,
including the formatting of function names, arguments, and syntax highlighting.
"""

from rich.syntax import Syntax

from streetrace.ui.adk_event_renderer import render_event


class TestFunctionCallRendering:
    """Test rendering of events with function calls."""

    def test_render_function_call_event(
        self,
        function_call_event,
        mock_console,
        sample_author,
    ):
        """Test rendering a basic function call event."""
        render_event(function_call_event, mock_console)

        expected_author = f"[bold]{sample_author}:[/bold]"
        mock_console.print.assert_called_once()

        call_args = mock_console.print.call_args
        assert call_args[0][0] == expected_author
        assert isinstance(call_args[0][1], Syntax)
        assert call_args[1]["end"] == " "

    def test_render_function_call_syntax_highlighting(
        self,
        function_call_event,
        mock_console,
    ):
        """Test that function calls use proper syntax highlighting."""
        render_event(function_call_event, mock_console)

        call_args = mock_console.print.call_args
        syntax_obj = call_args[0][1]

        assert isinstance(syntax_obj, Syntax)
        assert syntax_obj.lexer
        assert syntax_obj.lexer.name == "Python"  # lexer is a pygments lexer object
        assert syntax_obj.line_numbers is False
        assert syntax_obj.background_color == "default"

    def test_render_function_call_code_format(
        self,
        function_call_event,
        mock_console,
        sample_function_call_data,
    ):
        """Test that function call code is formatted correctly."""
        render_event(function_call_event, mock_console)

        call_args = mock_console.print.call_args
        syntax_obj = call_args[0][1]

        expected_code = (
            f"{sample_function_call_data['name']}({sample_function_call_data['args']})"
        )
        assert syntax_obj.code == expected_code

    def test_render_function_call_with_simple_args(self, mock_console, sample_author):
        """Test rendering function call with simple argument types."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part

        function_call = FunctionCall(
            name="simple_function",
            args={"string_arg": "hello", "number_arg": 42, "bool_arg": True},
            id="call_simple",
        )
        part = Part(function_call=function_call)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        call_args = mock_console.print.call_args
        syntax_obj = call_args[0][1]

        expected_args = {"string_arg": "hello", "number_arg": 42, "bool_arg": True}
        expected_code = f"simple_function({expected_args})"
        assert syntax_obj.code == expected_code

    def test_render_function_call_with_complex_args(self, mock_console, sample_author):
        """Test rendering function call with complex nested arguments."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part

        complex_args = {
            "nested_dict": {"key1": "value1", "key2": {"nested": "value"}},
            "list_arg": [1, 2, "three"],
            "null_arg": None,
        }

        function_call = FunctionCall(
            name="complex_function",
            args=complex_args,
            id="call_complex",
        )
        part = Part(function_call=function_call)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        call_args = mock_console.print.call_args
        syntax_obj = call_args[0][1]

        expected_code = f"complex_function({complex_args})"
        assert syntax_obj.code == expected_code

    def test_render_function_call_with_empty_args(self, mock_console, sample_author):
        """Test rendering function call with no arguments."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part

        function_call = FunctionCall(
            name="no_args_function",
            args={},
            id="call_empty",
        )
        part = Part(function_call=function_call)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        call_args = mock_console.print.call_args
        syntax_obj = call_args[0][1]

        expected_code = "no_args_function({})"
        assert syntax_obj.code == expected_code

    def test_render_function_call_with_none_args(self, mock_console, sample_author):
        """Test rendering function call with None arguments."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part

        function_call = FunctionCall(
            name="none_args_function",
            args=None,
            id="call_none",
        )
        part = Part(function_call=function_call)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        call_args = mock_console.print.call_args
        syntax_obj = call_args[0][1]

        expected_code = "none_args_function(None)"
        assert syntax_obj.code == expected_code

    def test_render_multiple_function_calls(self, mock_console, sample_author):
        """Test rendering event with multiple function calls."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part

        function_call_1 = FunctionCall(
            name="function_1",
            args={"arg": "value1"},
            id="call_1",
        )
        function_call_2 = FunctionCall(
            name="function_2",
            args={"arg": "value2"},
            id="call_2",
        )

        parts = [
            Part(function_call=function_call_1),
            Part(function_call=function_call_2),
        ]
        content = Content(parts=parts, role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        # Should have 2 print calls, one for each function call
        assert mock_console.print.call_count == 2

        expected_author = f"[bold]{sample_author}:[/bold]"
        for call_args in mock_console.print.call_args_list:
            assert call_args[0][0] == expected_author
            assert isinstance(call_args[0][1], Syntax)
            assert call_args[1]["end"] == " "

    def test_render_mixed_content_with_function_call(self, mock_console, sample_author):
        """Test rendering event with both text and function call parts."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part
        from rich.markdown import Markdown

        text_part = Part(text="About to call a function:")
        function_call = FunctionCall(
            name="test_function",
            args={"param": "value"},
            id="call_test",
        )
        function_part = Part(function_call=function_call)

        parts = [text_part, function_part]
        content = Content(parts=parts, role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        # Should have 2 print calls: one for text, one for function call
        assert mock_console.print.call_count == 2

        # First call should be for text (Markdown)
        first_call = mock_console.print.call_args_list[0]
        markdown_obj = first_call[0][1]
        assert isinstance(markdown_obj, Markdown)
        assert "About to call a function:" in markdown_obj.markup

        # Second call should be for function call (Syntax)
        second_call = mock_console.print.call_args_list[1]
        assert isinstance(second_call[0][1], Syntax)

    def test_render_function_call_with_special_characters(
        self,
        mock_console,
        sample_author,
    ):
        """Test rendering function call with special characters in name and args."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part

        function_call = FunctionCall(
            name="special_function_with_underscores",
            args={"special_chars": "quotes'and\"backslashes\\", "unicode": "🚗💨"},
            id="call_special",
        )
        part = Part(function_call=function_call)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        call_args = mock_console.print.call_args
        syntax_obj = call_args[0][1]

        # Should contain the function name and handle special characters
        assert "special_function_with_underscores" in syntax_obj.code
        assert "🚗💨" in syntax_obj.code

    def test_render_function_call_preserves_argument_types(
        self,
        mock_console,
        sample_author,
    ):
        """Test that argument types are preserved in the rendered output."""
        from google.adk.events import Event
        from google.genai.types import Content, FunctionCall, Part

        # Test various Python types
        args_with_types = {
            "string": "text",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "none_value": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        function_call = FunctionCall(
            name="typed_function",
            args=args_with_types,
            id="call_typed",
        )
        part = Part(function_call=function_call)
        content = Content(parts=[part], role="assistant")
        event = Event(
            author=sample_author,
            content=content,
            turn_complete=False,
            partial=False,
        )

        render_event(event, mock_console)

        call_args = mock_console.print.call_args
        syntax_obj = call_args[0][1]

        # The args should be represented as the original dictionary
        expected_code = f"typed_function({args_with_types})"
        assert syntax_obj.code == expected_code
