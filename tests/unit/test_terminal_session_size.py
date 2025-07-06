"""Tests for terminal size functionality in TerminalSession.

This module tests the terminal size management features:
- Setting custom terminal dimensions
- Auto-detection of parent terminal size
- Preserving parent terminal size after session ends
- Partial size configuration (width/height only)
- PTY size setting verification
"""

import os
import struct
from pathlib import Path
from unittest.mock import Mock, patch

from streetrace.terminal_session import (
    SessionEvent,
    TerminalSession,
)

# Use higher file descriptor numbers to avoid conflicts with pytest's internal FDs
TEST_MASTER_FD = 200
TEST_SLAVE_FD = 201

# Store the original os.close function before any mocking
with Path("/dev/null").open("rb") as f:
    _original_os_close = f.close


class TestTerminalSizeDetection:
    """Test terminal size detection functionality."""

    def test_get_terminal_size_from_ioctl(self):
        """Test terminal size detection using ioctl."""
        session = TerminalSession()

        # Mock successful ioctl call
        with patch("fcntl.ioctl") as mock_ioctl, patch("sys.stdout") as mock_stdout:
            # Mock the ioctl to return packed size data (rows=25, cols=80)
            packed_size = struct.pack("HHHH", 25, 80, 0, 0)
            mock_ioctl.return_value = packed_size
            mock_stdout.fileno.return_value = 1

            width, height = session._get_terminal_size()  # noqa: SLF001

            assert width == 80
            assert height == 25
            mock_ioctl.assert_called_once()

    def test_get_terminal_size_fallback_to_env(self):
        """Test terminal size fallback to environment variables."""
        session = TerminalSession()

        # Mock ioctl to fail, but environment variables are available
        with (
            patch("fcntl.ioctl", side_effect=OSError),
            patch.dict(os.environ, {"COLUMNS": "100", "LINES": "30"}),
        ):
            width, height = session._get_terminal_size()  # noqa: SLF001

            assert width == 100
            assert height == 30

    def test_get_terminal_size_fallback_to_defaults(self):
        """Test terminal size fallback to default values."""
        session = TerminalSession()

        # Mock ioctl to fail and no environment variables
        with (
            patch("fcntl.ioctl", side_effect=OSError),
            patch.dict(os.environ, {}, clear=True),
        ):
            width, height = session._get_terminal_size()  # noqa: SLF001

            assert width == 80
            assert height == 24

    def test_get_terminal_size_handles_invalid_env_vars(self):
        """Test terminal size handles invalid environment variables."""
        session = TerminalSession()

        # Mock ioctl to fail and invalid environment variables
        with (
            patch("fcntl.ioctl", side_effect=OSError),
            patch.dict(os.environ, {"COLUMNS": "invalid", "LINES": "also_invalid"}),
        ):
            width, height = session._get_terminal_size()  # noqa: SLF001

            assert width == 80
            assert height == 24


class TestTerminalSizeConfiguration:
    """Test terminal size configuration in TerminalSession."""

    def test_terminal_session_with_custom_size(self):
        """Test creating TerminalSession with custom terminal size."""
        session = TerminalSession(
            terminal_width=120,
            terminal_height=40,
        )

        assert session.terminal_width == 120
        assert session.terminal_height == 40

    def test_terminal_session_with_partial_size(self):
        """Test creating TerminalSession with partial size specification."""
        # Only width specified
        session1 = TerminalSession(terminal_width=100)
        assert session1.terminal_width == 100
        assert session1.terminal_height is None

        # Only height specified
        session2 = TerminalSession(terminal_height=35)
        assert session2.terminal_width is None
        assert session2.terminal_height == 35

    def test_terminal_session_with_default_size(self):
        """Test creating TerminalSession with default (auto-detected) size."""
        session = TerminalSession()

        assert session.terminal_width is None
        assert session.terminal_height is None


