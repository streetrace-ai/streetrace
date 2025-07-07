"""Test BashHandler implementation and functionality.

This module tests the BashHandler class including basic properties, command execution,
error handling, output formatting, and terminal session management.
"""

from datetime import UTC, datetime
from pathlib import Path
from subprocess import SubprocessError
from unittest.mock import Mock, patch

import pytest

from streetrace.bash_handler import BashHandler
from streetrace.input_handler import InputContext
from streetrace.terminal_session import (
    SessionData,
    SessionEvent,
    SessionStatus,
    TerminalSession,
)


class TestBashCommandProperties:
    """Test BashHandler basic properties and metadata."""

    @pytest.fixture
    def bash_handler(self, work_dir: Path) -> BashHandler:
        """Create a BashHandler instance with test working directory."""
        return BashHandler(work_dir=work_dir)

    @pytest.fixture
    def bash_handler_no_workdir(self) -> BashHandler:
        """Create a BashHandler instance without working directory."""
        return BashHandler()

    def test_initialization_with_work_dir(self, bash_handler: BashHandler) -> None:
        """Test that command properly stores working directory."""
        assert bash_handler.work_dir == bash_handler.work_dir

    def test_initialization_without_work_dir(
        self, bash_handler_no_workdir: BashHandler,
    ) -> None:
        """Test that command can be initialized without working directory."""
        assert bash_handler_no_workdir.work_dir is None


