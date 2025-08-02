"""Object to Rich Console rendering protocol."""

from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from rich.console import Console

T_Protocol_contra = TypeVar("T_Protocol_contra", contravariant=True)


@runtime_checkable
class RendererFn(Protocol[T_Protocol_contra]):
    """Protocol to render T_RenderedType_contra to Rich Console."""

    def __call__(self, obj: T_Protocol_contra, console: "Console") -> None:
        """Protocol to render an object type to console."""
        ...


_display_renderers_registry: dict[type, RendererFn[Any]] = {}


def register_renderer[T_Protocol_contra](
    protocol: RendererFn[T_Protocol_contra],
) -> RendererFn[T_Protocol_contra]:
    """Add a renderer to registry so it can be used in ConsoleUI."""
    if not isinstance(protocol, RendererFn):
        msg = (
            f"Function {protocol.__name__}({protocol.__annotations__}) does not "
            "conform to RendererFn protocol."
        )
        raise TypeError(msg)
    target_object_type = next(
        iter(protocol.__annotations__.values()),
    )  # first argument's type
    _display_renderers_registry[target_object_type] = protocol
    return protocol


def render_using_registered_renderer(
    obj: object,
    console: "Console",
) -> None:
    """Render the provided object using a registered renderer."""
    renderer = _display_renderers_registry.get(type(obj))
    if not renderer:
        msg = (
            f"Renderer for {type(obj)} is not registered, please register with "
            "@register_renderer"
        )
        raise ValueError(msg)
    renderer(obj, console)
