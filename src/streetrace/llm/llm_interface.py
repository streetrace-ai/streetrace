"""Provides a standardized interface for all LLM providers used by StreetRace🚗💨.

This module defines the common abstraction layer for interacting with language models
through the LlmInterface abstract class, with concrete implementations for specific
providers. It serves as the central point for creating LLM interfaces and handles
token estimation, API standardization, and provider-agnostic interactions.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, cast, override

if TYPE_CHECKING:
    from streetrace.llm.lite_llm_client import RetryingLiteLlm

from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

if TYPE_CHECKING:
    from google.adk.models.base_llm import BaseLlm
    from litellm.types.utils import ModelResponse

logger = get_logger(__name__)


class LlmInterface(ABC):
    """A generic LLM interface.

    Provides a way to call an LLM using StreetRace🚗💨 internal types for ease of use.

    StreetRace🚗💨 uses:
        streetrace.history.History for conversation history;
        list[dict] for tools;
        litellm.types.utils.ModelResponse for response.

    Ideally we should provide internal types for all of the above, but there is no
    value in it currently.

    """

    @abstractmethod
    def get_adk_llm(self) -> "BaseLlm":
        """Get the ADK LLM interface instance."""
        raise NotImplementedError

    @abstractmethod
    async def generate_async(
        self,
        messages: list[Any],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Call LLM interface's async generate method based on conversation history."""


class AdkLiteLlmInterface(LlmInterface):
    """LiteLLM interface for ADK using RetryingLiteLlm.

    This implementation uses the RetryingLiteLlm class which has built-in retry
    functionality for handling transient errors like rate limits and server errors.
    """

    def __init__(self, model: str, ui_bus: UiBus) -> None:
        """Initialize new AdkLiteLlmInterface for the given model.

        Args:
            model (str): Model names in format provider/model, or just model. See
                https://docs.litellm.ai/docs/set_keys.
            ui_bus: UI event bus to exchange messages with the UI.

        """
        from streetrace.llm.lite_llm_client import RetryingLiteLlm

        self.model = model
        self.llm_instance = RetryingLiteLlm(model=model, ui_bus=ui_bus)
        self.ui_bus = ui_bus
        # TODO(krmrn42): only the currently used model should estimate the token count
        ui_bus.on_typing_prompt(self.estimate_token_count)

    @override
    def get_adk_llm(self) -> "RetryingLiteLlm":
        """Get the internal LLM interface reference."""
        return self.llm_instance

    def estimate_token_count(
        self,
        prompt: str,
    ) -> None:
        """Estimate the number of tokens in the provided input.

        Override to provide a proper count estimation.
        """
        from litellm.utils import token_counter

        messages = [{"user": "role", "content": prompt}]
        estimated_token_count = token_counter(model=self.model, messages=messages)
        self.ui_bus.dispatch_prompt_token_count_estimate(estimated_token_count)

    # RetryingLiteLlm already handles the retry logic internally, so we don't need
    # the tenacity decorator here anymore
    @override
    async def generate_async(
        self,
        messages: list[Any],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate content for the provided messages using internal LiteLlm instance.

        Args:
            messages: List of messages accepted by LiteLLM, see
                https://github.com/search?q=repo%3ABerriAI%2Flitellm+path%3Alitellm%2Fmain.py+%22def+completion%28%22&type=code
            tools: tools in OpenAI format.

        """
        logger.debug("Calling LLM API...")
        # Since we're still using the same LiteLlm client under the hood,
        # we can use the same approach to call the LLM API but with RetryingLiteLlm
        # which will handle retries internally
        try:
            # Use the llm_client from RetryingLiteLlm to make the API call
            r = cast(
                "ModelResponse",
                await self.llm_instance.llm_client.acompletion(
                    model=self.llm_instance.model,
                    messages=messages,
                    stream=False,
                    tools=tools,
                    num_retries=0,  # Let RetryingLiteLlm handle retries
                ),
            )
            return r.model_dump()
        except Exception as e:
            # RetryingLiteLlm should handle retryable exceptions, so this should only
            # happen for non-retryable errors after all retry attempts have been
            # exhausted
            logger.exception("LLM call failed after retry attempts")
            self.ui_bus.dispatch_ui_update(ui_events.Error(f"LLM error: {e}"))
            raise
