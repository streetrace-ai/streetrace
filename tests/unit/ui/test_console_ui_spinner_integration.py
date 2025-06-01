"""Test ConsoleUI spinner integration and the original failing scenario.

This module specifically tests the spinner functionality and the scenario
that was causing the AttributeError.
"""

from unittest.mock import Mock, patch

import pytest

from streetrace.ui.console_ui import ConsoleUI, StatusSpinner


class TestConsoleUISpinnerIntegration:
    """Test ConsoleUI spinner integration scenarios."""

    @pytest.fixture
    def console_ui(self, app_state, mock_prompt_completer, mock_ui_bus):
        """Create a ConsoleUI instance."""
        return ConsoleUI(
            app_state=app_state,
            completer=mock_prompt_completer,
            ui_bus=mock_ui_bus,
        )

    def test_spinner_initially_none(self, console_ui):
        """Test that spinner is initially None."""
        assert console_ui.spinner is None

    def test_update_state_with_no_spinner(self, console_ui):
        """Test update_state when no spinner exists (the original failing scenario)."""
        # This was the original failing scenario - should not raise AttributeError
        console_ui.update_state()

        # Should complete without error
        assert console_ui.spinner is None

    def test_status_method_creates_spinner(self, console_ui):
        """Test that status() method creates and returns a StatusSpinner."""
        spinner = console_ui.status()

        assert isinstance(spinner, StatusSpinner)
        assert console_ui.spinner is spinner
        assert spinner.app_state is console_ui.app_state
        assert spinner.console is console_ui.console

    def test_update_state_with_active_spinner(self, console_ui):
        """Test update_state when spinner exists."""
        # Create a spinner
        spinner = console_ui.status()

        # Mock the spinner's update_state method
        spinner.update_state = Mock()

        # Call update_state
        console_ui.update_state()

        # Verify that the spinner's update_state was called
        spinner.update_state.assert_called_once()

    def test_multiple_status_calls_replace_spinner(self, console_ui):
        """Test that calling status() multiple times replaces the spinner."""
        spinner1 = console_ui.status()
        spinner2 = console_ui.status()

        assert spinner1 is not spinner2
        assert console_ui.spinner is spinner2
        assert isinstance(console_ui.spinner, StatusSpinner)

    def test_original_failing_scenario_simulation(self, console_ui):
        """Test the exact scenario that was failing in the error trace."""
        # Simulate the original error scenario:
        # 1. update_state() is called without spinner being set first
        # 2. This should NOT raise AttributeError anymore

        # This was the line that failed: if self.spinner:
        try:
            console_ui.update_state()
            # If we get here, the fix worked
            success = True
        except AttributeError:
            success = False

        assert success, (
            "update_state should not raise AttributeError when spinner is None"
        )

    def test_spinner_lifecycle_full_cycle(self, console_ui):
        """Test complete spinner lifecycle."""
        # Initially no spinner
        assert console_ui.spinner is None
        console_ui.update_state()  # Should not fail

        # Create spinner
        spinner = console_ui.status()
        assert console_ui.spinner is not None

        # Mock the spinner's update_state for testing
        with patch.object(spinner, "update_state") as mock_update:
            console_ui.update_state()
            mock_update.assert_called_once()

        # Clear spinner (simulating context manager exit or manual clear)
        console_ui.spinner = None
        console_ui.update_state()  # Should not fail again

    def test_spinner_integration_with_app_state_changes(self, console_ui, app_state):
        """Test spinner integration with changing app state."""
        spinner = console_ui.status()

        # Change app state
        app_state.current_model = "updated-model"

        # Mock the spinner's update_state method to verify it's called
        with patch.object(spinner, "update_state") as mock_update:
            console_ui.update_state()
            mock_update.assert_called_once()

        # Verify spinner has access to updated app state
        assert spinner.app_state.current_model == "updated-model"

    def test_spinner_state_management_edge_cases(self, console_ui):
        """Test edge cases in spinner state management."""
        # Test repeated update_state calls without spinner
        for _ in range(5):
            console_ui.update_state()  # Should not fail

        # Create spinner and test repeated calls
        spinner = console_ui.status()
        with patch.object(spinner, "update_state") as mock_update:
            for _ in range(3):
                console_ui.update_state()
            assert mock_update.call_count == 3

        # Clear and test again
        console_ui.spinner = None
        console_ui.update_state()  # Should not fail

    def test_fix_addresses_original_error_trace(self, console_ui):
        """Test that our fix specifically addresses the original error from the trace.

        Original error was:
        AttributeError: 'ConsoleUI' object has no attribute 'spinner'
        at line: if self.spinner:
        """
        # The original error occurred when update_state was called
        # and the spinner attribute didn't exist

        # Ensure spinner attribute exists and is properly initialized
        assert hasattr(console_ui, "spinner")
        assert console_ui.spinner is None

        # This should work without AttributeError
        console_ui.update_state()

        # Verify the attribute is still properly managed
        assert console_ui.spinner is None
