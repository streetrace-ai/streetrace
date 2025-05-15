"""Console UI."""

from typing import Any

from prompt_toolkit import HTML, PromptSession
from prompt_toolkit.completion import Completer  # Base class
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.status import Status

from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import render_using_registered_renderer

_PROMPT = "You:"

class ConsoleUI:
    """Handles all console input and output for the StreetRace application.

    Encapsulates print statements and ANSI color codes for consistent UI.
    Leverages a completer for interactive input suggestions.
    """

    cursor_is_in_line: bool = False

    def __init__(self, completer: Completer) -> None:
        """Initialize the ConsoleUI.

        Args:
            completer: An instance of a prompt_toolkit Completer implementation.

        """
        self.console = Console()
        self.completer = completer  # Use the generic completer instance
        # Enable multiline input, potentially useful for longer prompts or pasted code
        self.prompt_session = PromptSession(
            completer=self.completer,  # Pass the completer here
            complete_while_typing=True,  # Suggest completions proactively
            multiline=True,  # Allow multiline input with Esc+Enter
        )

    def display(self, obj: Any) -> None:  # noqa: ANN401
        """Display an object using a known renderer."""
        render_using_registered_renderer(obj, self.console)

    def status(self, message: str) -> Status:
        """Display a status message using rich.console.status."""
        return self.console.status(message, spinner="hamburger")

    async def prompt_async(self, prompt_str: str = _PROMPT) -> str:
        """Get input from the user via the console with autocompletion.

        Args:
            prompt_str: The prompt string to display to the user.

        Returns:
            The string entered by the user.

        """

        # --- prompt_toolkit setup ---
        def build_prompt() -> list[tuple[str, str]]:
            # Defines the main prompt appearance
            return [
                ("class:prompt", prompt_str),  # Style defined in Styles.PT
                ("", " "),  # Space after prompt
            ]

        def build_prompt_continuation(
            width: int,
            _1: int,
            _2: bool,  # noqa: FBT001
        ) -> list[tuple[str, str]]:
            # Defines appearance for continuation lines in multiline mode
            # Simple dots for now, could be more elaborate
            return [
                ("class:prompt-continuation", "." * width),  # Style in Styles.PT
            ]

        def build_bottom_toolbar() -> list[tuple[str, str]]:
            # Help text at the bottom
            current_model = "some model"
            input_tokens = "123"
            output_tokens = "456"
            cost = "123.00"
            return HTML(
                f"Model <highlight>{current_model}</highlight> | "
                f"tokens: <highlight>{input_tokens}</highlight>/<highlight>{output_tokens}</highlight>, <highlight>${cost}</highlight> | "
                f"New Line: Enter | Send: Esc,Enter | "
                f"Autocomplete: @ Tab / | Exit: /bye,Ctrl+C",
            )

        # --- End prompt_toolkit setup ---

        # patch_stdout ensures that prints from other threads don't interfere
        # with the prompt rendering.
        try:
            with patch_stdout():
                user_input = await self.prompt_session.prompt_async(
                    build_prompt,  # Use the function to build the prompt dynamically if needed
                    style=Styles.PT_ANSI,  # Apply the custom style map
                    prompt_continuation=build_prompt_continuation,
                    bottom_toolbar=build_bottom_toolbar,
                    # completer and complete_while_typing are set in __init__
                )
        except EOFError:  # Handle Ctrl+D as a way to exit
            return "/exit"  # Consistent exit command
        except KeyboardInterrupt as kb_interrupt:  # Handle Ctrl+C
            if self.prompt_session.app.current_buffer.text:
                self.prompt_session.app.current_buffer.reset()
                raise

            raise SystemExit from kb_interrupt
        else:
            self.cursor_is_in_line = False  # Prompt resets cursor position
            return user_input

    def confirm_with_user(self, message: str) -> str:
        """Ask the user to type something and return the typed string."""
        return self.console.input(f"[green]{message}[/green]").strip()

    #TODO(krmrn42): fix tests
    def display_info(self, message: str) -> None:
        """Display a standard informational message."""
        self.console.print(message, style=Styles.RICH_INFO)

    def display_warning(self, message: str) -> None:
        """Display a warning message."""
        self.console.print(message, style=Styles.RICH_WARNING)

    def display_error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(message, style=Styles.RICH_ERROR)
