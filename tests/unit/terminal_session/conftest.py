"""Fixtures and test utilities for terminal session tests."""

import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from streetrace.terminal_session import SessionData, SessionEvent, TerminalSession

# Use higher file descriptor numbers to avoid conflicts with pytest's internal FDs
TEST_MASTER_FD = 100
TEST_SLAVE_FD = 101

# Store the original os.close function before any mocking
_original_os_close = os.close


@pytest.fixture
def mock_terminal_session():
    """Mock terminal session with common patches."""
    # Create a more targeted mock for os.close that only affects our test FDs
    def mock_close(fd):
        if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
            # Let pytest's internal file descriptors be closed normally
            return _original_os_close(fd)
        # For our test FDs, do nothing
        return None

    with patch(
        "streetrace.terminal_session.pty.openpty",
    ) as mock_openpty, patch(
        "streetrace.terminal_session.subprocess.Popen",
    ) as mock_popen, patch(
        "streetrace.terminal_session.os.close",
        side_effect=mock_close,
    ) as mock_os_close, patch(
        "termios.tcgetattr",
    ) as mock_tcgetattr, patch(
        "termios.tcsetattr",
    ) as mock_tcsetattr, patch(
        "tty.setraw",
    ) as mock_setraw, patch(
        "streetrace.terminal_session.select.select",
    ) as mock_select, patch(
        "streetrace.terminal_session.os.read",
    ) as mock_read, patch(
        "streetrace.terminal_session.os.write",
    ) as mock_write, patch(
        "streetrace.terminal_session.sys.stdout",
    ) as mock_stdout:
        # Setup common mock returns
        mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)

        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        mock_select.return_value = ([], [], [])
        mock_read.return_value = b""

        yield {
            "openpty": mock_openpty,
            "popen": mock_popen,
            "close": mock_os_close,
            "tcgetattr": mock_tcgetattr,
            "tcsetattr": mock_tcsetattr,
            "setraw": mock_setraw,
            "select": mock_select,
            "read": mock_read,
            "write": mock_write,
            "stdout": mock_stdout,
            "process": mock_process,
        }


@pytest.fixture
def event_collector():
    """Collect session events for testing."""
    events = []

    def collect_event(event: SessionEvent) -> None:
        events.append(event)

    return events, collect_event


@pytest.fixture
def long_running_mock():
    """Mock for long-running processes."""

    def mock_close(fd):
        if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
            return _original_os_close(fd)
        return None

    with patch(
        "streetrace.terminal_session.pty.openpty",
    ) as mock_openpty, patch(
        "streetrace.terminal_session.subprocess.Popen",
    ) as mock_popen, patch(
        "streetrace.terminal_session.os.close",
        side_effect=mock_close,
    ), patch(
        "termios.tcgetattr",
    ), patch(
        "termios.tcsetattr",
    ), patch(
        "tty.setraw",
    ), patch(
        "streetrace.terminal_session.select.select",
    ) as mock_select, patch(
        "streetrace.terminal_session.os.read",
    ) as mock_read, patch(
        "streetrace.terminal_session.os.write",
    ), patch(
        "streetrace.terminal_session.sys.stdout",
    ), patch(
        "streetrace.terminal_session.sys.stdin",
    ) as mock_stdin, patch(
        "streetrace.terminal_session.threading.Timer",
    ) as mock_timer:
        # Mock stdin to have a fileno method
        mock_stdin.fileno.return_value = 0

        mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)

        # Mock a long-running process
        mock_process = Mock()
        mock_process.poll.side_effect = [None, None, None, 0]  # Running for a while
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        # Mock timer behavior
        mock_timer_instance = Mock()
        mock_timer.return_value = mock_timer_instance

        # Simulate periodic output
        mock_select.side_effect = [
            ([TEST_MASTER_FD], [], []),  # Data available
            ([], [], []),  # No data
            ([TEST_MASTER_FD], [], []),  # More data
            ([], [], []),  # Final check
        ]
        mock_read.side_effect = [
            b"Starting process...\\n",
            b"Process running...\\n",
        ]

        yield {
            "openpty": mock_openpty,
            "popen": mock_popen,
            "select": mock_select,
            "read": mock_read,
            "write": mock_write,
            "timer": mock_timer,
            "timer_instance": mock_timer_instance,
            "process": mock_process,
        }


