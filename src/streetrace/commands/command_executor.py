"""Manage and execute application-specific commands using a command pattern.

This module provides the CommandExecutor class which implements the command pattern
for StreetRace, enabling users to execute internal commands prefixed with '/' (e.g.,
'/help', '/exit'). It handles command registration, command lookup, validation,
and asynchronous execution with proper error handling and status reporting.
"""

from collections.abc import Sequence

from streetrace.input_handler import (
    HANDLED_STOP,
    SKIP,
    HandlerResult,
    InputContext,
    InputHandler,
)
from streetrace.log import get_logger

from .base_command import Command  # Import the base class

# Get a logger for this module
logger = get_logger(__name__)


class CommandExecutor(InputHandler):
    """Manage and execute commands derived from the Command base class.

    Handles registration of Command objects and executes them based on user input,
    passing the Application instance to the command's execute method.
    Handles case-insensitivity and basic error management during execution.
    """

    def __init__(self) -> None:
        """Initialize the CommandExecutor with an empty command registry."""
        # Stores command names (lowercase) mapped to their Command instances
        self._commands: list[Command] = []
        logger.info("CommandExecutor initialized.")

    @property
    def commands(self) -> Sequence[Command]:
        """Immutable access to registered commands."""
        return tuple(self._commands)

    def get_command(self, cmd_name: str) -> Command | None:
        """Get a registered command by name.

        Args:
            cmd_name: Name of command to retrieve.

        Returns:
            Command registered with a given name, or None if none found.

        """
        return next(
            (cmd for cmd in self._commands if cmd_name in cmd.names),
            None,
        )

    def register(self, command_instance: Command) -> None:
        """Register a Command instance.

        Args:
            command_instance: An instance of a class derived from Command.

        Raises:
            TypeError: If the provided object is not an instance of Command.
            ValueError: If the command name is empty or whitespace.

        """
        for name in command_instance.names:
            if not name.strip():
                msg = (
                    f"Command name '{name}' from {type(command_instance).__name__} "
                    "cannot be empty or whitespace."
                )
                raise ValueError(msg)

            if name != name.rstrip().lower():
                msg = (
                    f"Command name '{name}' from {type(command_instance).__name__} "
                    "cannot contain leading or trailing whitespace or uppercase "
                    "characters."
                )
                raise ValueError(msg)

            if self.get_command(name):
                msg = (
                    f"Attempt to redefine command '/{name}'. "
                    f"{type(command_instance).__name__} cannot be added because "
                    "{type(self._commands[name]).__name__} is already registered."
                )
                raise ValueError(msg)

        self._commands.append(command_instance)
        logger.debug(
            "Command %s registered as %s",
            type(command_instance).__name__,
            ",".join([f"/{name}" for name in command_instance.names]),
        )

    async def handle(
        self,
        ctx: InputContext,
    ) -> HandlerResult:
        """Attempt to execute a command based on the user input.

        Args:
            ctx: User input processing context.

        Returns:
            HandlerResult indicating handing result.

        """
        if not ctx.user_input:
            return SKIP

        command_name = ctx.user_input.strip().lower()
        if command_name.startswith("/"):
            # Remove leading '/' if present and make lowercase
            command_name = command_name[1:]
        else:
            # If input doesn't start with '/', it's not a command for this executor
            return SKIP

        command_instance = self.get_command(command_name)

        if not command_instance:
            # Input started with '/' but didn't match any registered command
            logger.debug(
                "Input '%s' is not a valid command name.",
                ctx.user_input,
            )
            # Conventionally, unrecognized commands don't stop the app.
            # We return False because *this specific input* wasn't a known command.
            return SKIP

        logger.info("Executing command: '/%s'", command_name)
        try:
            await command_instance.execute_async()
        except Exception as e:
            logger.exception(
                "Error executing command '/%s'",
                command_name,
            )
            # Command was found and attempted, but failed during execution.
            # Signal to continue the application loop.
            ctx.error = f"Error executing command '/{command_name}' ({e!s})"

        return HANDLED_STOP
