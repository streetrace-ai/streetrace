"""Terminal session management with interactive command execution and automation.

This module provides a comprehensive TerminalSession class that manages command
execution in a pseudo-terminal environment with real-time monitoring, callback-based
events, and programmatic input capabilities for building intelligent terminal
automation.

## Features

- **Interactive Command Execution**: Full PTY support for running interactive commands
  like `python`, `vim`, `top`, etc. with proper terminal control sequences
- **Real-time Session Monitoring**: Captures all user input and command output with
  timestamps and source tracking
- **Callback-based Events**: Configurable callbacks for session updates (snapshots)
  and completion events
- **Programmatic Input**: Send input to running processes programmatically for
  automation
- **Session Status Tracking**: Monitor session state (idle, running, completed, error)
- **Thread-safe Operation**: Proper locking and cleanup for concurrent access
- **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM

## Basic Usage

### Simple Command Execution with Monitoring

```python
from streetrace.terminal_session import TerminalSession, SessionEvent

def on_update(event: SessionEvent) -> None:
    print(f"Session update: {len(event.session_data)} data entries")

def on_complete(event: SessionEvent) -> None:
    print(f"Command '{event.command}' completed with code {event.return_code}")

# Create session with callbacks
session = TerminalSession(
    on_session_update=on_update,
    on_session_complete=on_complete
)

# Start session and execute commands
session.start()
session.execute_command("ls -la")
session.execute_command("python --version")
session.stop()
```

### Interactive Command with Programmatic Input

```python
import time
import threading
from streetrace.terminal_session import TerminalSession, SessionEvent, SessionStatus

def monitor_and_automate(session: TerminalSession) -> None:
    # Monitor session and provide automated input when needed
    while session.is_process_running():
        time.sleep(1)  # Check every second
        # In real usage, you'd analyze the latest session data here

session = TerminalSession()
session.start()

# Start monitoring in background
monitor_thread = threading.Thread(target=monitor_and_automate, args=(session,))
monitor_thread.daemon = True
monitor_thread.start()

# Execute interactive Python session
session.execute_command("python")

# Send programmatic input
if session.is_process_running():
    session.send_input("print('Hello from automation!')")
    session.send_input("exit()")
```

### Automation Example: Auto-exit Python Help Mode

```python
import time
from streetrace.terminal_session import TerminalSession, SessionEvent, SessionStatus

class SmartTerminalSession:
    def __init__(self):
        self.session = TerminalSession(
            on_session_update=self._on_session_update,
            on_session_complete=self._on_session_complete
        )

    def _on_session_update(self, event: SessionEvent) -> None:
        # Monitor session updates and apply automation heuristics
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
            print("[AUTOMATED] Detected Python help prompt - auto-exiting...")
            self.session.send_input("quit")

        # Auto-continue on prompts
        elif any(prompt in latest_output.lower() for prompt in [
            "press enter to continue",
            "continue? (y/n)",
            "[y/n]"
        ]):
            print("[AUTOMATED] Auto-continuing...")
            self.session.send_input("y")

    def _on_session_complete(self, event: SessionEvent) -> None:
        print(f"Session completed: {event.command}")

    def run_interactive_session(self):
        self.session.start()

        # User starts Python and enters help mode
        self.session.execute_command("python")

        # Simulation: after some time, user types help()
        # The automation will detect "help>" prompt and auto-exit
        time.sleep(2)
        if self.session.is_process_running():
            self.session.send_input("help()")  # This will trigger auto-exit

        time.sleep(3)  # Give time for automation to work

        if self.session.is_process_running():
            self.session.send_input("exit()")  # Exit Python

        self.session.stop()

# Usage
smart_session = SmartTerminalSession()
smart_session.run_interactive_session()
```

### Advanced Event Handling

```python
from streetrace.terminal_session import (
    TerminalSession, SessionEvent, SessionData
)

def detailed_event_handler(event: SessionEvent) -> None:
    # Comprehensive event handler showing all available data
    print(f"Command: {event.command}")
    print(f"Status: {event.status.value}")

    if event.return_code is not None:
        print(f"Return Code: {event.return_code}")

    if event.execution_time is not None:
        print(f"Execution Time: {event.execution_time:.2f}s")

    if event.error_message:
        print(f"Error: {event.error_message}")

    print(f"Session Data ({len(event.session_data)} entries):")
    for i, data in enumerate(event.session_data[-5:]):  # Show last 5 entries
        timestamp = data.timestamp.strftime("%H:%M:%S")
        print(f"  [{timestamp}] {data.source}: {data.content[:50]}...")

session = TerminalSession(
    on_session_update=detailed_event_handler,
    on_session_complete=detailed_event_handler
)
```

## Session Data Structure

Each session event contains:
- `command`: The executed command
- `status`: Current session status (SessionStatus enum)
- `return_code`: Exit code when completed (None while running)
- `session_data`: List of SessionData objects with timestamp, source, and content
- `error_message`: Error details if status is ERROR
- `execution_time`: Duration in seconds when completed

Session data sources:
- `"user"`: Input typed by the user
- `"command"`: Output from the executed command
- `"automated"`: Input sent programmatically via send_input()
"""

