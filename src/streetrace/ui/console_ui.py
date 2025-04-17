# app/console_ui.py
import os

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from streetrace.llm.wrapper import ContentPartToolCall, ToolCallResult
from streetrace.ui.colors import Styles

_PROMPT = "You:"


class ConsoleUI:
    """
    Handles all console input and output for the StreetRace application.

    Encapsulates print statements and ANSI color codes for consistent UI.
    """

    cursor_is_in_line: bool = False

    def __init__(self, debug_enabled: bool = False):
        """
        Initializes the ConsoleUI.

        Args:
            debug_enabled: If True, enables printing of debug messages.
        """
        self.debug_enabled = debug_enabled
        self.console = Console()
        self.prompt_session = PromptSession(multiline=True)

    def _splitter(self, splitter_char: str = "━") -> str:
        """
        Returns a string used to separate different sections of output.
        """
        return splitter_char * os.get_terminal_size().columns

    def _title(self, title: str) -> str:
        """
        Returns a string used to separate different sections of output.
        """
        return f"  {title}  \n{self._splitter('═')}"

    def status(self, message: str):
        return self.console.status(message, spinner="hamburger")

    def prompt(self, prompt: str = _PROMPT) -> str:
        """
        Gets input from the user via the console.

        Args:
            prompt: The prompt string to display to the user.

        Returns:
            The string entered by the user.
        """
        # Use Styles for the prompt string itself
        with patch_stdout():
            return self.prompt_session.prompt(
                [
                    ("class:prompt", prompt),
                    ("", " "),
                ],
                style=Styles.PT,
            )

    def display_system_message(self, message: str):
        """
        Displays an informational message to the console.

        Args:
            message: The message string to display.
            color: The Styles code to use for the message. Defaults to INFO.
        """
        self.new_line()
        self.console.print(
            Panel("System instructions"),
            style=Styles.RICH_HISTORY_SYSTEM_INSTRUCTIONS_HEADER,
        )
        self.console.print(message, style=Styles.RICH_HISTORY_SYSTEM_INSTRUCTIONS)

    def display_context_message(self, message: str):
        """
        Displays an informational message to the console.

        Args:
            message: The message string to display.
            color: The Styles code to use for the message. Defaults to INFO.
        """
        self.new_line()
        self.console.print(Panel("Context"), style=Styles.RICH_HISTORY_CONTEXT_HEADER)
        self.console.print(message, style=Styles.RICH_HISTORY_CONTEXT)

    def display_history_assistant_message(self, message: str):
        """
        Displays an informational message to the console.

        Args:
            message: The message string to display.
            color: The Styles code to use for the message. Defaults to INFO.
        """
        self.new_line()
        self.console.print("Assistant:", style=Styles.RICH_HISTORY_ASSISTANT_HEADER)
        self.console.print(message, style=Styles.RICH_HISTORY_ASSISTANT)

    def display_history_user_message(self, message: str):
        """
        Displays an informational message to the console.

        Args:
            message: The message string to display.
            color: The Styles code to use for the message. Defaults to INFO.
        """
        self.new_line()
        self.console.print("User:", style=Styles.RICH_HISTORY_USER_HEADER)
        self.console.print(message, style=Styles.RICH_HISTORY_USER)

    def display_info(self, message: str):
        """Displays a standard informational message."""
        self.new_line()
        self.console.print(message, style=Styles.RICH_INFO)

    def display_warning(self, message: str):
        """Displays a warning message."""
        self.new_line()
        self.console.print(message, style=Styles.RICH_WARNING)

    def display_error(self, message: str):
        """Displays an error message."""
        self.new_line()
        self.console.print(message, style=Styles.RICH_ERROR)

    def display_ai_response_chunk(self, chunk: str):
        """
        Displays a chunk of the AI's response, typically used for streaming.
        Prints directly without extra formatting or newlines.
        """
        self.console.print(Markdown(chunk), style=Styles.RICH_MODEL, end="")
        self.cursor_is_in_line = True

    def new_line(self):
        if self.cursor_is_in_line:
            self.console.print()
            self.cursor_is_in_line = False

    def display_tool_call(self, tool_call: ContentPartToolCall):
        """Displays information about a tool being called."""
        display_args = {
            k: v if len(str(v)) < 30 else str(v)[:20] + f"... ({len(str(v))})"
            for k, v in tool_call.arguments.items()
        }
        message = f"{tool_call.name}({str(display_args)})"
        syntax = Syntax(message, "coffee", theme=Styles.RICH_TOOL_CALL)
        self.new_line()
        self.console.print(syntax)

    def display_tool_result(self, result: ToolCallResult):
        """Displays the result of a tool execution."""
        # Shorten long results for display
        content = result.display_output or result.output
        self.new_line()
        if content.type == "diff":
            syntax = Syntax(content.content, "diff", theme=Styles.RICH_DIFF)
            self.console.print(syntax)
        else:
            self.console.print(content.content, style=Styles.RICH_TOOL)

    def display_tool_error(self, result: ToolCallResult):
        """Displays the result of a tool execution."""
        content = result.display_output or result.output
        # Shorten long results for display
        self.new_line()
        self.console.print(content.content, style=Styles.RICH_ERROR)

    def display_user_prompt(self, message: str):
        """Displays the user's prompt (e.g., in non-interactive mode)."""
        self.new_line()
        self.console.print(f"{_PROMPT} {message}", style=Styles.RICH_PROMPT)

    # --- Placeholder for future help command ---
    # def display_help(self, commands: list[str]):
    #     """Displays help information."""
    #     self.display_info("Available commands:")
    #     for cmd in commands:
    #         self.display_info(f"  {cmd}")
    #     self.display_info("Enter a prompt or @mention files to interact with the AI.")
