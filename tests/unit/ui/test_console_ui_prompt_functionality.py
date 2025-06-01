"""Test ConsoleUI prompt functionality.

This module tests the prompt-related functionality including prompt_async,
rprompt updates, and prompt session configuration.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from prompt_toolkit import HTML
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document

from streetrace.ui.console_ui import _PROMPT, ConsoleUI


class TestConsoleUIPromptFunctionality:
    """Test ConsoleUI prompt-related functionality."""

    @pytest.fixture
    def console_ui(self, app_state, mock_prompt_completer, mock_ui_bus):
        """Create a ConsoleUI instance."""
        return ConsoleUI(
            app_state=app_state,
            completer=mock_prompt_completer,
            ui_bus=mock_ui_bus,
        )

    def test_update_rprompt_with_token_count(self, console_ui):
        """Test _update_rprompt method with token count."""
        token_count = 150

        console_ui._update_rprompt(token_count)  # noqa: SLF001

        assert console_ui.prompt_session.rprompt == f"~{token_count}t"

    def test_update_rprompt_with_none(self, console_ui):
        """Test _update_rprompt method with None (clears rprompt)."""
        # First set a value
        console_ui.prompt_session.rprompt = "~100t"

        # Then clear it
        console_ui._update_rprompt(None)  # noqa: SLF001

        assert console_ui.prompt_session.rprompt is None

    def test_update_rprompt_with_zero(self, console_ui):
        """Test _update_rprompt method with zero tokens."""
        console_ui._update_rprompt(0)  # noqa: SLF001

        assert console_ui.prompt_session.rprompt == "~0t"

    @pytest.mark.asyncio
    async def test_prompt_async_default_prompt(self, console_ui):
        """Test prompt_async with default prompt string."""
        test_input = "user test input"

        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.return_value = test_input

            result = await console_ui.prompt_async()

            assert result == test_input
            mock_prompt.assert_called_once()

            # Verify the build_prompt function creates correct prompt
            call_args = mock_prompt.call_args[0]
            build_prompt = call_args[0]
            prompt_parts = build_prompt()

            assert prompt_parts == [("class:prompt", _PROMPT), ("", " ")]

    @pytest.mark.asyncio
    async def test_prompt_async_custom_prompt(self, console_ui):
        """Test prompt_async with custom prompt string."""
        custom_prompt = "Custom Prompt:"
        test_input = "user response"

        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.return_value = test_input

            result = await console_ui.prompt_async(custom_prompt)

            assert result == test_input

            # Verify the custom prompt was used
            call_args = mock_prompt.call_args[0]
            build_prompt = call_args[0]
            prompt_parts = build_prompt()

            assert prompt_parts == [("class:prompt", custom_prompt), ("", " ")]

    @pytest.mark.asyncio
    async def test_prompt_async_eof_error_handling(self, console_ui):
        """Test prompt_async handles EOFError (Ctrl+D)."""
        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.side_effect = EOFError()

            result = await console_ui.prompt_async()

            assert result == "/exit"

    @pytest.mark.asyncio
    async def test_prompt_async_keyboard_interrupt_with_empty_buffer(self, console_ui):
        """Test prompt_async handles KeyboardInterrupt with empty buffer."""
        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.side_effect = KeyboardInterrupt()

            # Mock empty buffer
            mock_app = Mock(spec=Application)
            mock_buffer = Mock(spec=Buffer)
            mock_buffer.text = ""
            mock_app.current_buffer = mock_buffer
            console_ui.prompt_session.app = mock_app

            with pytest.raises(SystemExit):
                await console_ui.prompt_async()

    @pytest.mark.asyncio
    async def test_prompt_async_keyboard_interrupt_with_text_in_buffer(
        self,
        console_ui,
    ):
        """Test prompt_async handles KeyboardInterrupt with text in buffer."""
        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.side_effect = KeyboardInterrupt()

            # Mock buffer with text
            mock_app = Mock(spec=Application)
            mock_buffer = Mock(spec=Buffer)
            mock_buffer.text = "some user input"
            mock_app.current_buffer = mock_buffer
            console_ui.prompt_session.app = mock_app

            with pytest.raises(KeyboardInterrupt):
                await console_ui.prompt_async()

            # Verify buffer was reset
            mock_buffer.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_async_ui_bus_integration(self, console_ui, mock_ui_bus):
        """Test that prompt_async integrates with UI bus for typing events."""
        test_input = "test input"

        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.return_value = test_input

            result = await console_ui.prompt_async()

            assert result == test_input

            # Verify validator was set up to dispatch typing events
            call_kwargs = mock_prompt.call_args[1]
            validator = call_kwargs["validator"]

            # Test the validator function with proper Document object
            test_text = "typing test"
            test_document = Document(text=test_text)

            # The validator's validate method doesn't return a value,
            # it raises ValidationError if invalid. Since our function
            # always returns True, this should not raise an exception.
            validator.validate(test_document)

            # Verify UI bus was called for typing
            mock_ui_bus.dispatch_typing_prompt.assert_called_with(test_text)

    @pytest.mark.asyncio
    async def test_prompt_async_clears_rprompt_on_completion(self, console_ui):
        """Test that prompt_async clears rprompt when done."""
        test_input = "test"

        # Set initial rprompt
        console_ui.prompt_session.rprompt = "~100t"

        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.return_value = test_input

            await console_ui.prompt_async()

            # Should clear rprompt after completion
            assert console_ui.prompt_session.rprompt is None

    @pytest.mark.asyncio
    async def test_prompt_async_clears_rprompt_on_exception(self, console_ui):
        """Test that prompt_async clears rprompt even when exception occurs."""
        # Set initial rprompt
        console_ui.prompt_session.rprompt = "~100t"

        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.side_effect = EOFError()

            await console_ui.prompt_async()

            # Should clear rprompt even after exception
            assert console_ui.prompt_session.rprompt is None

    def test_prompt_continuation_function(self, console_ui):
        """Test the prompt continuation function for multiline input."""
        test_input = "test"

        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.return_value = test_input

            # Get the prompt continuation function from the call
            mock_prompt.return_value = test_input

            # We need to actually call the method to test the continuation function
            async def test_continuation():
                await console_ui.prompt_async()

                # Get the continuation function from the call
                call_kwargs = mock_prompt.call_args[1]
                prompt_continuation = call_kwargs["prompt_continuation"]

                # Test the continuation function
                width = 5
                result = prompt_continuation(width, 0, 0)
                expected = [("class:prompt-continuation", "." * width)]

                assert result == expected

            # Run the async test
            import asyncio

            asyncio.run(test_continuation())

    def test_bottom_toolbar_function(self, console_ui, app_state):
        """Test the bottom toolbar function."""
        test_input = "test"

        with patch.object(
            console_ui.prompt_session,
            "prompt_async",
            new_callable=AsyncMock,
        ) as mock_prompt:
            mock_prompt.return_value = test_input

            async def test_toolbar():
                await console_ui.prompt_async()

                # Get the toolbar function from the call
                call_kwargs = mock_prompt.call_args[1]
                bottom_toolbar = call_kwargs["bottom_toolbar"]

                # Test the toolbar function
                result = bottom_toolbar()

                assert isinstance(result, HTML)
                # Should contain app state information
                assert app_state.current_model in str(result)

            # Run the async test
            import asyncio

            asyncio.run(test_toolbar())
