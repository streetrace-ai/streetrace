"""Rendering wrapper for google.adk.events.Event."""

from typing import Any

from google.adk.events import Event
from google.genai.types import FunctionCall
from mcp.types import CallToolResult
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax

from streetrace.log import get_logger
from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer

logger = get_logger(__name__)


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
    author: str,
    text: str,
    is_final_response: bool,  # noqa: FBT001
    console: Console,
) -> None:
    style = Styles.RICH_INFO
    if is_final_response:
        style = Styles.RICH_MODEL

    logger.info(
        "%sAssistant message: %s",
        ("Final " if is_final_response else ""),
        text,
    )

    console.print(
        author,
        Markdown(text, inline_code_theme=Styles.RICH_MD_CODE),
        style=style,
        end=" ",
    )


def _display_function_call(
    author: str,
    function_call: FunctionCall,
    console: Console,
) -> None:
    logger.info("Function call: `%s(%s)`", function_call.name, function_call.args)
    console.print(
        author,
        Syntax(
            code=f"{function_call.name}({function_call.args})",
            lexer="python",
            theme=Styles.RICH_TOOL_CALL,
            line_numbers=False,
            background_color="default",
        ),
        end=" ",
    )


def _display_function_response(response: dict[str, Any], console: Console) -> None:
    display_dict = response
    if len(display_dict) == 1:
        val = next(iter(display_dict.values()))
        if isinstance(val, CallToolResult):
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
    console.print(
        Syntax(
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
        ),
    )


@register_renderer
def render_event(obj: Event, console: Console) -> None:
    """Render the provided google.adk.events.Event to rich.console."""
    author = f"[bold]{obj.author}:[/bold]\n"
    if obj.is_final_response() and obj.actions and obj.actions.escalate:
        # Handle potential errors/escalations
        console.print(
            author,
            f"Agent escalated: {obj.error_message or 'No specific message.'}",
            style=Styles.RICH_ERROR,
        )
    if obj.content and obj.content.parts:
        for part in obj.content.parts:
            if part.text:
                _display_assistant_text(
                    author,
                    part.text,
                    obj.is_final_response(),
                    console,
                )

            if part.function_call:
                _display_function_call(author, part.function_call, console)

            if part.function_response and part.function_response.response:
                _display_function_response(part.function_response.response, console)
