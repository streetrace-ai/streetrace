"""Test ConsoleUI display methods.

This module tests display() and confirm_with_user().
"""

from unittest.mock import Mock, patch

import pytest

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
            skip_tty_check=True,
        )

    @patch("streetrace.ui.console_ui.render_using_registered_renderer")
    def test_display_method(self, mock_render, console_ui):
        """Test the display method delegates to registered renderer."""
        test_obj = Mock()

        console_ui.display(test_obj)

        mock_render.assert_called_once_with(test_obj, console_ui.console)

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
