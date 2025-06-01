"""A simple UI event loop decoupling bus.

The goal is to remove coupling between UI and the App logic.

We do this by implementing a simple PubSub - any component can Pub,
and any component can Sub, to any type of the events. Every event is
published to all who subscrbed to that type of event.

Rendering in the UI is implemented using RendererFn protocol. Any type can be
sent to UI via the bus so long as there is a registered RendererFn that can render
that type.

Alternatives considered:

There are multiple ways to achieve decoupling in UI updates. For now we are going with
a simple UI update bus. We don't need complex state management, as the other components
seem to be ok bening coupled via DI (this may change in the future).

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

from streetrace.costs import UsageAndCost
from streetrace.log import get_logger

logger = get_logger(__name__)

_UI_UPDATE_EVENT = "ui_update_event"
_TYPING_PROMPT_EVENT = "typing_prompt_event"
_PROMPT_TOKEN_COUNT_ESTIMATE_EVENT = "prompt_token_count_estimate_event"  # noqa: S105  # nosec B105
_USAGE_DATA_EVENT = "usage_data"


class UiBus:
    """UI event bus that helps exchange messages between UI and App logic."""

    _publisher: Publisher

    def __init__(self) -> None:
        """Initialize a new instance of UiBus with a separate pubsub Publisher."""
        self._publisher = Publisher()

    def dispatch_ui_update(self, event: Any) -> None:  # noqa: ANN401
        """Send a new renderable to the UI.

        Args:
            event: An instance of a type that has a registered RendererFn protocol.

        """
        self._publisher.sendMessage(_UI_UPDATE_EVENT, obj=event)

    def on_ui_update_requested(self, listener: Callable[[Any], None]) -> None:
        """Subscribe to UI update requests.

        The listener must be sync.

        Typically, ConsoleUI will subscribe to all UI update requests
        and fulfill them.

        Args:
            listener: A listener method to receive all UI updates.

        """
        self._publisher.subscribe(listener, _UI_UPDATE_EVENT)

    def dispatch_typing_prompt(self, prompt: str) -> None:
        """Inform subscribers of a prompt being typed.

        ConsoleUI sends these updates when the user is typing a prompt.

        Args:
            prompt: Currently typed prompt.

        """
        self._publisher.sendMessage(_TYPING_PROMPT_EVENT, prompt=prompt)

    def on_typing_prompt(self, listener: Callable[[str], None]) -> None:
        """Subscribe to prompt typing events.

        The listener must be sync.

        LlmInterface will subscribe to prompt updates to calculate estimated
        token count of the prompt (and issue an rprompt update request).

        Args:
            listener: A Callable[[str],...] listener to receive prompt typing events.

        """
        self._publisher.subscribe(listener, _TYPING_PROMPT_EVENT)

    def dispatch_prompt_token_count_estimate(self, token_count: int) -> None:
        """Send an estimated currently typed prompt token count update.

        Typically, LlmInterface will issue update requests to show
        estimated token count in the prompt being typed.

        Args:
            token_count: Updated prompt token count.

        """
        self._publisher.sendMessage(
            _PROMPT_TOKEN_COUNT_ESTIMATE_EVENT,
            token_count=token_count,
        )

    def on_prompt_token_count_estimate(self, listener: Callable[[int], None]) -> None:
        """Subscribe to prompt token count updates.

        The listener must be sync.

        Typically, ConsoleUI will subscribe to update requests
        and update the prompt session rprompt.

        Args:
            listener: A Callable[[int],...] listener to receive rprompt update requests.

        """
        self._publisher.subscribe(listener, _PROMPT_TOKEN_COUNT_ESTIMATE_EVENT)

    def dispatch_usage_data(self, usage: UsageAndCost) -> None:
        """Send usage data stats update.

        Typically, LlmInterface will issue update requests based on LiteLLM's
        completion_cost.

        Args:
            usage: Usage data.

        """
        self._publisher.sendMessage(
            _USAGE_DATA_EVENT,
            usage=usage,
        )

    def on_usage_data(self, listener: Callable[[UsageAndCost], None]) -> None:
        """Subscribe to prompt token count updates.

        The listener must be sync.

        Typically, ConsoleUI will subscribe to update requests
        and update the prompt session rprompt.

        Args:
            listener: A Callable[[int],...] listener to receive rprompt update requests.

        """
        self._publisher.subscribe(listener, _USAGE_DATA_EVENT)
