"""Events that App modules can send to UI for rendering.

Should also specify how to render the event.
"""

from typing import TYPE_CHECKING

from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer

if TYPE_CHECKING:
    from rich.console import Console

# skipping a bunch of checks here due to redundancy
# ruff: noqa: D101, D103


class _Str(str):
    __slots__ = ()


class Error(_Str):
    pass


@register_renderer
def render_error(obj: Error, console: "Console") -> None:
    console.print(obj, style=Styles.RICH_ERROR)


class Warn(_Str):
    pass


@register_renderer
def render_warn(obj: Warn, console: "Console") -> None:
    console.print(obj, style=Styles.RICH_WARNING)


class Info(_Str):
    pass


@register_renderer
def render_info(obj: Info, console: "Console") -> None:
    console.print(obj, style=Styles.RICH_INFO)


class Markdown(_Str):
    pass


@register_renderer
def render_markdown(obj: Markdown, console: "Console") -> None:
    from rich.markdown import Markdown as RichMarkdown

    console.print(RichMarkdown(obj), style=Styles.RICH_INFO)


_PROMPT = "> "


class UserInput(_Str):
    pass


@register_renderer
def render_user_input(obj: UserInput, console: "Console") -> None:
    console.print(f"{_PROMPT} {obj}", style=Styles.RICH_PROMPT)
    console.print()  # Add blank line for visual separation