@pytest.fixture
def failing_command_mock():
    """Mock for commands that fail."""

    def mock_close(fd):
        if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
            return _original_os_close(fd)
        return None

    with patch(
        "streetrace.terminal_session.pty.openpty",
    ) as mock_openpty, patch(
        "streetrace.terminal_session.subprocess.Popen",
    ) as mock_popen, patch(
        "streetrace.terminal_session.os.close",
        side_effect=mock_close,
    ), patch(
        "termios.tcgetattr",
    ), patch(
        "termios.tcsetattr",
    ), patch(
        "tty.setraw",
    ), patch(
        "streetrace.terminal_session.select.select",
    ) as mock_select, patch(
        "streetrace.terminal_session.os.read",
    ) as mock_read, patch(
        "streetrace.terminal_session.sys.stdout",
    ), patch(
        "streetrace.terminal_session.sys.stdin",
    ) as mock_stdin:
        # Mock stdin to have a fileno method
        mock_stdin.fileno.return_value = 0

        mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)

        mock_process = Mock()
        mock_process.poll.return_value = 1  # Failed
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        mock_select.side_effect = [
            ([TEST_MASTER_FD], [], []),  # Error output
            ([], [], []),  # No more data
        ]
        mock_read.return_value = b"Error: Command failed\\n"

        yield {
            "openpty": mock_openpty,
            "popen": mock_popen,
            "select": mock_select,
            "read": mock_read,
            "process": mock_process,
        }


@pytest.fixture
def terminal_session_factory(event_collector):
    """Create a factory for terminal sessions with event collection."""
    events, collect_event = event_collector

    def create_session(on_update=None, on_complete=None):
        """Create a terminal session with optional callbacks."""
        # Use provided callbacks or default to collector
        update_callback = on_update or collect_event
        complete_callback = on_complete or collect_event

        return TerminalSession(
            on_session_update=update_callback,
            on_session_complete=complete_callback,
        )

    return create_session, events


# Mock session data for testing
@pytest.fixture
def sample_session_data():
    """Provide sample session data for testing."""
    return [
        SessionData(
            timestamp=datetime.now(UTC),
            source="user",
            content="ls -la",
        ),
        SessionData(
            timestamp=datetime.now(UTC),
            source="command",
            content="total 0\\ndrwxr-xr-x 2 user user 60 Jan 1 12:00 .",
        ),
    ]


@pytest.fixture
def interactive_session_mock():
    """Mock for interactive sessions like Python interpreter."""

    def mock_close(fd):
        if fd not in [TEST_MASTER_FD, TEST_SLAVE_FD]:
            return _original_os_close(fd)
        return None

    with patch(
        "streetrace.terminal_session.pty.openpty",
    ) as mock_openpty, patch(
        "streetrace.terminal_session.subprocess.Popen",
    ) as mock_popen, patch(
        "streetrace.terminal_session.os.close",
        side_effect=mock_close,
    ), patch(
        "termios.tcgetattr",
    ), patch(
        "termios.tcsetattr",
    ), patch(
        "tty.setraw",
    ), patch(
        "streetrace.terminal_session.select.select",
    ) as mock_select, patch(
        "streetrace.terminal_session.os.read",
    ) as mock_read, patch(
        "streetrace.terminal_session.os.write",
    ), patch(
        "streetrace.terminal_session.sys.stdout",
    ), patch(
        "streetrace.terminal_session.sys.stdin",
    ) as mock_stdin, patch(
        "streetrace.terminal_session.threading.Timer",
    ) as mock_timer_class:
        # Mock stdin to have a fileno method
        mock_stdin.fileno.return_value = 0

        mock_openpty.return_value = (TEST_MASTER_FD, TEST_SLAVE_FD)

        # Mock interactive process (stays running)
        mock_process = Mock()
        mock_process.poll.side_effect = [None, None, None, 0]  # Running then exits
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        # Mock timer for snapshots
        mock_timer = Mock()
        mock_timer_class.return_value = mock_timer

        # Simulate interactive prompts
        mock_select.side_effect = [
            ([TEST_MASTER_FD], [], []),  # Initial prompt
            ([], [], []),  # Wait for input
            ([TEST_MASTER_FD], [], []),  # Response to input
            ([], [], []),  # Final state
        ]
        mock_read.side_effect = [
            b"Python 3.9.0\\n>>> ",
            b"42\\n>>> ",
        ]

        yield {
            "openpty": mock_openpty,
            "popen": mock_popen,
            "select": mock_select,
            "read": mock_read,
            "write": mock_write,
            "timer_class": mock_timer_class,
            "timer": mock_timer,
            "process": mock_process,
        }


@pytest.fixture
def mock_successful_process(mock_terminal_session):
    """Mock a successful process execution."""
    mock_process = Mock()
    mock_process.poll.side_effect = [None, 0]  # Running, then completed
    mock_process.wait.return_value = 0
    mock_terminal_session["popen"].return_value = mock_process

    # Default to no output
    mock_terminal_session["select"].return_value = ([], [], [])

    return mock_process


