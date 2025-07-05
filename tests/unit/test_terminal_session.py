"""Tests for terminal session management and automation features.

This module tests all use cases described in the terminal_session.py docstring:
- Simple command execution with monitoring
- Interactive command with programmatic input  
- Automation scenarios (auto-exit help mode)
- Advanced event handling
- Session status tracking and error handling
"""

import os
import select
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from streetrace.terminal_session import (
    SessionData,
    SessionEvent,
    SessionStatus,
    TerminalSession,
)

# Use higher file descriptor numbers to avoid conflicts with pytest's internal FDs
TEST_MASTER_FD = 100
TEST_SLAVE_FD = 101

# Store the original os.close function before any mocking
_original_os_close = os.close


class TestTerminalSessionBasicUsage:
    """Test basic command execution with monitoring callbacks."""

    def test_simple_command_execution_with_callbacks(self):
        """Test basic command execution with update and completion callbacks."""
        update_events = []
        complete_events = []
        
        def on_update(event: SessionEvent) -> None:
            update_events.append(event)
        
        def on_complete(event: SessionEvent) -> None:
            complete_events.append(event)
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                # Let pytest's internal file descriptors be closed normally
                return _original_os_close(fd)
            # For our test FDs, do nothing
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select') as mock_select, \
             patch('streetrace.terminal_session.os.read') as mock_read, \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            mock_select.side_effect = [
                ([TEST_MASTER_FD], [], []),  # Output available
                ([], [], []),  # No more output
            ]
            mock_read.return_value = b"Hello, World!\n"
            
            session = TerminalSession(
                on_session_update=on_update,
                on_session_complete=on_complete
            )
            session.start()
            
            return_code = session.execute_command("echo 'Hello, World!'")
            
            assert return_code == 0
            assert len(complete_events) == 1
            
            # Verify completion event
            completion = complete_events[0]
            assert completion.command == "echo 'Hello, World!'"
            assert completion.status == SessionStatus.COMPLETED
            assert completion.return_code == 0
            assert completion.execution_time is not None
            assert len(completion.session_data) >= 2  # At least command + output
            
            # Verify session data contains both input and output
            sources = [data.source for data in completion.session_data]
            assert "user" in sources
            assert "command" in sources

    def test_session_status_tracking(self):
        """Test session status transitions through different states."""
        status_changes = []
        
        def track_status(event: SessionEvent) -> None:
            status_changes.append(event.status)
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select') as mock_select, \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            mock_select.return_value = ([], [], [])
            
            session = TerminalSession(on_session_complete=track_status)
            
            # Test status transitions
            assert session.status == SessionStatus.IDLE
            
            session.start()
            assert session.status == SessionStatus.IDLE
            
            session.execute_command("ls")
            
            # Should end in completed status
            assert SessionStatus.COMPLETED in status_changes


class TestTerminalSessionInteractiveCommands:
    """Test interactive command execution with programmatic input."""

    def test_interactive_command_with_programmatic_input(self):
        """Test sending input to running interactive processes."""
        session_events = []
        
        def capture_events(event: SessionEvent) -> None:
            session_events.append(event)
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select') as mock_select, \
             patch('streetrace.terminal_session.os.read') as mock_read, \
             patch('streetrace.terminal_session.os.write') as mock_write, \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            
            mock_process = Mock()
            # Set up the process to be "running" for the duration of the test
            mock_process.poll.return_value = None  # Always running for this test
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            # Simulate Python interpreter output
            mock_select.side_effect = [
                ([TEST_MASTER_FD], [], []),  # Python prompt available
                ([], [], []),  # No more data for first check
                ([], [], []),  # Process completion
            ]
            mock_read.side_effect = [
                b"Python 3.12.9\n>>> ",
                b"",  # End of output
            ]
            
            session = TerminalSession(on_session_complete=capture_events)
            session.start()
            
            # Mock the session state to simulate an active process
            session._master_fd = TEST_MASTER_FD
            session._process = mock_process
            session.current_command = "python"
            session.status = SessionStatus.RUNNING
            
            # Send programmatic input  
            success = session.send_input("print('Hello from automation!')")
            assert success is True
            
            # Verify the input was written to the process
            mock_write.assert_called()
            
            # Manually add the automated input to session data (since the mock doesn't do this automatically)
            automated_entries = [d for d in session.session_data if d.source == "automated"]
            assert len(automated_entries) >= 1
            assert "print('Hello from automation!')" in automated_entries[0].content

    def test_send_input_to_non_running_process(self):
        """Test sending input when no process is running."""
        session = TerminalSession()
        session.start()
        
        # Try to send input with no running process
        success = session.send_input("test input")
        assert success is False

    def test_is_process_running_check(self):
        """Test the is_process_running method."""
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select'), \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            mock_process = Mock()
            mock_process.poll.side_effect = [None, None, 0]  # Running, then stopped
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            session = TerminalSession()
            session.start()
            
            # No process running initially
            assert session.is_process_running() is False
            
            # Start a command in a thread
            def run_command():
                session.execute_command("long_running_command")
            
            thread = threading.Thread(target=run_command)
            thread.start()
            thread.join(timeout=1)
            
            # Process should have finished
            assert session.is_process_running() is False


