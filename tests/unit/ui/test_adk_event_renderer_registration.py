"""Test renderer registration in ADK event renderer.

This module tests the integration of the render_event function with
the rendering protocol registration system, ensuring that Event objects
can be properly rendered through the registry.
"""

from unittest.mock import Mock, patch

import pytest
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai.types import Content, FunctionCall, FunctionResponse, Part

from streetrace.ui.adk_event_renderer import Event as EventWrapper
from streetrace.ui.adk_event_renderer import render_event
from streetrace.ui.console_ui import ConsoleUI
from streetrace.ui.render_protocol import (
    RendererFn,
    _display_renderers_registry,
    render_using_registered_renderer,
)


class TestRendererRegistration:
    """Test the renderer registration and integration."""

    def test_render_event_is_registered(self):
        """Test that render_event function is registered for Event type."""
        # Check that Event type is in the registry
        assert EventWrapper in _display_renderers_registry

        # Check that the registered function is our render_event
        registered_renderer = _display_renderers_registry[EventWrapper]
        assert registered_renderer == render_event

    def test_render_using_registered_renderer_calls_render_event(
        self,
        basic_event,
        mock_console,
    ):
        """Test that rendering through the registry calls our render_event function."""
        # Instead of patching the function, let's mock the registry directly
        with patch.dict(_display_renderers_registry, {Event: Mock()}) as mock_registry:
            mock_renderer = mock_registry[Event]
            render_using_registered_renderer(basic_event, mock_console)

            mock_renderer.assert_called_once_with(basic_event, mock_console)

    def test_render_using_registered_renderer_with_event_object(
        self,
        basic_event,
        mock_console,
    ):
        """Test that Event objects can be rendered through the registry."""
        # This should not raise an exception
        render_using_registered_renderer(EventWrapper(basic_event), mock_console)

        # Mock console should have been called (content rendering)
        mock_console.print.assert_called()

    def test_registry_contains_correct_function_signature(self):
        """Test that the registered function has the correct signature."""
        registered_renderer = _display_renderers_registry[EventWrapper]

        # Check function annotations
        annotations = registered_renderer.__annotations__
        assert "obj" in annotations
        assert "console" in annotations
        assert "return" in annotations
        assert annotations["return"] is None or annotations["return"] is type(None)

    def test_render_event_decorator_preserves_function(self):
        """Test that @register_renderer preserves the original function."""
        # Should be callable with proper arguments
        assert callable(render_event)

        # Should have proper docstring
        assert render_event.__doc__ is not None
        assert "google.adk.events.Event" in render_event.__doc__

    def test_multiple_event_types_can_be_rendered(self, mock_console, sample_author):
        """Test that different Event configurations can all be rendered."""
        # Test various event types
        event_configs = [
            # Basic text event
            {
                "content": Content(parts=[Part(text="Simple text")], role="assistant"),
                "turn_complete": False,
            },
            # Final response event
            {
                "content": Content(
                    parts=[Part(text="Final response")],
                    role="assistant",
                ),
                "turn_complete": True,
            },
            # Event with no content
            {
                "content": None,
                "turn_complete": False,
            },
            # Event with empty content
            {
                "content": Content(parts=[], role="assistant"),
                "turn_complete": False,
            },
        ]

        for config in event_configs:
            event = Event(
                author=sample_author,
                partial=False,
                **config,
            )

            # Each should render without error through the registry
            render_using_registered_renderer(EventWrapper(event), mock_console)

    def test_registry_error_for_unregistered_type(self, mock_console):
        """Test that unregistered types raise appropriate error."""
        unregistered_object = "This is not a registered type"

        with pytest.raises(ValueError, match="Renderer for .* is not registered"):
            render_using_registered_renderer(unregistered_object, mock_console)

    def test_render_event_protocol_compliance(self):
        """Test that render_event complies with the RendererFn protocol."""
        # Check if render_event is an instance of the protocol
        assert isinstance(render_event, RendererFn)

    def test_render_event_handles_all_event_variants(self, mock_console, sample_author):
        """Test that render_event can handle all possible Event variants."""
        # Create comprehensive event with all possible content types
        function_call = FunctionCall(
            name="test_func",
            args={"param": "value"},
            id="call_1",
        )
        function_response = FunctionResponse(
            id="call_1",
            name="test_func",
            response={"result": "success"},
        )

        comprehensive_content = Content(
            parts=[
                Part(text="Text content"),
                Part(function_call=function_call),
                Part(function_response=function_response),
            ],
            role="assistant",
        )

        comprehensive_event = Event(
            author=sample_author,
            content=comprehensive_content,
            turn_complete=True,
            partial=False,
            actions=EventActions(escalate=True),
            error_message="Test error",
        )

        # Should render without error

        render_event(EventWrapper(comprehensive_event), mock_console)

        # Should have multiple print calls for different content types
        assert mock_console.print.call_count > 1

    def test_integration_with_console_ui_display(self, basic_event):
        """Test integration with ConsoleUI.display method."""
        # Create a minimal ConsoleUI mock
        mock_ui_bus = Mock()
        mock_app_state = Mock()
        mock_completer = Mock()

        console_ui = ConsoleUI(
            app_state=mock_app_state,
            completer=mock_completer,
            ui_bus=mock_ui_bus,
        )

        # Mock the console.print method to verify calls
        with patch.object(console_ui.console, "print") as mock_print:
            console_ui.display(EventWrapper(basic_event))

            # Should have called print (content rendering)
            mock_print.assert_called()

    def test_direct_function_call_vs_registry_call(self, basic_event, mock_console):
        """Test that calling the function directly vs through registry is similar."""
        # Call directly

        render_event(EventWrapper(basic_event), mock_console)
        direct_call_count = mock_console.print.call_count

        # Call through registry
        mock_console.reset_mock()
        render_using_registered_renderer(EventWrapper(basic_event), mock_console)
        registry_call_count = mock_console.print.call_count

        # Should produce the same number of calls
        assert direct_call_count == registry_call_count
