"""Unit tests for FlowEvent renderers.

Test the rendering of LlmCallEvent and LlmResponseEvent to the console.
"""

from unittest.mock import Mock

import pytest
from rich.console import Console
from rich.markdown import Markdown

from streetrace.dsl.runtime.events import LlmCallEvent, LlmResponseEvent
from streetrace.ui.colors import Styles
from streetrace.ui.flow_event_renderer import render_llm_call, render_llm_response
from streetrace.ui.render_protocol import (
    RendererFn,
    _display_renderers_registry,
    render_using_registered_renderer,
)


class TestLlmCallEventRenderer:
    """Test the render_llm_call renderer function."""

    @pytest.fixture
    def llm_call_event(self) -> LlmCallEvent:
        """Create a sample LlmCallEvent for testing."""
        return LlmCallEvent(
            prompt_name="analyze",
            model="gpt-4",
            prompt_text="Analyze this input",
        )

    @pytest.fixture
    def mock_console(self) -> Console:
        """Create a mock Rich Console."""
        return Mock(spec=Console)

    def test_render_llm_call_prints_event_info(
        self,
        llm_call_event: LlmCallEvent,
        mock_console: Console,
    ):
        """Test that render_llm_call prints event info."""
        render_llm_call(llm_call_event, mock_console)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        printed_text = call_args[0][0]

        assert "[LLM Call]" in printed_text
        assert "analyze" in printed_text
        assert "gpt-4" in printed_text

    def test_render_llm_call_uses_info_style(
        self,
        llm_call_event: LlmCallEvent,
        mock_console: Console,
    ):
        """Test that render_llm_call uses RICH_INFO style."""
        render_llm_call(llm_call_event, mock_console)

        call_kwargs = mock_console.print.call_args[1]
        assert call_kwargs["style"] == Styles.RICH_INFO

    def test_render_llm_call_is_registered(self):
        """Test that render_llm_call is registered in the renderer registry."""
        assert LlmCallEvent in _display_renderers_registry
        assert _display_renderers_registry[LlmCallEvent] == render_llm_call

    def test_render_llm_call_conforms_to_protocol(self):
        """Test that render_llm_call conforms to RendererFn protocol."""
        assert isinstance(render_llm_call, RendererFn)

    def test_render_llm_call_via_registry(
        self,
        llm_call_event: LlmCallEvent,
        mock_console: Console,
    ):
        """Test rendering LlmCallEvent through the registry."""
        render_using_registered_renderer(llm_call_event, mock_console)

        mock_console.print.assert_called_once()


class TestLlmResponseEventRenderer:
    """Test the render_llm_response renderer function."""

    @pytest.fixture
    def llm_response_event(self) -> LlmResponseEvent:
        """Create a sample LlmResponseEvent for testing."""
        return LlmResponseEvent(
            prompt_name="analyze",
            content="The analysis shows important findings.",
        )

    @pytest.fixture
    def mock_console(self) -> Console:
        """Create a mock Rich Console."""
        return Mock(spec=Console)

    def test_render_llm_response_prints_markdown(
        self,
        llm_response_event: LlmResponseEvent,
        mock_console: Console,
    ):
        """Test that render_llm_response prints content as Markdown."""
        render_llm_response(llm_response_event, mock_console)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        printed_obj = call_args[0][0]

        # Should be a Markdown object
        assert isinstance(printed_obj, Markdown)

    def test_render_llm_response_uses_model_style(
        self,
        llm_response_event: LlmResponseEvent,
        mock_console: Console,
    ):
        """Test that render_llm_response uses RICH_MODEL style."""
        render_llm_response(llm_response_event, mock_console)

        call_kwargs = mock_console.print.call_args[1]
        assert call_kwargs["style"] == Styles.RICH_MODEL

    def test_render_llm_response_is_registered(self):
        """Test that render_llm_response is registered in the renderer registry."""
        assert LlmResponseEvent in _display_renderers_registry
        assert _display_renderers_registry[LlmResponseEvent] == render_llm_response

    def test_render_llm_response_conforms_to_protocol(self):
        """Test that render_llm_response conforms to RendererFn protocol."""
        assert isinstance(render_llm_response, RendererFn)

    def test_render_llm_response_via_registry(
        self,
        llm_response_event: LlmResponseEvent,
        mock_console: Console,
    ):
        """Test rendering LlmResponseEvent through the registry."""
        render_using_registered_renderer(llm_response_event, mock_console)

        mock_console.print.assert_called_once()

    def test_render_llm_response_with_markdown_content(
        self,
        mock_console: Console,
    ):
        """Test rendering response with markdown formatting."""
        event = LlmResponseEvent(
            prompt_name="format",
            content="Here is **bold** and `code`.",
        )

        render_llm_response(event, mock_console)

        call_args = mock_console.print.call_args
        markdown_obj = call_args[0][0]
        assert isinstance(markdown_obj, Markdown)
        # The Markdown object should contain the content
        assert markdown_obj.markup == "Here is **bold** and `code`."

    def test_render_llm_response_with_empty_content(
        self,
        mock_console: Console,
    ):
        """Test rendering response with empty content."""
        event = LlmResponseEvent(
            prompt_name="empty",
            content="",
        )

        render_llm_response(event, mock_console)

        mock_console.print.assert_called_once()


class TestRendererIntegration:
    """Test integration between renderers and the registry."""

    @pytest.fixture
    def mock_console(self) -> Console:
        """Create a mock Rich Console."""
        return Mock(spec=Console)

    def test_both_renderers_are_registered(self):
        """Test that both FlowEvent renderers are in the registry."""
        assert LlmCallEvent in _display_renderers_registry
        assert LlmResponseEvent in _display_renderers_registry

    def test_renderers_handle_different_event_types(
        self,
        mock_console: Console,
    ):
        """Test that different event types are handled by their renderers."""
        call_event = LlmCallEvent(
            prompt_name="test",
            model="gpt-4",
            prompt_text="Test",
        )
        response_event = LlmResponseEvent(
            prompt_name="test",
            content="Response",
        )

        render_using_registered_renderer(call_event, mock_console)
        first_call = mock_console.print.call_args

        mock_console.reset_mock()

        render_using_registered_renderer(response_event, mock_console)
        second_call = mock_console.print.call_args

        # The calls should be different (one is text, one is Markdown)
        assert first_call != second_call

    def test_renderer_registry_does_not_contain_base_flow_event(self):
        """Test that FlowEvent base class is not registered."""
        from streetrace.dsl.runtime.events import FlowEvent

        # Base class should not be registered - only concrete subclasses
        assert FlowEvent not in _display_renderers_registry