class TestTerminalSessionAutomation:
    """Test automation scenarios like auto-exit help mode."""

    def test_automation_with_help_mode_detection(self):
        """Test the complete automation example from the docstring."""
        
        class SmartTerminalSession:
            def __init__(self):
                self.automated_actions = []
                self.session = TerminalSession(
                    on_session_update=self._on_session_update,
                    on_session_complete=self._on_session_complete
                )
                
            def _on_session_update(self, event: SessionEvent) -> None:
                if event.status != SessionStatus.RUNNING:
                    return
                    
                # Get latest command output
                latest_output = ""
                for data in reversed(event.session_data):
                    if data.source == "command":
                        latest_output = data.content
                        break
                        
                # Auto-exit Python help mode
                if "help>" in latest_output.lower():
                    self.automated_actions.append("help_mode_detected")
                    self.session.send_input("quit")
                    self.automated_actions.append("sent_quit")
                    
                # Auto-continue on prompts
                elif any(prompt in latest_output.lower() for prompt in [
                    "continue? (y/n)",
                    "[y/n]"
                ]):
                    self.automated_actions.append("prompt_detected")
                    self.session.send_input("y")
                    self.automated_actions.append("sent_yes")
            
            def _on_session_complete(self, event: SessionEvent) -> None:
                self.automated_actions.append("session_completed")
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select') as mock_select, \
             patch('streetrace.terminal_session.os.read') as mock_read, \
             patch('streetrace.terminal_session.os.write'), \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            mock_process = Mock()
            mock_process.poll.side_effect = [None, None, 0]
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            # Simulate help mode output
            mock_select.side_effect = [
                ([TEST_MASTER_FD], [], []),  # Help output available
                ([], [], []),  # No more data
                ([], [], []),  # Process completion
            ]
            mock_read.side_effect = [
                b"Welcome to Python help utility!\nhelp> ",
                b"",
            ]
            
            smart_session = SmartTerminalSession()
            smart_session.session.start()
            
            # This should trigger the automation
            smart_session.session.execute_command("python")
            
            # Manually add the command output to trigger automation
            smart_session.session._add_session_data("Welcome to Python help utility!\nhelp> ", "command")
            
            # Manually trigger the update callback to test automation
            event = smart_session.session._create_session_event(SessionStatus.RUNNING)
            smart_session._on_session_update(event)
            
            # Verify automation was triggered
            assert "help_mode_detected" in smart_session.automated_actions
            assert "sent_quit" in smart_session.automated_actions
            assert "session_completed" in smart_session.automated_actions

    def test_prompt_continuation_automation(self):
        """Test automation for continuation prompts."""
        automation_triggers = []
        
        def automation_callback(event: SessionEvent) -> None:
            if event.status != SessionStatus.RUNNING:
                return
                
            latest_output = ""
            for data in reversed(event.session_data):
                if data.source == "command":
                    latest_output = data.content
                    break
            
            if "continue? (y/n)" in latest_output.lower():
                automation_triggers.append("continuation_prompt")
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select') as mock_select, \
             patch('streetrace.terminal_session.os.read') as mock_read, \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            mock_process = Mock()
            mock_process.poll.side_effect = [None, 0]
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            mock_select.side_effect = [([TEST_MASTER_FD], [], []), ([], [], [])]
            mock_read.return_value = b"Do you want to continue? (y/n): "
            
            session = TerminalSession(on_session_update=automation_callback)
            session.start()
            session.execute_command("some_interactive_command")
            
            # Manually add the continuation prompt to trigger automation
            session._add_session_data("Do you want to continue? (y/n): ", "command")
            
            # Manually trigger the update callback to test automation
            event = session._create_session_event(SessionStatus.RUNNING)
            automation_callback(event)
            
            assert "continuation_prompt" in automation_triggers


