"""Events that App modules can send to UI for rendering.

Should also specify how to render the event.
"""

from rich.console import Console

from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer

# skipping a bunch of checks here due to redundancy
# ruff: noqa: ANN204,D101,D103,D107,E701


class _Str(str):
    __slots__ = ()


class Error(_Str):
    pass


@register_renderer
def render_error(event: Error, console: Console) -> None:
    console.print(event, style=Styles.RICH_ERROR)


class Warn(_Str):
    pass


@register_renderer
def render_warn(event: Warn, console: Console) -> None:
    console.print(event, style=Styles.RICH_WARNING)


class Info(_Str):
    pass


@register_renderer
def render_info(event: Info, console: Console) -> None:
    console.print(event, style=Styles.RICH_INFO)


_PROMPT = "You:"


class UserInput(_Str):
    pass


@register_renderer
def render_user_input(event: UserInput, console: Console) -> None:
    console.print(f"{_PROMPT} {event}", style=Styles.RICH_PROMPT)