@pytest.fixture
def mock_failing_process(mock_terminal_session):
    """Mock a failing process execution."""
    mock_process = Mock()
    mock_process.poll.side_effect = [None, 1]  # Running, then failed
    mock_process.wait.return_value = 1
    mock_terminal_session["popen"].return_value = mock_process

    # Simulate error output
    mock_terminal_session["select"].side_effect = [
        ([TEST_MASTER_FD], [], []),
        ([], [], []),
    ]
    mock_terminal_session["read"].return_value = b"Error: Command failed\\n"

    return mock_process


@pytest.fixture
def mock_interactive_process(mock_terminal_session):
    """Mock an interactive process (like Python interpreter)."""
    mock_process = Mock()
    mock_process.poll.side_effect = [None, None, None, 0]  # Long running, then done
    mock_process.wait.return_value = 0
    mock_terminal_session["popen"].return_value = mock_process

    # Simulate interactive output
    mock_terminal_session["select"].side_effect = [
        ([TEST_MASTER_FD], [], []),  # Initial prompt
        ([], [], []),  # No more immediate output
        ([TEST_MASTER_FD], [], []),  # Response to input
        ([], [], []),  # Final state
    ]
    mock_terminal_session["read"].side_effect = [
        b"Python 3.12.9\\n>>> ",
        b"",
        b"Hello from automation!\\n>>> ",
        b"",
    ]

    return mock_process


@pytest.fixture
def automation_session_factory():
    """Create a factory for sessions with automation logic."""

    def create_automation_session(automation_rules: dict[str, Callable]):
        """Create a session with automation rules.

        Args:
            automation_rules: Dict mapping trigger phrases to action functions
        Returns:
            Tuple of (session, actions_taken_list)

        """
        actions_taken = []

        def automation_callback(event: SessionEvent) -> None:
            if event.status.value != "running":
                return

            # Get latest output
            latest_output = ""
            for data in reversed(event.session_data):
                if data.source == "command":
                    latest_output = data.content
                    break

            # Apply automation rules
            for trigger, action in automation_rules.items():
                if trigger.lower() in latest_output.lower():
                    action(actions_taken)
                    break

        session = TerminalSession(on_session_update=automation_callback)
        return session, actions_taken

    return create_automation_session


@pytest.fixture
def common_automation_actions():
    """Provide common automation actions for testing."""

    def help_mode_exit(actions_taken: list[str]) -> None:
        actions_taken.append("help_mode_detected")
        # Note: In real usage, you'd have access to the session instance
        # For testing, we just track that the action would be taken
        actions_taken.append("would_send_quit")

    def continue_prompt_yes(actions_taken: list[str]) -> None:
        actions_taken.append("continue_prompt_detected")
        # Note: In real usage, you'd have access to the session instance
        # For testing, we just track that the action would be taken
        actions_taken.append("would_send_yes")

    return {
        "help>": help_mode_exit,
        "continue? (y/n)": continue_prompt_yes,
        "[y/n]": continue_prompt_yes,
    }


@pytest.fixture
def temp_log_file(tmp_path: Path) -> Path:
    """Create a temporary log file for testing."""
    return tmp_path / "test_session.log"


@pytest.fixture
def session_data_examples():
    """Provide example session data for testing."""
    return [
        SessionData(
            timestamp=datetime.now(UTC),
            source="user",
            content="python",
        ),
        SessionData(
            timestamp=datetime.now(UTC),
            source="command",
            content="Python 3.12.9 (main, Mar 11 2025, 18:20:16) [GCC 14.2.1 20240910]",
        ),
        SessionData(
            timestamp=datetime.now(UTC),
            source="command",
            content='Type "help", "copyright", "credits" or "license" for more info.',
        ),
        SessionData(
            timestamp=datetime.now(UTC),
            source="user",
            content="help()",
        ),
        SessionData(
            timestamp=datetime.now(UTC),
            source="command",
            content="Welcome to Python's help utility!",
        ),
        SessionData(
            timestamp=datetime.now(UTC),
            source="command",
            content="help>",
        ),
        SessionData(
            timestamp=datetime.now(UTC),
            source="automated",
            content="quit",
        ),
    ]


@pytest.fixture
def mock_timer():
    """Mock threading.Timer for testing snapshot functionality."""
    with patch("streetrace.terminal_session.threading.Timer") as mock_timer_class:
        timer_instance = Mock()
        mock_timer_class.return_value = timer_instance

        yield {
            "Timer": mock_timer_class,
            "instance": timer_instance,
        }