class TestTerminalSessionAdvancedFeatures:
    """Test advanced event handling and session data access."""

    def test_comprehensive_event_data_access(self):
        """Test accessing all available session event data."""
        captured_events = []
        
        def detailed_event_handler(event: SessionEvent) -> None:
            captured_events.append({
                'command': event.command,
                'status': event.status,
                'return_code': event.return_code,
                'execution_time': event.execution_time,
                'error_message': event.error_message,
                'session_data_count': len(event.session_data),
                'data_sources': [d.source for d in event.session_data],
            })
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select') as mock_select, \
             patch('streetrace.terminal_session.os.read') as mock_read, \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 42  # Non-zero exit code
            mock_popen.return_value = mock_process
            
            mock_select.side_effect = [([TEST_MASTER_FD], [], []), ([], [], [])]
            mock_read.return_value = b"Error: Command failed\n"
            
            session = TerminalSession(
                on_session_update=detailed_event_handler,
                on_session_complete=detailed_event_handler
            )
            session.start()
            
            return_code = session.execute_command("failing_command")
            
            assert return_code == 42
            assert len(captured_events) >= 1
            
            final_event = captured_events[-1]
            assert final_event['command'] == "failing_command"
            assert final_event['status'] == SessionStatus.ERROR
            assert final_event['return_code'] == 42
            assert final_event['execution_time'] is not None
            assert final_event['session_data_count'] >= 1
            assert "user" in final_event['data_sources']  # Command entry
            assert "command" in final_event['data_sources']  # Output

    def test_session_data_structure(self):
        """Test the structure and content of session data."""
        session_events = []
        
        def capture_session_data(event: SessionEvent) -> None:
            session_events.append(event)
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select') as mock_select, \
             patch('streetrace.terminal_session.os.read') as mock_read, \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            mock_select.side_effect = [([TEST_MASTER_FD], [], []), ([], [], [])]
            mock_read.return_value = b"test output\n"
            
            session = TerminalSession(on_session_complete=capture_session_data)
            session.start()
            session.execute_command("test_command")
            
            assert len(session_events) == 1
            event = session_events[0]
            
            # Verify session data structure
            assert len(event.session_data) >= 2  # At least command + output
            
            # Check command entry
            command_entry = event.session_data[0]
            assert isinstance(command_entry, SessionData)
            assert command_entry.source == "user"
            assert command_entry.content == "test_command"
            assert isinstance(command_entry.timestamp, datetime)
            
            # Check output entry
            output_entries = [d for d in event.session_data if d.source == "command"]
            assert len(output_entries) >= 1
            assert "test output" in output_entries[0].content

    def test_snapshot_functionality(self):
        """Test periodic snapshot functionality."""
        snapshot_events = []
        completion_events = []
        
        def capture_snapshots(event: SessionEvent) -> None:
            snapshot_events.append(event)
        
        def capture_completion(event: SessionEvent) -> None:
            completion_events.append(event)
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select') as mock_select, \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin, \
             patch('streetrace.terminal_session.threading.Timer') as mock_timer:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            mock_process = Mock()
            mock_process.poll.return_value = 0
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            mock_select.side_effect = [([], [], [])]
            
            # Mock the timer - don't trigger automatically to avoid recursion
            mock_timer_instance = Mock()
            mock_timer.return_value = mock_timer_instance
            
            # Manually trigger snapshot after command starts
            def manual_trigger():
                session._take_snapshot()
            
            mock_timer_instance.start.side_effect = lambda: None  # Don't auto-trigger
            
            session = TerminalSession(
                on_session_update=capture_snapshots,
                on_session_complete=capture_completion
            )
            session.start()
            
            # Set up command state before taking snapshot
            session.current_command = "test_command"
            session.status = SessionStatus.RUNNING
            
            # Manually trigger snapshot while command is "running"
            session._take_snapshot()
            
            # Now execute the command (which will complete immediately due to mocking)
            session.execute_command("test_command")
            
            # Verify timer was created and started during execute_command
            mock_timer.assert_called_with(20.0, session._take_snapshot)
            mock_timer_instance.start.assert_called()
            mock_timer_instance.cancel.assert_called()  # Should be cancelled on completion
            
            # Should have captured snapshot and completion
            assert len(snapshot_events) >= 1
            assert len(completion_events) == 1
            
            # Verify snapshot event
            snapshot_event = snapshot_events[0]
            assert snapshot_event.status == SessionStatus.RUNNING
            assert snapshot_event.command == "test_command"


