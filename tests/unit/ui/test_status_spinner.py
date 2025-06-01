"""Test StatusSpinner class functionality.

This module tests the StatusSpinner class which encapsulates rich.status
for displaying working status messages.
"""

from types import TracebackType
from unittest.mock import AsyncMock, Mock

import pytest
from rich.console import Console

from streetrace.ui.console_ui import (
    _STATUS_MESSAGE_TEMPLATE,
    StatusSpinner,
    _format_app_state_str,
)


class TestStatusSpinner:
    """Test StatusSpinner functionality."""

    @pytest.fixture
    def mock_console(self):
        """Create a mock console."""
        console = Mock(spec=Console)
        mock_status_context = AsyncMock()
        console.status.return_value = mock_status_context
        return console

    @pytest.fixture
    def app_state_fixture(self, app_state):
        """Use the app_state fixture from conftest."""
        return app_state

    @pytest.fixture
    def status_spinner(self, app_state_fixture, mock_console):
        """Create a StatusSpinner instance."""
        return StatusSpinner(app_state_fixture, mock_console)

    def test_status_spinner_initialization(
        self,
        status_spinner,
        app_state_fixture,
        mock_console,
    ):
        """Test StatusSpinner initializes correctly."""
        assert status_spinner.app_state is app_state_fixture
        assert status_spinner.console is mock_console
        assert status_spinner._status is None  # noqa: SLF001

    def test_status_spinner_constants(self):
        """Test StatusSpinner class constants."""
        assert StatusSpinner._ICON == "hamburger"  # noqa: SLF001
        assert StatusSpinner._EMPTY_MESSAGE == "Working..."  # noqa: SLF001

    def test_update_state_with_no_status(self, status_spinner):
        """Test update_state when no status is active."""
        # Should not raise any errors
        status_spinner.update_state()

    def test_update_state_with_active_status(self, status_spinner, app_state_fixture):
        """Test update_state when status is active."""
        mock_status = Mock()
        status_spinner._status = mock_status  # noqa: SLF001

        status_spinner.update_state()

        # Verify that update was called with formatted template
        expected_message = _format_app_state_str(
            _STATUS_MESSAGE_TEMPLATE,
            app_state_fixture,
        )
        mock_status.update.assert_called_once_with(expected_message)

    def test_context_manager_enter(self, status_spinner, mock_console):
        """Test StatusSpinner as context manager - enter."""
        result = status_spinner.__enter__()

        # Should return self
        assert result is status_spinner

        # Should create and enter a console status
        mock_console.status.assert_called_once_with(
            status=StatusSpinner._EMPTY_MESSAGE,  # noqa: SLF001
            spinner=StatusSpinner._ICON,  # noqa: SLF001
        )

        # Should have stored the status
        assert status_spinner._status is not None  # noqa: SLF001

    def test_context_manager_exit_with_status(self, status_spinner):
        """Test StatusSpinner as context manager - exit with active status."""
        # Setup an active status
        mock_status = AsyncMock()
        status_spinner._status = mock_status  # noqa: SLF001

        # Test exception parameters
        exc_type = ValueError
        exc_value = ValueError("test error")
        traceback = Mock(spec=TracebackType)

        # Call exit
        status_spinner.__exit__(exc_type, exc_value, traceback)

        # Should call exit on the status
        mock_status.__exit__.assert_called_once_with(exc_type, exc_value, traceback)

        # Should clear the status
        assert status_spinner._status is None  # noqa: SLF001

    def test_context_manager_exit_with_no_status(self, status_spinner):
        """Test StatusSpinner as context manager - exit with no active status."""
        # Ensure no status is set
        status_spinner._status = None  # noqa: SLF001

        # Should not raise any errors
        status_spinner.__exit__(None, None, None)

    def test_context_manager_full_cycle(self, status_spinner, mock_console):
        """Test complete context manager cycle."""
        mock_status = AsyncMock()
        mock_console.status.return_value.__enter__.return_value = mock_status

        # Enter context
        result = status_spinner.__enter__()
        assert result is status_spinner
        assert status_spinner._status is mock_status  # noqa: SLF001

        # Exit context
        status_spinner.__exit__(None, None, None)
        assert status_spinner._status is None  # noqa: SLF001

        # Verify the complete flow
        mock_console.status.assert_called_once()
        mock_status.__exit__.assert_called_once_with(None, None, None)


class TestFormatAppStateStr:
    """Test the _format_app_state_str helper function."""

    def test_format_app_state_str(self, app_state):
        """Test formatting app state into string template."""
        template = (
            "Model: {current_model}, Cost: ${usage_and_cost.app_run_usage.cost_str}"
        )

        result = _format_app_state_str(template, app_state)

        # Should contain the model name and format correctly
        assert app_state.current_model in result
        assert "Cost: $" in result

    def test_format_app_state_str_with_complex_template(self, app_state):
        """Test formatting with more complex template matching the actual toolbar."""
        result = _format_app_state_str(_STATUS_MESSAGE_TEMPLATE, app_state)

        # Should contain expected elements
        assert app_state.current_model in result
        assert "Working..." in result
        # Should contain usage information formatted as strings
        assert "$" in result  # Cost information
