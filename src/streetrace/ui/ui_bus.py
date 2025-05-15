"""A simple UI event loop decoupling bus.

The goal is to remove coupling between UI and the App logic.

We do this by implementing a simple PubSub - any component can Pub,
and any component can Sub, to any type of the events. Every event is
published to all who subscrbed to that type of event.

Rendering in the UI is implemented using RendererFn protocol. Any type can be
sent to UI via the bus so long as there is a registered RendererFn that can render
that type.

Alternatives considered:

There are multiple ways to achieve that. For now we are going with
a simple UI update bus. We don't need State otherwise, as the other components
seem to be ok bening coupled via DI (this may change in the future).

The other reason I don't want to itroduce state is that it provides either
a complexity on the consumers' side (RxPY), or strongly typed state object (observables).

## Built-in Python Options

1. Observable Pattern with Python's Built-ins:
   * Use Python's built-in dataclasses with custom notification methods
   * Implement observer pattern using Python's event system
2. Custom Event System:
   * Python's threading.Event for basic signaling
   * asyncio.Event for async applications
3. RxPy (Reactive Extensions for Python):
   * Comprehensive reactive programming library
   * Allows composable event streams with observables
   * Great for complex event flows and transformations
   * PyPI: RxPy
4. Blinker:
   * Fast, simple object signaling library
   * Used by Flask and other frameworks
   * PyPI: Blinker
5. Redux-inspired State Management:
   * Pyrsistent for immutable data structures
   * python-redux for Redux pattern implementation
"""

from collections.abc import Callable
from typing import Any

from pubsub.core import Publisher

#TODO(krmrn42): Implement waiting for user input (confirm, prompt)

_UI_UPDATE_EVENT = "UI_UPDATE_EVENT"

class UiBus:
    """UI event bus that helps exchange messages between UI and App logic."""

    _publisher: Publisher

    def __init__(self) -> None:
        """Initialize a new instance of UiBus with a separate pubsub Publisher."""
        self._publisher = Publisher()

    def dispatch(self, event: Any) -> None:  # noqa: ANN401
        """Send a new renderable to the UI.

        Args:
            event: An instance of a type that has a registered RendererFn protocol.

        """
        self._publisher.sendMessage(_UI_UPDATE_EVENT, obj=event)


    def subscribe(self, listener: Callable[..., None]) -> None:
        """Subscribe to UI bus events.

        Args:
            listener: A listener method to receive all UI updates.

        """
        self._publisher.subscribe(listener, _UI_UPDATE_EVENT)