import contextlib
import fcntl
import os
import pty
import select
import signal
import struct
import subprocess  # nosec B404 user entered command
import sys
import termios
import threading
import tty
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import FrameType
from typing import Any

from streetrace.log import get_logger


class SessionStatus(Enum):
    """Status of a terminal session."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class SessionData:
    """Data entry for a terminal session."""

    timestamp: datetime
    source: str  # "user" or "command"
    content: str


@dataclass
class SessionEvent:
    """Event containing session state and data."""

    command: str
    status: SessionStatus
    return_code: int | None = None
    session_data: list[SessionData] = field(default_factory=list)
    error_message: str | None = None
    execution_time: float | None = None


class TerminalSession:
    """Manages a terminal session with command execution and event callbacks."""

    def __init__(
        self,
        on_session_update: Callable[[SessionEvent], None] | None = None,
        on_session_complete: Callable[[SessionEvent], None] | None = None,
        work_dir: Path | None = None,
        *,
        terminal_width: int | None = None,
        terminal_height: int | None = None,
    ) -> None:
        """Initialize the terminal session.

        Args:
            on_session_update: Callback for session updates (snapshots)
            on_session_complete: Callback for session completion
            work_dir: Working directory for the session
            terminal_width: Terminal width in columns (defaults to parent value)
            terminal_height: Terminal height in rows (defaults to parent value)

        """
        self.logger = get_logger(__name__)
        self.on_session_update = on_session_update
        self.on_session_complete = on_session_complete
        self.work_dir = work_dir or Path.cwd()

        # Terminal size configuration
        self.terminal_width = terminal_width
        self.terminal_height = terminal_height

        self.session_data: list[SessionData] = []
        self.current_command: str | None = None
        self.command_start_time: datetime | None = None
        self.snapshot_timer: threading.Timer | None = None
        self.is_running: bool = False
        self.status: SessionStatus = SessionStatus.IDLE
        self._lock = threading.Lock()

        # Terminal interaction state
        self._master_fd: int | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._command_output_buffer: str = ""
        self._last_error_message: str | None = None

        # Save original signal handlers so we can restore them later
        self._original_sigint_handler: (
            Callable[[int, FrameType | None], Any] | int | None
        ) = None
        self._original_sigterm_handler: (
            Callable[[int, FrameType | None], Any] | int | None
        ) = None

    def __del__(self) -> None:
        """Ensure signal handlers are restored when object is destroyed."""
        try:
            # Restore signal handlers as a safety net
            if self._original_sigint_handler is not None:
                signal.signal(signal.SIGINT, self._original_sigint_handler)
            if self._original_sigterm_handler is not None:
                signal.signal(signal.SIGTERM, self._original_sigterm_handler)
        except:  # noqa: E722, S110  # nosec B110 Ignore any errors during cleanup
            pass

    def _signal_handler(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.info(
            "Received signal %d, shutting down gracefully",
            signum,
            extra={"signum": signum, "frame": frame},
        )

        # If we're actively running a command, just stop the session
        if self.current_command is not None and self.is_running:
            self.is_running = False
            if self.snapshot_timer:
                self.snapshot_timer.cancel()
        # If no command is running, delegate to the original handler
        # This ensures KeyboardInterrupt is properly raised
        elif signum == signal.SIGINT and self._original_sigint_handler is not None:
            if callable(self._original_sigint_handler):
                self._original_sigint_handler(signum, frame)
            elif self._original_sigint_handler == signal.SIG_DFL:
                # Restore default and re-raise signal
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                os.kill(os.getpid(), signal.SIGINT)
        elif signum == signal.SIGTERM and self._original_sigterm_handler is not None:
            if callable(self._original_sigterm_handler):
                self._original_sigterm_handler(signum, frame)
            elif self._original_sigterm_handler == signal.SIG_DFL:
                # Restore default and re-raise signal
                signal.signal(signal.SIGTERM, signal.SIG_DFL)
                os.kill(os.getpid(), signal.SIGTERM)

    def _get_terminal_size(self) -> tuple[int, int]:
        """Get the current terminal size.

        Returns:
            Tuple of (width, height) in characters

        """
        # Try to get size from current terminal
        try:
            # TIOCGWINSZ (get window size)
            buf = b"\x00" * 8  # 8 bytes for winsize structure
            buf = fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
            rows, cols = struct.unpack("hh", buf[:4])
        except (OSError, AttributeError, TypeError):
            # Fallback to environment variables
            try:
                cols = int(os.environ.get("COLUMNS", "80"))
                rows = int(os.environ.get("LINES", "24"))
            except (ValueError, TypeError):
                # Final fallback to common defaults
                return 80, 24
            else:
                return cols, rows
        else:
            return cols, rows

    def _set_pty_size(self, master_fd: int, width: int, height: int) -> None:
        """Set the size of the pseudo-terminal.

        Args:
            master_fd: Master file descriptor of the PTY
            width: Terminal width in columns
            height: Terminal height in rows

        """
        try:
            # Pack window size structure: rows, cols, x_pixels, y_pixels
            winsize = struct.pack("HHHH", height, width, 0, 0)
            # TIOCSWINSZ (set window size)
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
            self.logger.info(
                "Set PTY size to %dx%d",
                width,
                height,
                extra={"width": width, "height": height},
            )
        except (OSError, struct.error):
            self.logger.exception(
                "Failed to set PTY size",
                extra={"width": width, "height": height},
            )

    def _add_session_data(self, content: str, source: str) -> None:
        """Add session data with timestamp and source.

        Args:
            content: The content to log
            source: Source of the content (user/command)

        """
        with self._lock:
            self._add_session_data_unsafe(content, source)

    def _add_session_data_unsafe(self, content: str, source: str) -> None:
        """Add session data without acquiring lock - use when lock is already held.

        Args:
            content: The content to log
            source: Source of the content (user/command)

        """
        self.session_data.append(
            SessionData(
                timestamp=datetime.now(UTC),
                source=source,
                content=content,
            ),
        )

    def send_input(self, input_text: str, *, add_newline: bool = True) -> bool:
        """Send input to the running interactive process.

        Args:
            input_text: Text to send to the process
            add_newline: Whether to add a newline at the end
        Returns:
            True if input was sent successfully, False otherwise

        """
        if not self.is_running or not self._master_fd or not self._process:
            self.logger.warning("Cannot send input: no active session")
            return False

        # Check if process is still running
        if self._process.poll() is not None:
            self.logger.warning("Cannot send input: process has terminated")
            return False

        try:
            # Prepare input with optional newline
            if add_newline and not input_text.endswith("\n"):
                input_text += "\n"

            # Send input to the process
            with self._lock:
                os.write(self._master_fd, input_text.encode("utf-8"))
                # Log this automated input
                clean_input = input_text.replace("\n", "").replace("\r", "")
                if clean_input:
                    self._add_session_data_unsafe(clean_input, "automated")

            self.logger.info(
                "Sent automated input to process: %s",
                repr(input_text.strip()),
                extra={"input": input_text.strip(), "command": self.current_command},
            )
        except OSError:
            self.logger.exception(
                "Failed to send input to process",
                extra={"input": input_text},
            )
            return False
        else:
            return True

    def is_process_running(self) -> bool:
        """Check if there's a currently running process.

        Returns:
            True if a process is running, False otherwise

        """
        return (
            self.is_running
            and self._process is not None
            and self._process.poll() is None
        )

    def _create_session_event(
        self,
        status: SessionStatus,
        return_code: int | None = None,
        error_message: str | None = None,
    ) -> SessionEvent:
        """Create a session event with current state.

        Args:
            status: Current session status
            return_code: Return code if command completed
            error_message: Error message if there was an error
        Returns:
            SessionEvent with current state

        """
        execution_time = None
        if self.command_start_time:
            execution_time = (
                datetime.now(UTC) - self.command_start_time
            ).total_seconds()

        with self._lock:
            return SessionEvent(
                command=self.current_command or "",
                status=status,
                return_code=return_code,
                session_data=self.session_data.copy(),
                error_message=error_message,
                execution_time=execution_time,
            )

    def _flush_command_output_buffer(self) -> None:
        """Flush any buffered command output to session data."""
        with self._lock:
            stripped_buffer = self._command_output_buffer.strip()
            if stripped_buffer:
                self._add_session_data_unsafe(stripped_buffer, "command")
            self._command_output_buffer = ""

    def _take_snapshot(self) -> None:
        """Take a snapshot of the current session state."""
        # Flush any buffered output before taking snapshot
        self._flush_command_output_buffer()

        if self.on_session_update:
            event = self._create_session_event(SessionStatus.RUNNING)
            self.on_session_update(event)

        # Schedule next snapshot if command is still running
        if self.is_running and self.current_command:
            self.snapshot_timer = threading.Timer(20.0, self._take_snapshot)
            self.snapshot_timer.start()

    def _execute_command_with_pty(self, command: str) -> int:  # noqa: C901, PLR0912, PLR0915
        """Execute a command using pseudo-terminal for interactive support.

        Args:
            command: The command to execute
        Returns:
            Exit code of the command

        """
        master_fd, slave_fd = pty.openpty()
        old_settings = None

        try:
            # Get terminal size (use provided or detect from parent)
            if self.terminal_width is not None and self.terminal_height is not None:
                width, height = self.terminal_width, self.terminal_height
            else:
                parent_width, parent_height = self._get_terminal_size()
                width = self.terminal_width or parent_width
                height = self.terminal_height or parent_height

            # Set the PTY size
            self._set_pty_size(master_fd, width, height)

            # Start the process
            process = subprocess.Popen(  # noqa: S603   # nosec B603 user's command
                ["/bin/sh", "-c", command],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                cwd=self.work_dir,
            )

            # Store process references for programmatic input
            self._master_fd = master_fd
            self._process = process

            # Close slave fd in parent process
            os.close(slave_fd)
            slave_fd = -1  # Mark as closed

            # Save original terminal settings before making changes
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())

            # Buffer for collecting user input before logging
            user_input_buffer = ""
            # Reset command output buffer for new command
            with self._lock:
                self._command_output_buffer = ""

            while True:
                # Check if process is still running
                if process.poll() is not None:
                    break

                # Check for available data on multiple file descriptors
                ready_fds: list[int | Any]
                ready_fds, _, _ = select.select([master_fd, sys.stdin], [], [], 0.1)

                for fd in ready_fds:
                    if fd == master_fd:
                        self._handle_master_fd(master_fd)
                    elif fd == sys.stdin:
                        user_input_buffer = self._handle_stdin(
                            master_fd,
                            user_input_buffer,
                        )

            # Wait for process to complete and get return code
            return_code = process.wait()

            # Log any remaining buffered data
            if user_input_buffer.strip():
                clean_input = (
                    user_input_buffer.replace("\\r", "").replace("\\n", "").strip()
                )
                if clean_input:
                    self._add_session_data(clean_input, "user")

            # Flush any remaining command output buffer
            self._flush_command_output_buffer()
            self._read_remaining_output(master_fd)

        except OSError as e:
            error_message = str(e)
            self.logger.exception(
                "Error executing command",
                extra={"command": command},
            )
            # Set error message for later use
            self._last_error_message = error_message
            return 1

        else:
            return return_code

        finally:
            # Restore terminal settings
            if old_settings is not None:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            # Clean up process references
            self._master_fd = None
            self._process = None

            # Reset command output buffer
            with self._lock:
                self._command_output_buffer = ""

            with contextlib.suppress(OSError):
                os.close(master_fd)
            if slave_fd != -1:
                with contextlib.suppress(OSError):
                    os.close(slave_fd)

    def _handle_master_fd(self, master_fd: int) -> None:
        """Handle output from the command's master file descriptor."""
        try:
            data = os.read(master_fd, 1024)
            if data:
                # Write to stdout
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
                # Buffer the output
                decoded_data = data.decode("utf-8", errors="replace")
                with self._lock:
                    self._command_output_buffer += decoded_data

                    # Log complete lines or significant chunks
                    if "\\n" in self._command_output_buffer:
                        lines = self._command_output_buffer.split("\\n")
                        # Log all complete lines except the last one
                        for line in lines[:-1]:
                            if line.strip():  # Only log non-empty lines
                                self._add_session_data_unsafe(line, "command")
                        # Keep the last potentially incomplete line in buffer
                        self._command_output_buffer = lines[-1]
        except OSError:
            # This can happen if the process closes the PTY before we read it
            pass

    def _handle_stdin(self, master_fd: int, user_input_buffer: str) -> str:
        """Handle user input from stdin."""
        try:
            data = os.read(sys.stdin.fileno(), 1024)
            if data:
                # Write to master_fd
                os.write(master_fd, data)
                # Buffer the input
                decoded_data = data.decode("utf-8", errors="replace")
                user_input_buffer += decoded_data

                # Log when user presses Enter (complete commands)
                if "\\r" in user_input_buffer or "\\n" in user_input_buffer:
                    # Clean up the input
                    clean_input = (
                        user_input_buffer.replace("\\r", "").replace("\\n", "").strip()
                    )
                    if clean_input:
                        with self._lock:
                            self._add_session_data_unsafe(clean_input, "user")
                    user_input_buffer = ""
        except OSError:
            # Ignore errors on stdin read
            pass
        return user_input_buffer

    def _read_remaining_output(self, master_fd: int) -> None:
        """Read any remaining output from the PTY after the process has finished."""
        with contextlib.suppress(OSError):
            while True:
                ready_fds, _, _ = select.select([master_fd], [], [], 0.1)
                if not ready_fds:
                    break
                data = os.read(master_fd, 1024)
                if not data:
                    break
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
                decoded_data = data.decode("utf-8", errors="replace")
                # Log final output immediately since process is done
                if decoded_data.strip():
                    self._add_session_data(decoded_data.strip(), "command")

    def execute_command(self, command: str) -> int:
        """Execute a shell command with event callbacks.

        Args:
            command: The shell command to execute
        Returns:
            Exit code of the command

        """
        self.current_command = command
        self.command_start_time = datetime.now(UTC)
        self.status = SessionStatus.RUNNING

        # Clear previous session data and error message
        with self._lock:
            self.session_data.clear()
            self._last_error_message = None

        # Add command to session data
        self._add_session_data(command, "user")

        self.logger.info(
            "Starting command execution: %s",
            command,
            extra={"command": command},
        )

        # Start snapshot timer
        self.snapshot_timer = threading.Timer(20.0, self._take_snapshot)
        self.snapshot_timer.start()

        try:
            # Execute command
            return_code = self._execute_command_with_pty(command)

            # Update status based on return code
            if return_code != 0:
                self.status = SessionStatus.ERROR
                error_message = (
                    self._last_error_message
                    or f"Command exited with status {return_code}"
                )
            else:
                self.status = SessionStatus.COMPLETED
                error_message = None
            if self.command_start_time:
                execution_time = datetime.now(UTC) - self.command_start_time
                self.logger.info(
                    "Command completed with exit code %d in %s",
                    return_code,
                    execution_time,
                    extra={
                        "command": command,
                        "return_code": return_code,
                        "execution_time": str(execution_time),
                    },
                )

            # Flush any remaining buffered output before final event
            self._flush_command_output_buffer()

            # Send final event
            if self.on_session_complete:
                event = self._create_session_event(
                    self.status,
                    return_code,
                    error_message,
                )
                self.on_session_complete(event)

        except OSError:
            self.status = SessionStatus.ERROR
            error_message = self._last_error_message or "Unknown execution error"

            self.logger.exception("Error executing command")

            # Flush any remaining buffered output before error event
            self._flush_command_output_buffer()

            # Send error event
            if self.on_session_complete:
                event = self._create_session_event(self.status, 1, error_message)
                self.on_session_complete(event)

            return 1

        else:
            return return_code

        finally:
            # Cancel snapshot timer
            if self.snapshot_timer:
                self.snapshot_timer.cancel()
            self.current_command = None
            self.command_start_time = None
            self._last_error_message = None

    def start(self) -> None:
        """Start the terminal session."""
        self.is_running = True
        self.status = SessionStatus.IDLE

        # Save and setup signal handlers only if not already done
        if self._original_sigint_handler is None:
            self._original_sigint_handler = signal.signal(
                signal.SIGINT,
                self._signal_handler,
            )
        if self._original_sigterm_handler is None:
            self._original_sigterm_handler = signal.signal(
                signal.SIGTERM,
                self._signal_handler,
            )

    def stop(self) -> None:
        """Stop the terminal session."""
        self.is_running = False
        if self.snapshot_timer:
            self.snapshot_timer.cancel()
        self.status = SessionStatus.IDLE

        # Restore original signal handlers
        if self._original_sigint_handler is not None:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
            self._original_sigint_handler = None
        if self._original_sigterm_handler is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm_handler)
            self._original_sigterm_handler = None
