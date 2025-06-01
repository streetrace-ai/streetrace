"""Test ConsoleUI display methods.

This module tests the various display methods in ConsoleUI including
display(), display_info(), display_warning(), display_error(), and confirm_with_user().
"""

from unittest.mock import Mock, patch

import pytest

from streetrace.ui.colors import Styles
from streetrace.ui.console_ui import ConsoleUI


class TestConsoleUIDisplayMethods:
    """Test ConsoleUI display method functionality."""

    @pytest.fixture
    def console_ui(self, app_state, mock_prompt_completer, mock_ui_bus):
        """Create a ConsoleUI instance."""
        return ConsoleUI(
            app_state=app_state,
            completer=mock_prompt_completer,
            ui_bus=mock_ui_bus,
        )

    @patch("streetrace.ui.console_ui.render_using_registered_renderer")
    def test_display_method(self, mock_render, console_ui):
        """Test the display method delegates to registered renderer."""
        test_obj = Mock()

        console_ui.display(test_obj)

        mock_render.assert_called_once_with(test_obj, console_ui.console)

    def test_display_info(self, console_ui):
        """Test display_info method."""
        test_message = "This is an info message"

        with patch.object(console_ui.console, "print") as mock_print:
            console_ui.display_info(test_message)

            mock_print.assert_called_once_with(test_message, style=Styles.RICH_INFO)

    def test_display_warning(self, console_ui):
        """Test display_warning method."""
        test_message = "This is a warning message"

        with patch.object(console_ui.console, "print") as mock_print:
            console_ui.display_warning(test_message)

            mock_print.assert_called_once_with(test_message, style=Styles.RICH_WARNING)

    def test_display_error(self, console_ui):
        """Test display_error method."""
        test_message = "This is an error message"

        with patch.object(console_ui.console, "print") as mock_print:
            console_ui.display_error(test_message)

            mock_print.assert_called_once_with(test_message, style=Styles.RICH_ERROR)

    def test_confirm_with_user(self, console_ui):
        """Test confirm_with_user method."""
        test_message = "Please confirm"
        test_input = "user input response"

        with patch.object(
            console_ui.console,
            "input",
            return_value=f"  {test_input}  ",
        ) as mock_input:
            result = console_ui.confirm_with_user(test_message)

            mock_input.assert_called_once_with(f"[green]{test_message}[/green]")
            assert result == test_input  # Should be stripped

    def test_confirm_with_user_strips_whitespace(self, console_ui):
        """Test that confirm_with_user strips whitespace from user input."""
        test_message = "Enter something"
        user_input_with_whitespace = "   response with spaces   "
        expected_result = "response with spaces"

        with patch.object(
            console_ui.console,
            "input",
            return_value=user_input_with_whitespace,
        ):
            result = console_ui.confirm_with_user(test_message)

            assert result == expected_result

    def test_display_methods_with_different_message_types(self, console_ui):
        """Test display methods with various message types."""
        # Test with empty string
        with patch.object(console_ui.console, "print") as mock_print:
            console_ui.display_info("")
            mock_print.assert_called_with("", style=Styles.RICH_INFO)

        # Test with multiline string
        multiline_message = "Line 1\nLine 2\nLine 3"
        with patch.object(console_ui.console, "print") as mock_print:
            console_ui.display_warning(multiline_message)
            mock_print.assert_called_with(multiline_message, style=Styles.RICH_WARNING)

        # Test with unicode characters
        unicode_message = "Unicode test: 🚗💨 StreetRace!"
        with patch.object(console_ui.console, "print") as mock_print:
            console_ui.display_error(unicode_message)
            mock_print.assert_called_with(unicode_message, style=Styles.RICH_ERROR)

    def test_display_with_various_object_types(self, console_ui):
        """Test display method with different object types."""
        test_objects = [
            "string object",
            42,
            ["list", "object"],
            {"dict": "object"},
            Mock(name="mock_object"),
        ]

        with patch(
            "streetrace.ui.console_ui.render_using_registered_renderer",
        ) as mock_render:
            for obj in test_objects:
                console_ui.display(obj)
                mock_render.assert_called_with(obj, console_ui.console)

            # Verify all objects were processed
            assert mock_render.call_count == len(test_objects)