class TestPTYSizeSetting:
    """Test PTY size setting functionality."""

    def test_set_pty_size_success(self):
        """Test successful PTY size setting."""
        session = TerminalSession()

        with patch("fcntl.ioctl") as mock_ioctl:
            session._set_pty_size(TEST_MASTER_FD, 100, 30)  # noqa: SLF001

            # Verify ioctl was called with correct parameters
            mock_ioctl.assert_called_once()
            call_args = mock_ioctl.call_args[0]

            assert call_args[0] == TEST_MASTER_FD  # file descriptor
            # call_args[2] should be the packed window size
            unpacked = struct.unpack("HHHH", call_args[2])
            assert unpacked[0] == 30  # rows (height)
            assert unpacked[1] == 100  # cols (width)

    def test_set_pty_size_handles_errors(self):
        """Test PTY size setting handles errors gracefully."""
        session = TerminalSession()

        with patch("fcntl.ioctl", side_effect=OSError("Mock ioctl error")):
            # Should not raise exception
            session._set_pty_size(TEST_MASTER_FD, 100, 30)  # noqa: SLF001


class TestTerminalSizeInCommandExecution:
    """Test terminal size behavior during command execution."""

    def get_standard_mocks(self):
        """Get the standard set of mocks for command execution tests."""

        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        return {
            "mock_close": mock_close,
            "patches": [
                patch("streetrace.terminal_session.pty.openpty"),
                patch("streetrace.terminal_session.subprocess.Popen"),
                patch("streetrace.terminal_session.os.close"),
                patch("termios.tcgetattr"),
                patch("termios.tcsetattr"),
                patch("tty.setraw"),
                patch("streetrace.terminal_session.select.select"),
                patch("streetrace.terminal_session.os.read"),
                patch("streetrace.terminal_session.sys.stdout"),
                patch("streetrace.terminal_session.sys.stdin"),
                patch("fcntl.ioctl"),  # Mock ioctl for PTY size setting
            ],
        }

    def test_command_execution_with_custom_terminal_size(self):
        """Test command execution with custom terminal size."""
        session_events = []

        def capture_events(event: SessionEvent) -> None:
            session_events.append(event)

        mocks = self.get_standard_mocks()

        with (
            patch("streetrace.terminal_session.pty.openpty") as mock_openpty,
            patch("streetrace.terminal_session.subprocess.Popen") as mock_popen,
            patch(
                "streetrace.terminal_session.os.close",
                side_effect=mocks["mock_close"],
            ),
            patch("termios.tcgetattr"),
            patch("termios.tcsetattr"),
            patch("tty.setraw"),
            patch("streetrace.terminal_session.select.select") as mock_select,
            patch("streetrace.terminal_session.os.read") as mock_read,
            patch("streetrace.terminal_session.sys.stdout"),
            patch("streetrace.terminal_session.sys.stdin") as mock_stdin,
            patch("fcntl.ioctl") as mock_ioctl,
        ):
            # Setup mocks
            mock_stdin.fileno.return_value = 0
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)

            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            mock_select.return_value = ([], [], [])
            mock_read.return_value = b""

            # Create session with custom size
            session = TerminalSession(
                on_session_complete=capture_events,
                terminal_width=150,
                terminal_height=50,
            )
            session.start()

            # Execute command
            return_code = session.execute_command("echo test")

            # Verify command executed successfully
            assert return_code == 0
            assert len(session_events) == 1

            # Verify PTY size was set correctly
            pty_size_calls = [
                call
                for call in mock_ioctl.call_args_list
                if len(call[0]) >= 3 and isinstance(call[0][2], bytes)
            ]
            assert len(pty_size_calls) >= 1

            # Check the last PTY size setting call
            last_call = pty_size_calls[-1]
            assert last_call[0][0] == TEST_MASTER_FD

            # Unpack the window size structure
            unpacked = struct.unpack("HHHH", last_call[0][2])
            assert unpacked[0] == 50  # rows (height)
            assert unpacked[1] == 150  # cols (width)

    def test_command_execution_with_auto_detected_size(self):
        """Test command execution with auto-detected terminal size."""
        session_events = []

        def capture_events(event: SessionEvent) -> None:
            session_events.append(event)

        mocks = self.get_standard_mocks()

        with (
            patch("streetrace.terminal_session.pty.openpty") as mock_openpty,
            patch("streetrace.terminal_session.subprocess.Popen") as mock_popen,
            patch(
                "streetrace.terminal_session.os.close",
                side_effect=mocks["mock_close"],
            ),
            patch("termios.tcgetattr"),
            patch("termios.tcsetattr"),
            patch("tty.setraw"),
            patch("streetrace.terminal_session.select.select") as mock_select,
            patch("streetrace.terminal_session.os.read") as mock_read,
            patch("streetrace.terminal_session.sys.stdout"),
            patch("streetrace.terminal_session.sys.stdin") as mock_stdin,
            patch("fcntl.ioctl") as mock_ioctl,
        ):
            # Setup mocks
            mock_stdin.fileno.return_value = 0
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)

            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            mock_select.return_value = ([], [], [])
            mock_read.return_value = b""

            # Mock terminal size detection to return known values
            def ioctl_side_effect(fd, _cmd, buf):
                if fd == TEST_MASTER_FD:
                    # This is PTY size setting - return the buffer
                    return buf
                # This is terminal size detection - return packed size (25 r, 90 c)
                return struct.pack("HHHH", 25, 90, 0, 0)

            mock_ioctl.side_effect = ioctl_side_effect

            # Create session without specified size (should auto-detect)
            session = TerminalSession(on_session_complete=capture_events)
            session.start()

            # Execute command
            return_code = session.execute_command("echo test")

            # Verify command executed successfully
            assert return_code == 0
            assert len(session_events) == 1

            # Verify terminal size was detected and PTY was sized correctly
            pty_size_calls = [
                call
                for call in mock_ioctl.call_args_list
                if call[0][0] == TEST_MASTER_FD and len(call[0]) >= 3
            ]
            assert len(pty_size_calls) >= 1

            # Check the PTY size setting call
            pty_call = pty_size_calls[0]
            unpacked = struct.unpack("HHHH", pty_call[0][2])
            assert unpacked[0] == 25  # rows (height)
            assert unpacked[1] == 90  # cols (width)

    def test_command_execution_with_partial_size_config(self):
        """Test command execution with partial size configuration."""
        session_events = []

        def capture_events(event: SessionEvent) -> None:
            session_events.append(event)

        mocks = self.get_standard_mocks()

        with (
            patch("streetrace.terminal_session.pty.openpty") as mock_openpty,
            patch("streetrace.terminal_session.subprocess.Popen") as mock_popen,
            patch(
                "streetrace.terminal_session.os.close",
                side_effect=mocks["mock_close"],
            ),
            patch("termios.tcgetattr"),
            patch("termios.tcsetattr"),
            patch("tty.setraw"),
            patch("streetrace.terminal_session.select.select") as mock_select,
            patch("streetrace.terminal_session.os.read") as mock_read,
            patch("streetrace.terminal_session.sys.stdout"),
            patch("streetrace.terminal_session.sys.stdin") as mock_stdin,
            patch("fcntl.ioctl") as mock_ioctl,
        ):
            # Setup mocks
            mock_stdin.fileno.return_value = 0
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)

            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            mock_select.return_value = ([], [], [])
            mock_read.return_value = b""

            # Mock terminal size detection to return known values
            def ioctl_side_effect(fd, _cmd, buf):
                if fd == TEST_MASTER_FD:
                    # This is PTY size setting - return the buffer
                    return buf
                # This is terminal size detection - return packed size (30 r, 85 c)
                return struct.pack("HHHH", 30, 85, 0, 0)

            mock_ioctl.side_effect = ioctl_side_effect

            # Create session with only width specified (height should be auto-detected)
            session = TerminalSession(
                on_session_complete=capture_events,
                terminal_width=110,  # Only specify width
            )
            session.start()

            # Execute command
            return_code = session.execute_command("echo test")

            # Verify command executed successfully
            assert return_code == 0
            assert len(session_events) == 1

            # Verify PTY was sized with custom width and detected height
            pty_size_calls = [
                call
                for call in mock_ioctl.call_args_list
                if call[0][0] == TEST_MASTER_FD and len(call[0]) >= 3
            ]
            assert len(pty_size_calls) >= 1

            # Check the PTY size setting call
            pty_call = pty_size_calls[0]
            unpacked = struct.unpack("HHHH", pty_call[0][2])
            assert unpacked[0] == 30  # rows (detected height)
            assert unpacked[1] == 110  # cols (specified width)


