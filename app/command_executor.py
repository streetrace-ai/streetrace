# app/command_executor.py
import logging
from typing import Callable, Dict, Tuple, List

# Get a logger for this module
logger = logging.getLogger(__name__)

class CommandExecutor:
    """
    Manages and executes user-defined commands for the application.

    Handles registration of commands and their corresponding actions.
    Executes commands based on user input, handling case-insensitivity
    and basic error management during action execution.
    """
    def __init__(self):
        """Initializes the CommandExecutor with an empty command registry."""
        # Stores command names (lowercase) mapped to their action callables
        self._commands: Dict[str, Callable[[], bool]] = {}
        logger.info("CommandExecutor initialized.")

    def register(self, name: str, action: Callable[[], bool]):
        """
        Registers a command with its associated action.

        Args:
            name: The name of the command (will be treated case-insensitively).
            action: A callable that takes no arguments and returns a boolean.
                    Returning False signals the application should exit,
                    True signals it should continue.

        Raises:
            ValueError: If the command name is empty or whitespace.
            TypeError: If the action is not callable.
        """
        if not callable(action):
            raise TypeError(f"Action for command '{name}' must be callable.")
        
        clean_name = name.strip().lower()
        if not clean_name:
             raise ValueError("Command name cannot be empty or whitespace.")

        if clean_name in self._commands:
            logger.warning(f"Command '{clean_name}' is being redefined.")
        
        self._commands[clean_name] = action
        logger.debug(f"Command '{clean_name}' registered.")

    def get_commands(self) -> List[str]:
        """
        Returns a sorted list of registered command names.

        Returns:
            A list of command names in alphabetical order.
        """
        return sorted(self._commands.keys())

    def execute(self, user_input: str) -> Tuple[bool, bool]:
        """
        Attempts to execute a command based on the user input.

        Args:
            user_input: The raw input string from the user.

        Returns:
            A tuple (command_executed: bool, should_continue: bool):
            - command_executed: True if the input matched a registered command
                                and the action was attempted, False otherwise.
            - should_continue: The boolean result from the command's action
                               (False to exit, True to continue). If the command
                               was not found, defaults to True. If an error
                               occurred during action execution, defaults to True.
        """
        command = user_input.strip().lower()

        if command in self._commands:
            logger.info(f"Executing command: '{command}'")
            action = self._commands[command]
            try:
                # Execute the action and capture its return value
                should_continue = action()
                if not isinstance(should_continue, bool):
                    logger.error(f"Action for command '{command}' did not return a boolean. Assuming continue.")
                    return True, True # Command executed, but faulty action, continue
                
                logger.debug(f"Command '{command}' action returned: {should_continue}")
                return True, should_continue # Command executed, return action's signal
            except Exception as e:
                # Log the error and inform the user via logger
                logger.error(f"Error executing action for command '{command}': {e}", exc_info=True)
                # We might want a UI component to display this later
                # For now, log it and signal to continue the application loop
                return True, True # Command executed, but failed, continue
        else:
            # Input did not match any registered command
            logger.debug(f"Input '{user_input}' is not a registered command.")
            return False, True # Command not executed, continue
