"""Tests for TerminalEmulator terminal size functionality.

This module tests the terminal size integration in the TerminalEmulator class
from stdstd.py to ensure it properly passes size parameters to TerminalSession.
"""

from pathlib import Path
from unittest.mock import Mock, patch

from streetrace.stdstd import TerminalEmulator


class TestTerminalEmulatorSizeIntegration:
    """Test terminal size integration in TerminalEmulator."""

    def test_terminal_emulator_with_custom_size(self, tmp_path: Path):
        """Test TerminalEmulator passes custom size to TerminalSession."""
        log_path = tmp_path / "test_terminal.log"

        with patch("streetrace.stdstd.TerminalSession") as mock_terminal_session_class:
            mock_session_instance = Mock()
            mock_terminal_session_class.return_value = mock_session_instance

            # Create TerminalEmulator with custom size
            _ = TerminalEmulator(
                log_path,
                enable_automation=False,
                terminal_width=140,
                terminal_height=35,
            )

            # Verify TerminalSession was created with correct size parameters
            mock_terminal_session_class.assert_called_once()
            call_kwargs = mock_terminal_session_class.call_args[1]

            assert "terminal_width" in call_kwargs
            assert "terminal_height" in call_kwargs
            assert call_kwargs["terminal_width"] == 140
            assert call_kwargs["terminal_height"] == 35

    def test_terminal_emulator_with_partial_size(self, tmp_path: Path):
        """Test TerminalEmulator passes partial size configuration."""
        log_path = tmp_path / "test_terminal.log"

        with patch("streetrace.stdstd.TerminalSession") as mock_terminal_session_class:
            mock_session_instance = Mock()
            mock_terminal_session_class.return_value = mock_session_instance

            # Create TerminalEmulator with only width specified
            _ = TerminalEmulator(
                log_path,
                enable_automation=True,
                terminal_width=110,
            )

            # Verify TerminalSession was created with correct parameters
            mock_terminal_session_class.assert_called_once()
            call_kwargs = mock_terminal_session_class.call_args[1]

            assert "terminal_width" in call_kwargs
            assert "terminal_height" in call_kwargs
            assert call_kwargs["terminal_width"] == 110
            assert call_kwargs["terminal_height"] is None

    def test_terminal_emulator_with_default_size(self, tmp_path: Path):
        """Test TerminalEmulator with default size (None values)."""
        log_path = tmp_path / "test_terminal.log"

        with patch("streetrace.stdstd.TerminalSession") as mock_terminal_session_class:
            mock_session_instance = Mock()
            mock_terminal_session_class.return_value = mock_session_instance

            # Create TerminalEmulator without size parameters
            _ = TerminalEmulator(log_path, enable_automation=True)

            # Verify TerminalSession was created with None size parameters
            mock_terminal_session_class.assert_called_once()
            call_kwargs = mock_terminal_session_class.call_args[1]

            assert "terminal_width" in call_kwargs
            assert "terminal_height" in call_kwargs
            assert call_kwargs["terminal_width"] is None
            assert call_kwargs["terminal_height"] is None

    def test_terminal_emulator_callbacks_still_work(self, tmp_path: Path):
        """Test that terminal size doesn't interfere with existing callbacks."""
        log_path = tmp_path / "test_terminal.log"

        with (
            patch("streetrace.stdstd.TerminalSession") as mock_terminal_session_class,
            patch("streetrace.stdstd.SessionLogger") as mock_session_logger_class,
        ):
            mock_session_instance = Mock()
            mock_terminal_session_class.return_value = mock_session_instance

            mock_logger_instance = Mock()
            mock_session_logger_class.return_value = mock_logger_instance

            # Create TerminalEmulator with size
            _ = TerminalEmulator(
                log_path,
                enable_automation=True,
                terminal_width=100,
                terminal_height=30,
            )

            # Verify TerminalSession was created with callbacks and size
            mock_terminal_session_class.assert_called_once()
            call_args = mock_terminal_session_class.call_args

            # Check positional arguments (callbacks)
            assert "on_session_update" in call_args[1]
            assert "on_session_complete" in call_args[1]
            assert call_args[1]["on_session_update"] is not None
            assert call_args[1]["on_session_complete"] is not None

            # Check size parameters
            assert call_args[1]["terminal_width"] == 100
            assert call_args[1]["terminal_height"] == 30

    def test_send_input_to_process_with_custom_size(self, tmp_path: Path):
        """Test send_input_to_process method works with custom terminal size."""
        log_path = tmp_path / "test_terminal.log"

        with (
            patch("streetrace.stdstd.TerminalSession") as mock_terminal_session_class,
            patch("streetrace.stdstd.print_formatted_text"),
        ):  # Mock to prevent actual printing
            mock_session_instance = Mock()
            mock_session_instance.send_input.return_value = True
            mock_terminal_session_class.return_value = mock_session_instance

            # Create TerminalEmulator with custom size
            emulator = TerminalEmulator(
                log_path,
                terminal_width=150,
                terminal_height=45,
            )

            # Test send_input_to_process method
            result = emulator.send_input_to_process("test input")

            # Verify both calls were made: the actual input, then the automated "quit"
            expected_calls = [
                (("test input",), {"add_newline": True}),
                (("quit",), {}),
            ]

            assert mock_session_instance.send_input.call_count == 2
            actual_calls = [
                (call[0], call[1])
                for call in mock_session_instance.send_input.call_args_list
            ]
            assert actual_calls == expected_calls
            assert result is True
