# app/console_ui.py
import os
import sys
from streetrace.ui.colors import AnsiColors # Assuming colors.py is accessible

class ConsoleUI:
    """
    Handles all console input and output for the StreetRace application.

    Encapsulates print statements and ANSI color codes for consistent UI.
    """
    def __init__(self, debug_enabled: bool = False):
        """
        Initializes the ConsoleUI.

        Args:
            debug_enabled: If True, enables printing of debug messages.
        """
        self.debug_enabled = debug_enabled

    def _splitter(self, splitter_char: str = '━') -> str:
        """
        Returns a string used to separate different sections of output.
        """
        return splitter_char*os.get_terminal_size().columns

    def _title(self, title: str) -> str:
        """
        Returns a string used to separate different sections of output.
        """
        return f"  {title}  \n{self._splitter('═')}"

    def get_user_input(self, prompt: str = "You: ") -> str:
        """
        Gets input from the user via the console.

        Args:
            prompt: The prompt string to display to the user.

        Returns:
            The string entered by the user.
        """
        # Use AnsiColors for the prompt string itself
        colored_prompt = f"{AnsiColors.USER}{prompt}{AnsiColors.RESET} "
        try:
            return input(colored_prompt)
        except EOFError:
            # Propagate EOFError to be handled by the main loop
            raise
        except KeyboardInterrupt:
            # Propagate KeyboardInterrupt to be handled by the main loop
            raise

    def display_system_message(self, message: str, color: str = AnsiColors.DEBUG):
        """
        Displays an informational message to the console.

        Args:
            message: The message string to display.
            color: The AnsiColors code to use for the message. Defaults to INFO.
        """
        print(f"{color}{self._splitter()}\n{self._title("System instructions")}\n{message}\n{AnsiColors.RESET}")

    def display_context_message(self, message: str, color: str = AnsiColors.INFO):
        """
        Displays an informational message to the console.

        Args:
            message: The message string to display.
            color: The AnsiColors code to use for the message. Defaults to INFO.
        """
        print(f"{color}{self._splitter()}\n{self._title("Context")}\n{message}\n{AnsiColors.RESET}")

    def display_history_assistant_message(self, message: str, color: str = AnsiColors.INFO):
        """
        Displays an informational message to the console.

        Args:
            message: The message string to display.
            color: The AnsiColors code to use for the message. Defaults to INFO.
        """
        print(f"{color}{self._splitter()}\n{self._title("Assistant:")}\n{message}\n{AnsiColors.RESET}")

    def display_history_user_message(self, message: str, color: str = AnsiColors.INFO):
        """
        Displays an informational message to the console.

        Args:
            message: The message string to display.
            color: The AnsiColors code to use for the message. Defaults to INFO.
        """
        print(f"{color}{self._splitter()}\n{self._title("User:")}\n{message}\n{AnsiColors.RESET}")

    def display_message(self, message: str, color: str = AnsiColors.INFO):
        """
        Displays an informational message to the console.

        Args:
            message: The message string to display.
            color: The AnsiColors code to use for the message. Defaults to INFO.
        """
        print(f"{color}{message}{AnsiColors.RESET}")

    def display_info(self, message: str):
        """Displays a standard informational message."""
        self.display_message(message, AnsiColors.INFO)

    def display_warning(self, message: str):
        """Displays a warning message."""
        # Add a [Warning] prefix for clarity
        self.display_message(f"[Warning] {message}", AnsiColors.WARNING)

    def display_error(self, message: str):
        """Displays an error message."""
        # Add an [Error] prefix for clarity
        self.display_message(f"[Error] {message}", AnsiColors.TOOLERROR) # Using TOOLERROR color for errors

    def display_debug(self, message: str):
        """Displays a debug message only if debug mode is enabled."""
        if self.debug_enabled:
            # Add a [Debug] prefix for clarity
            self.display_message(f"[Debug] {message}", AnsiColors.DEBUG) # Assuming DEBUG color exists

    def display_ai_response_chunk(self, chunk: str):
        """
        Displays a chunk of the AI's response, typically used for streaming.
        Prints directly without extra formatting or newlines.
        """
        # We use sys.stdout.write and flush for streaming compatibility
        sys.stdout.write(f"{AnsiColors.ASSISTANT}{chunk}{AnsiColors.RESET}")
        sys.stdout.flush()

    def display_tool_call(self, tool_name: str, args_display: str):
        """Displays information about a tool being called."""
        self.display_message(f"Tool Call: {tool_name}({args_display})", AnsiColors.TOOL)

    def display_tool_result(self, result_display: str):
        """Displays the result of a tool execution."""
        # Shorten long results for display
        if len(result_display) > 500:
             result_display = result_display[:497] + "..."
        self.display_message(f"Result: {result_display}", AnsiColors.TOOL)

    def display_user_prompt(self, prompt: str):
        """Displays the user's prompt (e.g., in non-interactive mode)."""
        self.display_message(f"Prompt: {prompt}", AnsiColors.USER)

    # --- Placeholder for future help command ---
    # def display_help(self, commands: list[str]):
    #     """Displays help information."""
    #     self.display_info("Available commands:")
    #     for cmd in commands:
    #         self.display_info(f"  {cmd}")
    #     self.display_info("Enter a prompt or @mention files to interact with the AI.")
