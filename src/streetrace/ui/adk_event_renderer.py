"""Rendering wrapper for google.adk.events.Event."""

from google.adk.events import Event
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax

from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer


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
        lines = lines[: max_lines - 1] + [
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
                style = Styles.RICH_INFO
                if obj.is_final_response():
                    style = Styles.RICH_MODEL

                console.print(
                    author,
                    Markdown(part.text, inline_code_theme=Styles.RICH_MD_CODE),
                    style=style,
                    end=" ",
                )

            if part.function_call:
                fn = part.function_call
                console.print(
                    author,
                    Syntax(
                        code=f"{fn.name}({fn.args})",
                        lexer="python",
                        theme=Styles.RICH_TOOL_CALL,
                        line_numbers=False,
                        background_color="default",
                    ),
                    end=" ",
                )

            if part.function_response:
                fn = part.function_response
                if fn.response:
                    console.print(
                        Syntax(
                            code="\n".join(
                                [
                                    f"  ↳ {key}: {_trim_text(str(fn.response[key]))}"
                                    for key in fn.response
                                ],
                            ),
                            lexer="python",
                            theme=Styles.RICH_TOOL_CALL,
                            line_numbers=False,
                            background_color="default",
                        ),
                    )
