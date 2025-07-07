"""Implement the bash command to run in a terminal session.

This module defines the BashCommand class which allows users to run a bash command
in a terminal session.
"""

from pathlib import Path
from subprocess import SubprocessError  # nosec B404 used only for exception handling
from typing import override

from streetrace.input_handler import (
    HANDLED_CONT,
    SKIP,
    HandlerResult,
    InputContext,
    InputHandler,
)
from streetrace.log import get_logger
from streetrace.terminal_session import SessionData, SessionEvent, TerminalSession

logger = get_logger(__name__)


class BashHandler(InputHandler):
    """Command to run a bash command in a virtual terminal.

    Handles special command syntax: any user input starting from ! is treated as a bash
    command.
    """

    def __init__(self, work_dir: Path | None = None) -> None:
        """Initialize the BashCommand.

        Args:
            work_dir: Working directory for the command.

        """
        self.work_dir = work_dir

    @override
    async def handle(self, ctx: InputContext) -> HandlerResult:
        """Execute user input as a bash command.

        Args:
            ctx: User input processing context.

        Raises:
            OSError: If the command fails to execute.
            SubprocessError: If the command fails to execute.

        Returns:
            HandlerResult indicating handing result.

        """
        if not ctx.user_input:
            return SKIP

        cli_command = ctx.user_input.strip()
        if cli_command[0] != "!":
            return SKIP

        cli_command = cli_command[1:]

        logger.info(
            "Executing CLI command: %s",
            cli_command,
            extra={"command": cli_command},
        )

        # Collect command output
        command_error = None

        def on_session_complete(event: SessionEvent) -> None:
            nonlocal command_error
            if event.error_message:
                command_error = event.error_message

        # Create terminal session
        terminal_session = TerminalSession(
            on_session_complete=on_session_complete,
            work_dir=self.work_dir,
        )

        try:
            # Start the terminal session
            terminal_session.start()

            # Execute the command
            return_code = terminal_session.execute_command(cli_command)

            # Format the output for the model
            ctx.bash_output = self._format_cli_output(
                cli_command,
                terminal_session.session_data,
                return_code,
                command_error,
            )

        except (OSError, SubprocessError) as e:
            logger.exception(
                "CLI command execution failed",
                extra={"command": cli_command, "error": str(e)},
            )
            ctx.bash_output = str(e)
        finally:
            # Clean up terminal session
            terminal_session.stop()

        return HANDLED_CONT

    def _format_cli_output(
        self,
        command: str,
        session_data: list[SessionData],
        return_code: int,
        error_message: str | None = None,
    ) -> str:
        """Format CLI command output for the model.

        Args:
            command: The executed command
            session_data: Session data from TerminalSession
            return_code: Command return code
            error_message: Error message if any

        Returns:
            Formatted string to send to the model

        """
        lines = [f"Command: {command}"]

        if return_code is not None:
            lines.append(f"Exit code: {return_code}")

        if error_message:
            lines.append(f"Error: {error_message}")

        # Add session data output
        if session_data:
            lines.append("Output:")
            lines.extend(
                data.content for data in session_data if data.source == "command"
            )
        else:
            lines.append("Output: (no output)")

        return "\n".join(lines)
