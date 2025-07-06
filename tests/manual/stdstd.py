"""Terminal emulator with interactive shell command execution and logging.

This module provides a terminal emulator that allows users to execute shell commands
interactively with comprehensive logging capabilities.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import print_formatted_text
from prompt_toolkit.styles import Style

from streetrace.log import get_logger
from streetrace.terminal_session import SessionEvent, SessionStatus, TerminalSession

# Constants
LOG_FILE_NAME: str = "terminal_session.log"
"""Name of the log file for terminal session output."""

PROMPT_STYLE: str = "ansigreen bold"
"""Style for the terminal prompt."""

ERROR_STYLE: str = "ansired bold"
"""Style for error messages."""

INFO_STYLE: str = "ansiblue"
"""Style for info messages."""


class SessionLogger:
    """Handles logging of terminal session events."""

    def __init__(self, log_file_path: Path) -> None:
        """Initialize the session logger.

        Args:
            log_file_path: Path to the log file

        """
        self.logger = get_logger(__name__)
        self.log_file_path = log_file_path

    def _format_session_data(self, event: SessionEvent) -> str:
        """Format session data for logging.

        Args:
            event: Session event to format
        Returns:
            Formatted string for logging

        """
        lines = []
        for data in event.session_data:
            timestamp = data.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"[{timestamp}] {data.source}: {data.content}")
        return "\n".join(lines)

    def _write_to_log_file(
        self,
        content: str,
        message_type: str,
        event: SessionEvent,
    ) -> None:
        """Write content to the log file.

        Args:
            content: Content to write to the log file
            message_type: Type of message (snapshot/final)
            event: Session event for context

        """
        try:
            with self.log_file_path.open("a", encoding="utf-8") as log_file:
                log_file.write(f"\\n{'=' * 50}\\n")
                log_file.write(f"{message_type.upper()} - {datetime.now(UTC)}\\n")
                log_file.write(f"Command: {event.command}\\n")
                log_file.write(f"Status: {event.status.value}\\n")
                if event.return_code is not None:
                    log_file.write(f"Return Code: {event.return_code}\\n")
                if event.execution_time is not None:
                    log_file.write(f"Execution Time: {event.execution_time:.2f}s\\n")
                log_file.write(f"{'=' * 50}\\n")
                log_file.write(content)
                log_file.write(f"\\n{'=' * 50}\\n\\n")
                log_file.flush()
            self.logger.info(
                "Logged %s to %s",
                message_type,
                self.log_file_path,
                extra={
                    "message_type": message_type,
                    "file_path": str(self.log_file_path),
                },
            )
        except OSError:
            self.logger.exception(
                "Failed to write to log file: %s",
                extra={"file_path": str(self.log_file_path)},
            )

    def on_session_update(self, event: SessionEvent) -> None:
        """Handle session update events (snapshots).

        Args:
            event: Session update event

        """
        content = self._format_session_data(event)
        if content:
            self._write_to_log_file(content, "snapshot", event)

    def on_session_complete(self, event: SessionEvent) -> None:
        """Handle session completion events.

        Args:
            event: Session completion event

        """
        content = self._format_session_data(event)
        if content:
            self._write_to_log_file(content, "final", event)


class TerminalEmulator:
    """Main terminal emulator class with interactive prompt."""

    def __init__(
        self,
        log_file_path: Path | None = None,
        *,
        enable_automation: bool = True,
        terminal_width: int | None = None,
        terminal_height: int | None = None,
    ) -> None:
        """Initialize the terminal emulator.

        Args:
            log_file_path: Path to the log file. If None, uses current directory.
            enable_automation: Whether to enable automated input based on heuristics
            terminal_width: Terminal width in columns (defaults to parent value)
            terminal_height: Terminal height in rows (defaults to parent value)

        """
        self.logger = get_logger(__name__)
        self.log_file_path = log_file_path or Path(LOG_FILE_NAME)
        self.enable_automation = enable_automation

        # Create session logger
        self.session_logger = SessionLogger(self.log_file_path)

        # Create terminal session with callbacks
        self.terminal_session = TerminalSession(
            on_session_update=self._on_session_update,
            on_session_complete=self._on_session_complete,
            terminal_width=terminal_width,
            terminal_height=terminal_height,
        )

        self.history = InMemoryHistory()

        # Setup prompt session with style
        self.style = Style.from_dict(
            {
                "prompt": PROMPT_STYLE,
                "error": ERROR_STYLE,
                "info": INFO_STYLE,
                "automated": "ansimagenta",
            },
        )

        self.prompt_session = PromptSession(  # type: ignore[var-annotated]
            history=self.history,
            style=self.style,
        )

    def _print_welcome_message(self) -> None:
        """Print welcome message to the user."""
        welcome_text = [
            ("class:info", "Terminal Emulator started"),
            ("", "\\n"),
            ("class:info", f"Session log will be written to: {self.log_file_path}"),
            ("", "\\n"),
            ("class:info", "Type 'exit' to quit"),
            ("", "\\n"),
        ]
        print_formatted_text(welcome_text, style=self.style)

    def _print_error(self, message: str) -> None:
        """Print error message to the user.

        Args:
            message: Error message to display

        """
        error_text = [("class:error", f"Error: {message}")]
        print_formatted_text(error_text, style=self.style)

    def _print_automated_action(self, message: str) -> None:
        """Print automated action message to the user.

        Args:
            message: Action message to display

        """
        automated_text = [("class:automated", f"[AUTOMATED] {message}")]
        print_formatted_text(automated_text, style=self.style)
        self.terminal_session.send_input("quit")

    def _on_session_update(self, event: SessionEvent) -> None:
        """Handle session update events with automation logic.

        Args:
            event: Session update event

        """
        # First, log the update
        self.session_logger.on_session_update(event)

        # Then, apply automation heuristics if enabled
        if self.enable_automation and event.status == SessionStatus.RUNNING:
            self._apply_automation_heuristics(event)

    def _on_session_complete(self, event: SessionEvent) -> None:
        """Handle session completion events.

        Args:
            event: Session completion event

        """
        # Log the completion
        self.session_logger.on_session_complete(event)

    def _apply_automation_heuristics(self, event: SessionEvent) -> None:
        """Apply automation heuristics based on session data.

        Args:
            event: Current session event

        """
        if not event.session_data:
            return

        # Get the latest command output
        latest_output = ""
        for data in reversed(event.session_data):
            if data.source == "command":
                latest_output = data.content
                break

        if not latest_output:
            return

        # Example heuristics - you can extend these
        self._check_for_python_interactive_prompts(latest_output)
        self._check_for_common_interactive_prompts(latest_output)

    def _check_for_python_interactive_prompts(self, output: str) -> None:
        """Check for Python interactive prompts and provide helpful responses.

        Args:
            output: Latest command output

        """
        # Example: Detect Python help() prompt
        if "help>" in output.lower():
            self._print_automated_action(
                "Detected Python help prompt. You can type 'quit' to exit help.",
            )

        # Example: Detect Python >>> prompt after an import
        if ">>>" in output and any(
            keyword in output.lower() for keyword in ["import", "from"]
        ):
            # This is just an example - you can add more sophisticated logic
            pass

    def _check_for_common_interactive_prompts(self, output: str) -> None:
        """Check for common interactive prompts and provide responses.

        Args:
            output: Latest command output

        """
        # Example: Detect "Press Enter to continue" or similar
        if any(
            phrase in output.lower()
            for phrase in [
                "press enter to continue",
                "press any key to continue",
                "continue? (y/n)",
                "[y/n]",
                "do you want to continue",
            ]
        ):
            self._print_automated_action(
                "Detected continuation prompt. I could automate this response.",
            )

    def send_input_to_process(
        self,
        input_text: str,
        *,
        add_newline: bool = True,
    ) -> bool:
        """Send input to the currently running process.

        Args:
            input_text: Text to send to the process
            add_newline: Whether to add a newline at the end
        Returns:
            True if input was sent successfully, False otherwise

        """
        if self.terminal_session.send_input(input_text, add_newline=add_newline):
            self._print_automated_action(f"Sent input: {input_text!r}")
            return True
        return False

    def run(self) -> None:
        """Run the terminal emulator main loop."""
        self.logger.info("Starting terminal emulator")
        self.terminal_session.start()

        self._print_welcome_message()

        try:
            while self.terminal_session.is_running:
                try:
                    # Get user input
                    user_input = self.prompt_session.prompt(
                        [("class:prompt", "$ ")],
                        style=self.style,
                    ).strip()

                    # Handle built-in commands
                    if user_input.lower() in ("exit", "quit"):
                        break

                    if not user_input:
                        continue

                    # Execute the command
                    return_code = self.terminal_session.execute_command(user_input)

                    if return_code != 0:
                        self._print_error(f"Command exited with code {return_code}")

                except KeyboardInterrupt:
                    self._print_error("\\nUse 'exit' to quit")
                    continue
                except EOFError:
                    break
                except Exception:
                    self.logger.exception("Unexpected error in main loop")
                    self._print_error("Unexpected error")

        finally:
            self.terminal_session.stop()
            self.logger.info("Terminal emulator stopped")


def main() -> None:
    """Run the main entry point for the terminal emulator."""
    try:
        # Create terminal emulator with log file in current directory
        log_file_path = Path.cwd() / LOG_FILE_NAME

        emulator = TerminalEmulator(
            log_file_path,
            enable_automation=True,
        )

        # Run the emulator
        emulator.run()

    except Exception as e:
        logger = get_logger(__name__)
        logger.exception("Fatal error in terminal emulator")
        message = f"Fatal error: {e!s}"
        print(message, file=sys.stderr)  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
