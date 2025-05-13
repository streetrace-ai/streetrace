"""Object to Rich Console rendering protocol."""

from typing import Generic, Protocol, TypeVar, runtime_checkable

from rich.console import Console

T_RenderedType = TypeVar("T_RenderedType")


@runtime_checkable
class RendererFn(Protocol, Generic[T_RenderedType]):
    """Object to Rich Console rendering protocol."""

    def __call__(self, obj: T_RenderedType, console: Console) -> str:
        """Protocol to render a T_RenderedType instance to console."""
        ...


_display_renderers_registry: dict[type, RendererFn] = {}


def register_renderer(fn: RendererFn) -> RendererFn:
    """Add a renderer to registry so it can be used in ConsoleUI."""
    if not isinstance(fn, RendererFn):
        msg = f" Function {fn.__name__}({fn.__annotations__}) does not conform to RendererFn protocol."
        raise TypeError(msg)
    target_object_type = next(
        iter(fn.__annotations__.values()),
    )  # first argument's type
    _display_renderers_registry[target_object_type] = fn
    return fn


def render_using_registered_renderer(obj: T_RenderedType, console: Console) -> None:
    """Render the provided object using a registered renderer."""
    renderer = _display_renderers_registry.get(type(obj))
    if not renderer:
        msg = f"Renderer for {type(obj)} is not registered, please register with @register_renderer"
        raise ValueError(msg)
    renderer(obj, console)
