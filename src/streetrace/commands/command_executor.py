"""Manage and execute commands derived from the Command base class.

This module provides the CommandExecutor class which handles registration,
lookup, and execution of commands in the application.
"""

import logging
from typing import TYPE_CHECKING

from .base_command import Command  # Import the base class

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from streetrace.application import Application

# Get a logger for this module
logger = logging.getLogger(__name__)


class CommandExecutor:
    """Manage and execute commands derived from the Command base class.

    Handles registration of Command objects and executes them based on user input,
    passing the Application instance to the command's execute method.
    Handles case-insensitivity and basic error management during execution.
    """

    def __init__(self) -> None:
        """Initialize the CommandExecutor with an empty command registry."""
        # Stores command names (lowercase) mapped to their Command instances
        self._commands: dict[str, Command] = {}
        logger.info("CommandExecutor initialized.")

    def register(self, command_instance: Command) -> None:
        """Register a Command instance.

        Args:
            command_instance: An instance of a class derived from Command.

        Raises:
            TypeError: If the provided object is not an instance of Command.
            ValueError: If the command name is empty or whitespace.

        """
        if not isinstance(command_instance, Command):
            msg = f"Object {command_instance} is not an instance of Command."
            raise TypeError(msg)

        for name in command_instance.names:
            if not name.strip():
                msg = f"Command name '{name}' from {type(command_instance).__name__} cannot be empty or whitespace."
                raise ValueError(msg)

            if name != name.rstrip().lower():
                msg = f"Command name '{name}' from {type(command_instance).__name__} cannot contain leading or trailing whitespace or uppercase characters."
                raise ValueError(msg)

            if name in self._commands:
                msg = f"Attempt to redefine command '/{name}'. {type(command_instance).__name__} cannot be added because {type(self._commands[name]).__name__} is already registered."
                raise ValueError(msg)

            self._commands[name] = command_instance
            logger.debug(
                "Command '/%s' (%s) registered: %s",
                name,
                type(command_instance).__name__,
                command_instance.description,
            )

    def get_commands(self) -> list[str]:
        """Return a sorted list of registered command names (lowercase).

        Returns:
            A list of command names (e.g., 'exit', 'history') in registration order.

        """
        return list(self._commands.keys())

    def get_command_descriptions(self) -> dict[str, str]:
        """Return a dictionary of command names (lowercase) and their descriptions."""
        return {name: cmd.description for name, cmd in self._commands.items()}

    def get_command_names_with_prefix(self) -> list[str]:
        """Return a sorted list of registered command names, prefixed with '/'.

        Returns:
            A list of command names (e.g., '/exit', '/history') in registration order.

        """
        return [f"/{name}" for name in self._commands]

    def execute(
        self,
        user_input: str,
        app_instance: "Application",
    ) -> tuple[bool, bool]:
        """Attempt to execute a command based on the user input.

        Args:
            user_input: The raw input string from the user (e.g., "/exit").
            app_instance: The Application instance to pass to the command's execute method.

        Returns:
            A tuple (command_executed: bool, should_continue: bool):
            - command_executed: True if the input (stripping '/') matched a registered command
                                and its execute method was called, False otherwise.
            - should_continue: The boolean result from the command's execute method
                               (False to exit, True to continue). If the command
                               was not found, defaults to True. If an error
                               occurred during execution, defaults to True.

        """
        # Remove leading '/' if present and make lowercase
        command_name = user_input.strip().lower()
        if command_name.startswith("/"):
            command_name = command_name[1:]
        else:
            # If input doesn't start with '/', it's not a command for this executor
            return False, True

        if command_name not in self._commands:
            # Input started with '/' but didn't match any registered command
            logger.debug(
                "Input '%s' is not a valid command name.",
                user_input,
            )
            # Conventionally, unrecognized commands don't stop the app.
            # We return False because *this specific input* wasn't a known command.
            return False, True

        command_instance = self._commands[command_name]
        logger.info("Executing command: '/%s'", command_name)
        try:
            # Pass the required app_instance to the command's execute method
            should_continue = command_instance.execute(app_instance)
        except Exception:
            logger.exception(
                "Error executing command '/%s' (%s)",
                command_name,
                type(command_instance).__name__,
            )
            # Command was found and attempted, but failed during execution.
            # Signal to continue the application loop.
            return True, True
        else:
            if not isinstance(should_continue, bool):
                # If the command's execute method doesn't return a boolean, raise an error
                msg = "Command execute method should return a boolean"
                raise TypeError(msg)

            logger.debug(
                "Command '/%s' executed. Result: %s.",
                command_name,
                "continue" if should_continue else "exit",
            )
            return True, should_continue  # Command executed, return its signal
