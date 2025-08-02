"""Chain-of-Responsibility pattern for handling user input."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import NamedTuple


class HandlerResult(NamedTuple):
    """Result of input handler."""

    handled: bool
    continue_: bool


HANDLED_STOP = HandlerResult(handled=True, continue_=False)
"""Processing completed, stop pipeline."""
HANDLED_CONT = HandlerResult(handled=True, continue_=True)
"""Input was processed, but the pipeline should continue."""
SKIP = HandlerResult(handled=False, continue_=True)
"""Input was not processed, so the pipeline should continue."""


@dataclass
class InputContext:
    """State of input handler."""

    user_input: str | None = None
    bash_output: str | None = None
    enrich_input: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    agent_name: str | None = None

    def __iter__(self) -> Iterator[str]:
        """Iterate over the input context."""
        if self.user_input:
            yield self.user_input
        if self.bash_output:
            yield self.bash_output
        for k, v in self.enrich_input.items():
            sep = "\n\n===\n\n"
            yield f"{sep}Attached file `{k!s}`:\n\n{v}{sep}"
        if self.error:
            yield self.error


class InputHandler(ABC):
    """Base handler for Chain-of-Responsibility."""

    long_running: bool = False
    """Whether the handler is long running."""

    @abstractmethod
    async def handle(
        self,
        ctx: InputContext,
    ) -> HandlerResult:
        """Handle user input.

        Args:
            ctx: User input processing context.

        Returns:
            HandlerResult indicating handing result.

        """