class TestTerminalSessionErrorHandling:
    """Test error handling and edge cases."""

    def test_command_execution_error(self):
        """Test handling of command execution errors."""
        error_events = []
        
        def capture_errors(event: SessionEvent) -> None:
            error_events.append(event)
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close):
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            mock_popen.side_effect = OSError("Failed to start process")
            
            session = TerminalSession(on_session_complete=capture_errors)
            session.start()
            
            return_code = session.execute_command("invalid_command")
            
            assert return_code == 1
            assert len(error_events) == 1
            
            error_event = error_events[0]
            assert error_event.status == SessionStatus.ERROR
            assert error_event.return_code == 1
            assert error_event.error_message is not None
            assert "Failed to start process" in error_event.error_message

    def test_signal_handling(self):
        """Test graceful shutdown on signals."""
        import signal
        
        session = TerminalSession()
        session.start()
        
        # Simulate signal handling
        original_running = session.is_running
        session._signal_handler(signal.SIGINT, None)
        
        assert session.is_running is False

    def test_cleanup_on_session_stop(self):
        """Test proper cleanup when session is stopped."""
        session = TerminalSession()
        session.start()
        
        assert session.is_running is True
        assert session.status == SessionStatus.IDLE
        
        session.stop()
        
        assert session.is_running is False
        assert session.status == SessionStatus.IDLE

    def test_buffer_flushing_edge_cases(self):
        """Test edge cases in buffer flushing."""
        session = TerminalSession()
        session.start()
        
        # Test flushing empty buffer
        session._flush_command_output_buffer()  # Should not crash
        
        # Test flushing with whitespace-only content
        session._command_output_buffer = "   \n\t  "
        session._flush_command_output_buffer()
        
        # Should not add empty session data
        assert len(session.session_data) == 0


class TestTerminalSessionIntegration:
    """Integration tests combining multiple features."""

    def test_full_interactive_session_workflow(self):
        """Test a complete interactive session workflow."""
        session_history = []
        
        def track_session(event: SessionEvent) -> None:
            session_history.append({
                'type': 'update' if event.status == SessionStatus.RUNNING else 'complete',
                'command': event.command,
                'status': event.status,
                'data_count': len(event.session_data),
            })
        
        # Create a more targeted mock for os.close that only affects our test FDs
        def mock_close(fd):
            if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
                return _original_os_close(fd)
            return None

        with patch('streetrace.terminal_session.pty.openpty') as mock_openpty, \
             patch('streetrace.terminal_session.subprocess.Popen') as mock_popen, \
             patch('streetrace.terminal_session.os.close', side_effect=mock_close), \
             patch('termios.tcgetattr'), \
             patch('termios.tcsetattr'), \
             patch('tty.setraw'), \
             patch('streetrace.terminal_session.select.select') as mock_select, \
             patch('streetrace.terminal_session.os.read') as mock_read, \
             patch('streetrace.terminal_session.os.write'), \
             patch('streetrace.terminal_session.sys.stdout'), \
             patch('streetrace.terminal_session.sys.stdin') as mock_stdin:
            
            # Mock stdin to have a fileno method
            mock_stdin.fileno.return_value = 0
            
            mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)
            
            # Create separate mock processes for each command
            mock_process1 = Mock()
            mock_process1.poll.side_effect = [None, None, 0]
            mock_process1.wait.return_value = 0
            
            mock_process2 = Mock()
            mock_process2.poll.side_effect = [None, None, 0]
            mock_process2.wait.return_value = 0
            
            # Return different processes for different commands
            mock_popen.side_effect = [mock_process1, mock_process2]
            
            # Setup select and read for both command executions
            mock_select.side_effect = [
                ([TEST_MASTER_FD], [], []),  # Output available for first command
                ([], [], []),  # No more output for first command
                ([], [], []),  # Process completion for first command
                ([TEST_MASTER_FD], [], []),  # Output available for second command
                ([], [], []),  # No more output for second command
                ([], [], []),  # Process completion for second command
            ]
            mock_read.side_effect = [
                b"Python output\n",
                b"",
                b"Directory listing\n",
                b"",
            ]
            
            session = TerminalSession(
                on_session_update=track_session,
                on_session_complete=track_session
            )
            session.start()
            
            # Execute multiple commands
            return_code1 = session.execute_command("python")
            assert return_code1 == 0
            
            return_code2 = session.execute_command("ls -la")
            assert return_code2 == 0
            
            session.stop()
            
            # Verify session tracking
            assert len(session_history) >= 2  # At least completion events
            
            # All commands should be tracked
            commands = [h['command'] for h in session_history]
            assert "python" in commands
            assert "ls -la" in commands 