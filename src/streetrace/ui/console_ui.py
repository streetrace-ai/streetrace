"""Console UI."""

from typing import Any

import litellm
from prompt_toolkit import HTML, PromptSession
from prompt_toolkit.completion import Completer  # Base class
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.syntax import Syntax

from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import render_using_registered_renderer

_PROMPT = "You:"
_MAX_LONG_LINE_LENGTH = 100  # Maximum length for a single line of output


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

    # --- Display methods remain largely the same ---

    def display_system_message(self, message: str) -> None:
        """Display an informational message to the console.

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

    def display_context_message(self, message: str) -> None:
        """Display an informational message to the console.

        Args:
            message: The message string to display.
            color: The Styles code to use for the message. Defaults to INFO.

        """
        self.new_line()
        self.console.print(Panel("Context"), style=Styles.RICH_HISTORY_CONTEXT_HEADER)
        self.console.print(message, style=Styles.RICH_HISTORY_CONTEXT)

    def display_history_assistant_message(self, message: str) -> None:
        """Display an informational message to the console.

        Args:
            message: The message string to display.
            color: The Styles code to use for the message. Defaults to INFO.

        """
        self.new_line()
        self.console.print("Assistant:", style=Styles.RICH_HISTORY_ASSISTANT_HEADER)
        self.console.print(message, style=Styles.RICH_HISTORY_ASSISTANT)

    def display_history_user_message(self, message: str) -> None:
        """Display an informational message to the console.

        Args:
            message: The message string to display.
            color: The Styles code to use for the message. Defaults to INFO.

        """
        self.new_line()
        self.console.print("User:", style=Styles.RICH_HISTORY_USER_HEADER)
        self.console.print(message, style=Styles.RICH_HISTORY_USER)

    def display(self, obj: Any) -> None:  # noqa: ANN401
        """Display an object using a known renderer."""
        render_using_registered_renderer(obj, self.console)

    def display_info(self, message: str) -> None:
        """Display a standard informational message."""
        self.new_line()
        self.console.print(message, style=Styles.RICH_INFO)

    def display_warning(self, message: str) -> None:
        """Display a warning message."""
        self.new_line()
        self.console.print(message, style=Styles.RICH_WARNING)

    def display_error(self, message: str) -> None:
        """Display an error message."""
        self.new_line()
        self.console.print(message, style=Styles.RICH_ERROR)

    def display_finish_reason(self, message: str) -> None:
        """Display a standard informational message."""
        self.display_info(message)

    def display_ai_response_chunk(self, chunk: str) -> None:
        """Display a chunk of the AI's response.

        Typically used for streaming.
        Prints directly without extra formatting or newlines.
        Handles Markdown rendering.
        """
        # Use Markdown for potentially formatted chunks
        # `inline_code_theme` can be customized if needed
        md = Markdown(chunk, inline_code_theme=Styles.RICH_MD_CODE)
        self.console.print(md, style=Styles.RICH_MODEL, end="")
        # if the chunk ends with a newline, we still miss one line break because
        # it's a ui-level newline, and the one in chunk is content-level newline.
        self.cursor_is_in_line = True

    def new_line(self) -> None:
        """Ensure the next print starts on a new line if needed."""
        if self.cursor_is_in_line:
            self.console.print()
            self.cursor_is_in_line = False

    def display_tool_call(
        self,
        tool_call: litellm.ChatCompletionMessageToolCall,
    ) -> None:
        """Display information about a tool being called."""
        # Shorten long arguments for display clarity
        display_args = {}
        if isinstance(tool_call.function.arguments, dict):
            for k, v in tool_call.function.arguments.items():
                # Convert value to string, handle potential errors
                try:
                    v_str = str(v)
                except (TypeError, ValueError):
                    v_str = "[Error converting arg to string]"

                if len(v_str) > _MAX_LONG_LINE_LENGTH:
                    display_args[k] = v_str[:90] + f"... ({len(v_str)} chars)"
                else:
                    display_args[k] = v_str  # Keep short args as is
        else:
            display_args = {
                "args": str(tool_call.function.arguments),
            }  # Handle non-dict args

        # Format arguments nicely
        try:
            args_str = ", ".join(f"{k}={v!r}" for k, v in display_args.items())
        except (TypeError, ValueError, KeyError):
            args_str = "[Error formatting args]"

        message = f"{tool_call.function.name}({args_str})"

        # Use Python syntax highlighting for the call representation
        syntax = Syntax(
            message,
            "python",
            theme=Styles.RICH_TOOL_CALL,
            line_numbers=False,
        )
        self.new_line()
        self.console.print(Panel(syntax, title="Tool Call"))
        self.cursor_is_in_line = False

    def display_user_prompt(self, message: str) -> None:
        """Display the user's prompt (e.g., in non-interactive mode)."""
        self.new_line()
        self.console.print(f"{_PROMPT} {message}", style=Styles.RICH_PROMPT)
        self.cursor_is_in_line = False  # Assume prompt display finishes the line

    def confirm_with_user(self, message: str) -> str:
        """Ask the user to type something and return the typed string."""
        return self.console.input(f"[green]{message}[/green]").strip()