class TestParentTerminalPreservation:
    """Test that parent terminal size is preserved after session ends."""

    def test_parent_terminal_size_preserved_after_session(self):
        """Test that parent terminal settings are restored after session ends."""
        original_events = []

        def capture_events(event: SessionEvent) -> None:
            original_events.append(event)

        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with (
            patch("streetrace.terminal_session.pty.openpty") as mock_openpty,
            patch("streetrace.terminal_session.subprocess.Popen") as mock_popen,
            patch("streetrace.terminal_session.os.close", side_effect=mock_close),
            patch("termios.tcgetattr") as mock_tcgetattr,
            patch("termios.tcsetattr") as mock_tcsetattr,
            patch("tty.setraw"),
            patch("streetrace.terminal_session.select.select") as mock_select,
            patch("streetrace.terminal_session.os.read") as mock_read,
            patch("streetrace.terminal_session.sys.stdout"),
            patch("streetrace.terminal_session.sys.stdin") as mock_stdin,
            patch("fcntl.ioctl"),
        ):
            # Setup mocks
            mock_stdin.fileno.return_value = 0
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)

            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            mock_select.return_value = ([], [], [])
            mock_read.return_value = b""

            # Mock terminal attributes
            original_attrs = ["mock", "terminal", "attributes"]
            mock_tcgetattr.return_value = original_attrs

            # Create session with custom size (different from "parent")
            session = TerminalSession(
                on_session_complete=capture_events,
                terminal_width=200,  # Much larger than typical
                terminal_height=60,
            )
            session.start()

            # Execute command
            return_code = session.execute_command("echo test")

            # Verify command executed successfully
            assert return_code == 0
            assert len(original_events) == 1

            session.stop()

            # Verify that terminal attributes were saved and restored
            mock_tcgetattr.assert_called()  # Original attributes were saved
            mock_tcsetattr.assert_called()  # Attributes were restored

            # Verify the attributes were restored with the original values
            restore_call = mock_tcsetattr.call_args
            assert restore_call[0][2] == original_attrs  # Same attributes restored

    def test_multiple_sessions_dont_interfere(self):
        """Test that multiple sessions with different sizes don't interfere."""
        events_session1 = []
        events_session2 = []

        def capture_events1(event: SessionEvent) -> None:
            events_session1.append(event)

        def capture_events2(event: SessionEvent) -> None:
            events_session2.append(event)

        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with (
            patch("streetrace.terminal_session.pty.openpty") as mock_openpty,
            patch("streetrace.terminal_session.subprocess.Popen") as mock_popen,
            patch("streetrace.terminal_session.os.close", side_effect=mock_close),
            patch("termios.tcgetattr") as mock_tcgetattr,
            patch("termios.tcsetattr") as mock_tcsetattr,
            patch("tty.setraw"),
            patch("streetrace.terminal_session.select.select") as mock_select,
            patch("streetrace.terminal_session.os.read") as mock_read,
            patch("streetrace.terminal_session.sys.stdout"),
            patch("streetrace.terminal_session.sys.stdin") as mock_stdin,
            patch("fcntl.ioctl") as mock_ioctl,
        ):
            # Setup mocks
            mock_stdin.fileno.return_value = 0
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)

            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            mock_select.return_value = ([], [], [])
            mock_read.return_value = b""

            original_attrs = ["original", "terminal", "state"]
            mock_tcgetattr.return_value = original_attrs

            # First session with one size
            session1 = TerminalSession(
                on_session_complete=capture_events1,
                terminal_width=100,
                terminal_height=25,
            )
            session1.start()
            session1.execute_command("echo session1")
            session1.stop()

            # Second session with different size
            session2 = TerminalSession(
                on_session_complete=capture_events2,
                terminal_width=120,
                terminal_height=40,
            )
            session2.start()
            session2.execute_command("echo session2")
            session2.stop()

            # Verify both sessions completed successfully
            assert len(events_session1) == 1
            assert len(events_session2) == 1

            # Verify terminal state was restored for both sessions
            assert mock_tcgetattr.call_count >= 2  # Called for each session
            assert mock_tcsetattr.call_count >= 2  # Restored for each session

            # Verify different PTY sizes were set
            pty_size_calls = [
                call
                for call in mock_ioctl.call_args_list
                if call[0][0] == TEST_MASTER_FD and len(call[0]) >= 3
            ]
            assert len(pty_size_calls) >= 2

            # Check that different sizes were used
            sizes_used = []
            for call in pty_size_calls:
                unpacked = struct.unpack("HHHH", call[0][2])
                sizes_used.append((unpacked[1], unpacked[0]))  # (width, height)

            # Should have used both (100, 25) and (120, 40)
            assert (100, 25) in sizes_used
            assert (120, 40) in sizes_used
