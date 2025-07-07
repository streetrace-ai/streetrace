"""Define the HelpCommand class to display available commands.

This module provides a command to list all available slash commands
in the application along with their descriptions.
"""

from typing import override

from streetrace.commands.base_command import Command
from streetrace.commands.command_executor import CommandExecutor
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class HelpCommand(Command):
    """Displays a list of all available commands with their descriptions."""

    def __init__(self, ui_bus: UiBus, cmd_executor: CommandExecutor) -> None:
        """Initialize the HelpCommand.

        Args:
            ui_bus: UI event bus to display command information.
            cmd_executor: CommandExecutor instance to get command information.

        """
        self.ui_bus = ui_bus
        self.cmd_executor = cmd_executor
        logger.debug("HelpCommand initialized")

    @property
    def names(self) -> list[str]:
        """Get command invocation names.

        Returns:
            List of command names without the leading '/'.

        """
        return ["help", "h"]

    @property
    def description(self) -> str:
        """Get command description.

        Returns:
            Description of what the command does.

        """
        return "Displays a list of all available commands with their descriptions."

    @override
    async def execute_async(self) -> None:
        """Display all registered commands with their descriptions."""
        logger.info("Executing help command")

        # Format the output
        help_text = "Available commands:\n\n"

        for cmd in self.cmd_executor.commands:
            names = ",".join([f"/{name}" for name in cmd.names])
            help_text += f"{names}: {cmd.description}\n"

        # Display the help information
        self.ui_bus.dispatch_ui_update(ui_events.Info(help_text))
