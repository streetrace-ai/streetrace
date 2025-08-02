"""Console UI."""

from types import TracebackType
from typing import TYPE_CHECKING, Any

from prompt_toolkit import HTML, PromptSession
from prompt_toolkit.completion import Completer  # Base class
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.validation import Validator
from rich.console import Console

from streetrace.app_state import AppState
from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import render_using_registered_renderer
from streetrace.ui.ui_bus import UiBus

if TYPE_CHECKING:
    from rich.status import Status

_PROMPT = "> "

_TOOLBAR_TEMPLATE = (
    "<highlight>{current_model}</highlight> | "
    "usage: <highlight>{usage_and_cost.app_run_usage.prompt_tokens_str}</highlight>in/"
    "<highlight>{usage_and_cost.app_run_usage.completion_tokens_str}</highlight>out, "
    "<highlight>${usage_and_cost.app_run_usage.cost_str}</highlight> | "
    "Send: Enter | New line: Alt+Enter | Hints: @ Tab / | Exit: Ctrl+C"
)
_STATUS_MESSAGE_TEMPLATE = (
    "{current_model} Working... {usage_and_cost.turn_usage.prompt_tokens_str}in:"
    "{usage_and_cost.turn_usage.completion_tokens_str}out, "
    "${usage_and_cost.turn_usage.cost_str}"
)


def _format_app_state_str(template: str, app_state: AppState) -> str:
    return template.format(
        current_model=app_state.current_model,
        usage_and_cost=app_state.usage_and_cost,
    )


class StatusSpinner:
    """Console Status, encapsulates rich.status."""

    _ICON = "hamburger"
    _EMPTY_MESSAGE = "Working..."

    def __init__(self, app_state: AppState, console: Console) -> None:
        """Initialize the instance and instantiate rich.status.

        Args:
            app_state: App State container.
            console: The console instance to attach the spinner to.

        """
        self.app_state = app_state
        self.console = console
        self._status: Status | None = None

    def update_state(self) -> None:
        """Update status message."""
        if self._status:
            self._status.update(
                _format_app_state_str(_STATUS_MESSAGE_TEMPLATE, self.app_state),
            )

    def __enter__(self) -> "StatusSpinner":
        """Enter the context by starting the spinner.

        Returns:
            self, so that logging methods can be called within the context.

        """
        self._status = self.console.status(
            status=StatusSpinner._EMPTY_MESSAGE,
            spinner=StatusSpinner._ICON,
        ).__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the context by propagating the signal to the spinner.

        Args:
            exc_type: The type of exception raised (if any).
            exc_value: The exception instance (if any).
            traceback: The traceback object (if any).

        """
        if self._status:
            self._status.__exit__(exc_type, exc_value, traceback)
            self._status = None


class ConsoleUI:
    """Handles all console input and output for the StreetRace application.

    Encapsulates print statements and ANSI color codes for consistent UI.
    Leverages a completer for interactive input suggestions.
    """

    def __init__(
        self,
        app_state: AppState,
        completer: Completer,
        ui_bus: UiBus,
    ) -> None:
        """Initialize the ConsoleUI.

        Args:
            app_state: App State container.
            completer: An instance of a prompt_toolkit Completer implementation.
            ui_bus: UI event bus to exchange messages with the UI.

        """
        self.app_state = app_state
        self.console = Console()
        self.completer = completer  # Use the generic completer instance

        # Create custom key bindings for intuitive Enter behavior
        kb = KeyBindings()

        @kb.add("escape", "enter")  # Alt+Enter fallback (works everywhere)
        def _(event: KeyPressEvent) -> None:
            """Insert newline on Alt+Enter (universal fallback)."""
            event.current_buffer.insert_text("\n")

        @kb.add("enter")  # Plain Enter submits
        def _(event: KeyPressEvent) -> None:
            """Submit input on plain Enter."""
            event.current_buffer.validate_and_handle()

        self.prompt_session: PromptSession[Any] = PromptSession(
            completer=self.completer,  # Pass the completer here
            complete_while_typing=True,  # Suggest completions proactively
            multiline=True,  # Keep buffer capable of real newlines
            key_bindings=kb,  # Custom key bindings for Enter behavior
        )
        self.ui_bus = ui_bus
        self.spinner: StatusSpinner | None = None  # Initialize spinner attribute

        ui_bus.on_ui_update_requested(self.display)
        ui_bus.on_prompt_token_count_estimate(self._update_rprompt)

    def display(self, obj: Any) -> None:  # noqa: ANN401
        """Display an object using a known renderer."""
        render_using_registered_renderer(obj, self.console)

    def status(self) -> StatusSpinner:
        """Display a status message using rich.console.status."""
        self.spinner = StatusSpinner(self.app_state, self.console)
        return self.spinner

    def update_state(self) -> None:
        """Update status message."""
        if self.spinner:
            self.spinner.update_state()

    def _update_rprompt(self, token_count: int | None) -> None:
        if token_count is None:
            self.prompt_session.rprompt = None
        else:
            self.prompt_session.rprompt = f"~{token_count}t"

    async def prompt_async(self, prompt_str: str = _PROMPT) -> str:
        """Get input from the user via the console with autocompletion.

        Args:
            prompt_str: The prompt string to display to the user.

        Returns:
            The string entered by the user.

        """
        from prompt_toolkit.styles import Style

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
            _2: int,
        ) -> StyleAndTextTuples:
            # Defines appearance for continuation lines in multiline mode
            # Simple dots for now, could be more elaborate
            return [
                ("class:prompt-continuation", " " * width),  # Style in Styles.PT
            ]

        def build_bottom_toolbar() -> HTML:
            return HTML(
                _format_app_state_str(_TOOLBAR_TEMPLATE, self.app_state),
            )

        def send_is_typing(text: str) -> bool:
            self.ui_bus.dispatch_typing_prompt(text)
            return True

        # --- End prompt_toolkit setup ---

        # patch_stdout ensures that prints from other threads don't interfere
        # with the prompt rendering.
        try:
            with patch_stdout():
                self.console.print()
                user_input = await self.prompt_session.prompt_async(
                    build_prompt,
                    style=Style.from_dict(Styles.PT_ANSI),
                    prompt_continuation=build_prompt_continuation,
                    bottom_toolbar=build_bottom_toolbar,
                    validator=Validator.from_callable(send_is_typing),
                    placeholder=[("class:placeholder", "Enter your prompt")],
                    # completer and complete_while_typing are set in __init__
                )
                self.console.print()
        except EOFError:  # Handle Ctrl+D as a way to exit
            return "/exit"  # Consistent exit command
        except KeyboardInterrupt as kb_interrupt:  # Handle Ctrl+C
            if self.prompt_session.app.current_buffer.text:
                self.prompt_session.app.current_buffer.reset()
                raise

            raise SystemExit from kb_interrupt
        else:
            return str(user_input)
        finally:
            self._update_rprompt(None)

    def confirm_with_user(self, message: str) -> str:
        """Ask the user to type something and return the typed string."""
        return self.console.input(f"[green]{message}[/green]").strip()
