"""Events that App modules can send to UI for rendering.

Should also specify how to render the event.
"""

from rich.console import Console
from rich.markdown import Markdown as RichMarkdown

from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer

# skipping a bunch of checks here due to redundancy
# ruff: noqa: ANN204,D101,D103,D107,E701


class _Str(str):
    __slots__ = ()


class Error(_Str):
    pass


@register_renderer
def render_error(obj: Error, console: Console) -> None:
    console.print(obj, style=Styles.RICH_ERROR)


class Warn(_Str):
    pass


@register_renderer
def render_warn(obj: Warn, console: Console) -> None:
    console.print(obj, style=Styles.RICH_WARNING)


class Info(_Str):
    pass


@register_renderer
def render_info(obj: Info, console: Console) -> None:
    console.print(obj, style=Styles.RICH_INFO)


class Markdown(_Str):
    pass


@register_renderer
def render_markdown(obj: Markdown, console: Console) -> None:
    console.print(RichMarkdown(obj), style=Styles.RICH_INFO)


_PROMPT = "You:"


class UserInput(_Str):
    pass


@register_renderer
def render_user_input(obj: UserInput, console: Console) -> None:
    console.print(f"{_PROMPT} {obj}", style=Styles.RICH_PROMPT)
