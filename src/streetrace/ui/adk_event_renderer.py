"""Rendering wrapper for google.adk.events.Event."""

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from streetrace.log import get_logger
from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer

if TYPE_CHECKING:
    from google.adk.events import Event as AdkEvent
    from google.genai.types import FunctionCall
    from rich.console import Console
    from rich.syntax import Syntax

logger = get_logger(__name__)


class EventRenderer:
    """Stateful renderer that groups function calls with their responses."""

    def __init__(self) -> None:
        """Initialize the event renderer."""
        self.pending_function_call: tuple[str, FunctionCall] | None = None

    def render_event(self, obj: "Event", console: "Console") -> None:
        """Render the provided google.adk.events.Event to rich.console."""
        from rich.panel import Panel

        author = f"[bold]{obj.event.author}:[/bold]"

        if (
            obj.event.is_final_response()
            and obj.event.actions
            and obj.event.actions.escalate
        ):
            # Handle potential errors/escalations
            console.print(
                author,
                f"Agent escalated: {obj.event.error_message or 'No specific message.'}",
                style=Styles.RICH_ERROR,
            )

        if obj.event.content and obj.event.content.parts:
            for part in obj.event.content.parts:
                if part.text:
                    # If we have a pending function call, render it first
                    self._flush_pending_function_call(console)

                    _display_assistant_text(
                        part.text,
                        obj.event.is_final_response(),
                        console,
                    )

                if part.function_call:
                    # Store function call for later grouping with response
                    self.pending_function_call = (author, part.function_call)

                if part.function_response and part.function_response.response:
                    # Group with pending function call if available
                    if self.pending_function_call:
                        self._render_function_call_group(
                            self.pending_function_call[1],
                            part.function_response.response,
                            console,
                        )
                        self.pending_function_call = None
                    else:
                        # Orphaned response - render standalone
                        console.print(
                            Panel(
                                _format_function_response(
                                    part.function_response.response,
                                ),
                                title="Function Response",
                                border_style="blue",
                            ),
                        )

        # Flush any remaining pending function call that wasn't paired with a response
        self._flush_pending_function_call(console)

    def _flush_pending_function_call(self, console: "Console") -> None:
        """Render any pending function call that hasn't been paired with a response."""
        from rich.panel import Panel

        if self.pending_function_call:
            author, function_call = self.pending_function_call
            console.print(
                Panel(
                    _format_function_call(function_call),
                    title=f"{author} Function Call",
                    border_style="yellow",
                ),
            )
            self.pending_function_call = None

    def _render_function_call_group(
        self,
        function_call: "FunctionCall",
        response: dict[str, Any],
        console: "Console",
    ) -> None:
        """Render function call and response together in a grouped panel."""
        from rich.panel import Panel

        call_content = _format_function_call(function_call)
        response_content = _format_function_response(response)

        # Create a group with call and response
        from rich.console import Group

        combined_content = Group(
            call_content,
            "",  # Empty line separator
            response_content,
        )

        console.print(
            Panel(
                combined_content,
                border_style="cyan",
            ),
        )


@dataclass
class Event:
    """Wrapper for ADK Event.

    This class is used to allow lazy-loading of ADK Event while having strict
    typing of the Event type.
    """

    event: "AdkEvent"


def _trim_text(text: str, max_length: int = 200, max_lines: int = 2) -> str:
    if text:
        text = text.strip()
    if not text:
        return text
    if max_lines == 0:
        return ""
    lines = text.splitlines()
    lines_count = len(lines)
    if lines_count > max_lines:
        lines = [
            *lines[: max_lines - 1],
            f"({lines_count - max_lines + 1} lines trimmed)...",
        ]
    trimmed_lines = []
    for line in lines:
        if len(line) > max_length:
            trimmed_lines.append(
                line[: max_length - 3] + "...",
            )
        else:
            trimmed_lines.append(line)
    return "\n".join(trimmed_lines)


def _display_assistant_text(
    text: str,
    is_final_response: bool,  # noqa: FBT001
    console: "Console",
) -> None:
    from rich.markdown import Markdown

    style = Styles.RICH_INFO
    if is_final_response:
        style = Styles.RICH_MODEL

    logger.info(
        "%sAssistant message: %s",
        ("Final " if is_final_response else ""),
        text,
    )

    console.print(
        Markdown(text, inline_code_theme=Styles.RICH_MD_CODE),
        style=style,
        end=" ",
    )


def _format_function_call(function_call: "FunctionCall") -> "Syntax":
    """Format function call for display."""
    logger.info("Function call: `%s(%s)`", function_call.name, function_call.args)
    from rich.syntax import Syntax

    return Syntax(
        code=f"{function_call.name}({function_call.args})",
        lexer="python",
        theme=Styles.RICH_TOOL_CALL,
        line_numbers=False,
        background_color="default",
    )


def _is_call_tool_result(value: object) -> bool:
    if value and "mcp.types" in sys.modules:
        return isinstance(value, sys.modules["mcp.types"].CallToolResult)
    return False


def _format_function_response(response: dict[str, Any]) -> "Syntax":
    """Format function response for display."""
    from rich.syntax import Syntax

    display_dict = response
    if len(display_dict) == 1:
        val = next(iter(display_dict.values()))
        if _is_call_tool_result(val):
            display_dict = val.model_dump()
        elif isinstance(val, dict):
            display_dict = val
    logger.info(
        "Function response:\n%s",
        "\n".join(
            [
                f"  ↳ {key}: {_trim_text(str(display_dict[key]))}"
                for key in display_dict
            ],
        ),
    )
    return Syntax(
        code="\n".join(
            [
                f"  ↳ {key}: {_trim_text(str(display_dict[key]))}"
                for key in display_dict
            ],
        ),
        lexer="python",
        theme=Styles.RICH_TOOL_CALL,
        line_numbers=False,
        background_color="default",
    )


# Global renderer instance to maintain state across events
_renderer_instance = EventRenderer()


@register_renderer
def render_event(obj: Event, console: "Console") -> None:
    """Render the provided google.adk.events.Event to rich.console."""
    _renderer_instance.render_event(obj, console)