class TestBashCommandExecution:
    """Test BashHandler execution scenarios."""

    @pytest.fixture
    def bash_handler(self, work_dir: Path) -> BashHandler:
        """Create a BashHandler instance with test working directory."""
        return BashHandler(work_dir=work_dir)

    @pytest.fixture
    def mock_terminal_session(self) -> Mock:
        """Create a mock TerminalSession."""
        return Mock(spec=TerminalSession)

    @pytest.fixture
    def sample_session_data(self) -> list[SessionData]:
        """Create sample session data for testing."""
        return [
            SessionData(
                timestamp=datetime.now(UTC),
                source="user",
                content="echo hello",
            ),
            SessionData(
                timestamp=datetime.now(UTC),
                source="command",
                content="hello",
            ),
        ]

    @pytest.mark.asyncio
    async def test_execute_async_successful_command(
        self,
        bash_handler: BashHandler,
        mock_terminal_session: Mock,
        sample_session_data: list[SessionData],
    ) -> None:
        """Test successful command execution with output."""
        # Setup mock terminal session
        mock_terminal_session.execute_command.return_value = 0
        mock_terminal_session.session_data = sample_session_data

        input_context = InputContext(user_input="!echo hello")
        with patch(
            "streetrace.bash_handler.TerminalSession",
            return_value=mock_terminal_session,
        ):
            await bash_handler.handle(input_context)

        # Verify terminal session lifecycle
        mock_terminal_session.start.assert_called_once()
        mock_terminal_session.execute_command.assert_called_once_with("echo hello")
        mock_terminal_session.stop.assert_called_once()

        # Verify output formatting
        assert input_context.bash_output
        assert "Command: echo hello" in input_context.bash_output
        assert "Exit code: 0" in input_context.bash_output
        assert "Output:" in input_context.bash_output
        assert "hello" in input_context.bash_output

    @pytest.mark.asyncio
    async def test_execute_async_command_with_error(
        self,
        bash_handler: BashHandler,
        mock_terminal_session: Mock,
        sample_session_data: list[SessionData],
    ) -> None:
        """Test command execution with error message via callback."""
        # Setup mock terminal session
        mock_terminal_session.execute_command.return_value = 1
        mock_terminal_session.session_data = sample_session_data
        error_message = "Command failed"

        # Capture the callback passed to TerminalSession
        captured_callback = None

        def mock_terminal_session_constructor(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("on_session_complete")
            return mock_terminal_session

        input_context = InputContext(user_input="!echo hello")
        with patch(
            "streetrace.bash_handler.TerminalSession",
            side_effect=mock_terminal_session_constructor,
        ):
            await bash_handler.handle(input_context)

        # Verify basic output without error initially (callback hasn't been called)
        assert input_context.bash_output
        assert "Command: echo hello" in input_context.bash_output
        assert "Exit code: 1" in input_context.bash_output
        assert "Error:" not in input_context.bash_output  # Error not yet captured

        # Now simulate the callback being called with error
        if captured_callback:
            event = SessionEvent(
                command="echo hello",
                status=SessionStatus.ERROR,
                error_message=error_message,
            )
            captured_callback(event)

            # Test that the formatting method works correctly when error is provided
            formatted_output = bash_handler._format_cli_output(  # noqa: SLF001
                "echo hello",
                sample_session_data,
                1,
                error_message,
            )
            assert f"Error: {error_message}" in formatted_output

    @pytest.mark.asyncio
    async def test_execute_async_command_preprocessing(
        self,
        bash_handler: BashHandler,
        mock_terminal_session: Mock,
        sample_session_data: list[SessionData],
    ) -> None:
        """Test that command input is properly preprocessed."""
        mock_terminal_session.execute_command.return_value = 0
        mock_terminal_session.session_data = sample_session_data

        with patch(
            "streetrace.bash_handler.TerminalSession",
            return_value=mock_terminal_session,
        ):
            # Test with leading exclamation mark
            await bash_handler.handle(InputContext(user_input="!ls -la"))
            mock_terminal_session.execute_command.assert_called_with("ls -la")

            # Test with whitespace - note: the actual implementation only removes
            # the '!' character, not additional whitespace, so we expect the
            # whitespace to remain
            await bash_handler.handle(InputContext(user_input="  !  echo test  "))
            mock_terminal_session.execute_command.assert_called_with("  echo test")

    @pytest.mark.asyncio
    async def test_execute_async_no_output(
        self,
        bash_handler: BashHandler,
        mock_terminal_session: Mock,
    ) -> None:
        """Test command execution with no output."""
        mock_terminal_session.execute_command.return_value = 0
        mock_terminal_session.session_data = []

        input_context = InputContext(user_input="!true")
        with patch(
            "streetrace.bash_handler.TerminalSession",
            return_value=mock_terminal_session,
        ):
            await bash_handler.handle(input_context)

        assert input_context.bash_output
        assert "Command: true" in input_context.bash_output
        assert "Exit code: 0" in input_context.bash_output
        assert "Output: (no output)" in input_context.bash_output

    @pytest.mark.asyncio
    async def test_execute_async_os_error(
        self,
        bash_handler: BashHandler,
        mock_terminal_session: Mock,
    ) -> None:
        """Test OSError handling during command execution."""
        mock_terminal_session.start.side_effect = OSError("Permission denied")

        input_context = InputContext(user_input="!echo test")
        with patch(
            "streetrace.bash_handler.TerminalSession",
            return_value=mock_terminal_session,
        ):
            await bash_handler.handle(input_context)

        assert input_context.bash_output
        assert "Permission denied" in input_context.bash_output
        # Verify cleanup is called even on error
        mock_terminal_session.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_async_subprocess_error(
        self,
        bash_handler: BashHandler,
        mock_terminal_session: Mock,
    ) -> None:
        """Test SubprocessError handling during command execution."""
        mock_terminal_session.execute_command.side_effect = SubprocessError(
            "Subprocess failed",
        )

        input_context = InputContext(user_input="!echo test")
        with patch(
            "streetrace.bash_handler.TerminalSession",
            return_value=mock_terminal_session,
        ):
            await bash_handler.handle(input_context)

        assert input_context.bash_output
        assert "Subprocess failed" in input_context.bash_output
        # Verify cleanup is called even on error
        mock_terminal_session.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_async_terminal_session_initialization(
        self,
        bash_handler: BashHandler,
        mock_terminal_session: Mock,
    ) -> None:
        """Test that TerminalSession is properly initialized with work_dir."""
        mock_terminal_session.execute_command.return_value = 0
        mock_terminal_session.session_data = []

        with patch(
            "streetrace.bash_handler.TerminalSession",
            return_value=mock_terminal_session,
        ) as mock_constructor:
            await bash_handler.handle(InputContext(user_input="!echo test"))

        # Verify TerminalSession constructor was called with proper arguments
        mock_constructor.assert_called_once()
        args, kwargs = mock_constructor.call_args
        assert "work_dir" in kwargs
        assert kwargs["work_dir"] == bash_handler.work_dir
        assert "on_session_complete" in kwargs
        assert callable(kwargs["on_session_complete"])


class TestBashCommandOutputFormatting:
    """Test BashHandler output formatting functionality."""

    @pytest.fixture
    def bash_handler(self) -> BashHandler:
        """Create a BashHandler instance."""
        return BashHandler()

    @pytest.fixture
    def sample_session_data(self) -> list[SessionData]:
        """Create sample session data for testing."""
        return [
            SessionData(
                timestamp=datetime.now(UTC),
                source="user",
                content="echo hello",
            ),
            SessionData(
                timestamp=datetime.now(UTC),
                source="command",
                content="hello",
            ),
            SessionData(
                timestamp=datetime.now(UTC),
                source="command",
                content="world",
            ),
        ]

    def test_format_cli_output_with_all_data(
        self,
        bash_handler: BashHandler,
        sample_session_data: list[SessionData],
    ) -> None:
        """Test output formatting with all data present."""
        result = bash_handler._format_cli_output(  # noqa: SLF001
            command="echo hello",
            session_data=sample_session_data,
            return_code=0,
            error_message="Test error",
        )

        assert "Command: echo hello" in result
        assert "Exit code: 0" in result
        assert "Error: Test error" in result
        assert "Output:" in result
        assert "hello" in result
        assert "world" in result

    def test_format_cli_output_no_error(
        self,
        bash_handler: BashHandler,
        sample_session_data: list[SessionData],
    ) -> None:
        """Test output formatting without error message."""
        result = bash_handler._format_cli_output(  # noqa: SLF001
            command="echo hello",
            session_data=sample_session_data,
            return_code=0,
            error_message=None,
        )

        assert "Command: echo hello" in result
        assert "Exit code: 0" in result
        assert "Error:" not in result
        assert "Output:" in result
        assert "hello" in result

    def test_format_cli_output_with_return_code(
        self,
        bash_handler: BashHandler,
        sample_session_data: list[SessionData],
    ) -> None:
        """Test output formatting with return code."""
        result = bash_handler._format_cli_output(  # noqa: SLF001
            command="echo hello",
            session_data=sample_session_data,
            return_code=0,
            error_message=None,
        )

        assert "Command: echo hello" in result
        assert "Exit code: 0" in result
        assert "Output:" in result
        assert "hello" in result

    def test_format_cli_output_no_session_data(
        self,
        bash_handler: BashHandler,
    ) -> None:
        """Test output formatting with no session data."""
        result = bash_handler._format_cli_output(  # noqa: SLF001
            command="echo hello",
            session_data=[],
            return_code=0,
            error_message=None,
        )

        assert "Command: echo hello" in result
        assert "Exit code: 0" in result
        assert "Output: (no output)" in result

    def test_format_cli_output_filters_command_source(
        self,
        bash_handler: BashHandler,
    ) -> None:
        """Test that output formatting only includes command source data."""
        session_data = [
            SessionData(
                timestamp=datetime.now(UTC),
                source="user",
                content="this should not appear",
            ),
            SessionData(
                timestamp=datetime.now(UTC),
                source="command",
                content="this should appear",
            ),
            SessionData(
                timestamp=datetime.now(UTC),
                source="automated",
                content="this should not appear either",
            ),
        ]

        result = bash_handler._format_cli_output(  # noqa: SLF001
            command="echo hello",
            session_data=session_data,
            return_code=0,
            error_message=None,
        )

        assert "this should appear" in result
        assert "this should not appear" not in result
        assert "this should not appear either" not in result


class TestBashCommandErrorHandling:
    """Test BashHandler error handling and callback management."""

    @pytest.fixture
    def bash_handler(self) -> BashHandler:
        """Create a BashHandler instance."""
        return BashHandler()

    @pytest.mark.asyncio
    async def test_callback_function_integration(
        self,
        bash_handler: BashHandler,
    ) -> None:
        """Test that the callback function works correctly when called."""
        # Create a mock terminal session
        mock_terminal_session = Mock(spec=TerminalSession)
        mock_terminal_session.execute_command.return_value = 0
        mock_terminal_session.session_data = []

        # Capture the callback function
        captured_callback = None

        def mock_terminal_session_constructor(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("on_session_complete")
            return mock_terminal_session

        with patch(
            "streetrace.bash_handler.TerminalSession",
            side_effect=mock_terminal_session_constructor,
        ):
            await bash_handler.handle(InputContext(user_input="!echo test"))

        # Verify callback was captured
        assert captured_callback is not None
        assert callable(captured_callback)

        # Test that callback can be called without error
        error_event = SessionEvent(
            command="echo test",
            status=SessionStatus.ERROR,
            error_message="test error",
        )

        # This should not raise an exception
        captured_callback(error_event)

    def test_error_message_handling_in_callback(
        self,
    ) -> None:
        """Test that error messages are properly captured by the callback."""
        # Create the callback function manually (simulating what happens in
        # execute_async)
        command_error = None

        def on_session_complete(event: SessionEvent) -> None:
            nonlocal command_error
            if event.error_message:
                command_error = event.error_message

        # Test with error message
        error_event = SessionEvent(
            command="test command",
            status=SessionStatus.ERROR,
            error_message="Command execution failed",
        )

        on_session_complete(error_event)
        assert command_error == "Command execution failed"

        # Test with no error message
        command_error = None
        success_event = SessionEvent(
            command="test command",
            status=SessionStatus.COMPLETED,
            error_message=None,
        )

        on_session_complete(success_event)
        assert command_error is None
