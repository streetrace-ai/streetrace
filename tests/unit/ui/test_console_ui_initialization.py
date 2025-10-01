"""Test ConsoleUI initialization and basic properties.

This module tests the fundamental aspects of the ConsoleUI class including
initialization, dependency injection, and basic setup.
"""

from unittest.mock import Mock

import pytest
from prompt_toolkit.completion import Completer
from rich.console import Console

from streetrace.ui.console_ui import ConsoleUI


class TestConsoleUIInitialization:
    """Test ConsoleUI initialization and basic setup."""

    @pytest.fixture
    def mock_completer(self):
        """Create a mock completer."""
        return Mock(spec=Completer)

    @pytest.fixture
    def console_ui(self, app_state, mock_completer, mock_ui_bus):
        """Create a ConsoleUI instance with mocked dependencies."""
        return ConsoleUI(
            app_state=app_state,
            completer=mock_completer,
            ui_bus=mock_ui_bus,
            skip_tty_check=True,
        )

    def test_initialization_stores_dependencies(
        self,
        app_state,
        mock_completer,
        mock_ui_bus,
    ):
        """Test that ConsoleUI properly stores all injected dependencies."""
        console_ui = ConsoleUI(
            app_state=app_state,
            completer=mock_completer,
            ui_bus=mock_ui_bus,
            skip_tty_check=True,
        )

        assert console_ui.app_state is app_state
        assert console_ui.completer is mock_completer
        assert console_ui.ui_bus is mock_ui_bus
        assert isinstance(console_ui.console, Console)
        assert console_ui.spinner is None  # Should be initialized to None

    def test_prompt_session_configuration(self, console_ui, mock_completer):
        """Test that PromptSession is configured correctly."""
        prompt_session = console_ui.prompt_session

        assert prompt_session.completer is mock_completer
        assert prompt_session.complete_while_typing is True
        assert prompt_session.multiline is True
        assert prompt_session.key_bindings is not None  # Custom key bindings

    def test_ui_bus_event_registration(self, app_state, mock_completer, mock_ui_bus):
        """Test that ConsoleUI registers for UI bus events."""
        console_ui = ConsoleUI(
            app_state=app_state,
            completer=mock_completer,
            ui_bus=mock_ui_bus,
            skip_tty_check=True,
        )

        # Verify that the UI bus methods were called to register callbacks
        mock_ui_bus.on_ui_update_requested.assert_called_once_with(console_ui.display)
        mock_ui_bus.on_prompt_token_count_estimate.assert_called_once_with(
            console_ui._update_rprompt,  # noqa: SLF001
        )

    def test_initialization_creates_new_console(
        self,
        app_state,
        mock_completer,
        mock_ui_bus,
    ):
        """Test that initialization creates a new Console instance."""
        console_ui1 = ConsoleUI(
            app_state,
            mock_completer,
            mock_ui_bus,
            skip_tty_check=True,
        )
        console_ui2 = ConsoleUI(
            app_state,
            mock_completer,
            mock_ui_bus,
            skip_tty_check=True,
        )

        # Each instance should have its own console
        assert console_ui1.console is not console_ui2.console
        assert isinstance(console_ui1.console, Console)
        assert isinstance(console_ui2.console, Console)

    def test_initialization_parameter_types(
        self,
        app_state,
        mock_completer,
        mock_ui_bus,
    ):
        """Test that initialization accepts correct parameter types."""
        # Should accept valid types without error
        console_ui = ConsoleUI(
            app_state=app_state,
            completer=mock_completer,
            ui_bus=mock_ui_bus,
            skip_tty_check=True,
        )
        assert isinstance(console_ui, ConsoleUI)

        # Verify the dependencies are stored with correct references
        assert id(console_ui.app_state) == id(app_state)
        assert id(console_ui.completer) == id(mock_completer)
        assert id(console_ui.ui_bus) == id(mock_ui_bus)
