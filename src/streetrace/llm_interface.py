"""A single point of creating an interface to any LLM used by StreetRace🚗💨."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Generic, TypeVar, override

from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from litellm import token_counter
from litellm.exceptions import InternalServerError, RateLimitError
from litellm.types.utils import ModelResponse
from tenacity import (
    AsyncRetrying,
    TryAgain,
    stop_after_attempt,
    wait_incrementing,
)

from streetrace.history import History
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

_MAX_RETRIES = 7
"""Maximum number of retry attempts for the retrying LLM."""
# Base waiting time between retries in seconds
_RETRY_WAIT_START = 30
"""Base waiting time between retries in seconds."""

_RETRY_WAIT_INCREMENT = 30
"""Increment of waiting time between retries in seconds."""

_RETRY_WAIT_MAX = 10 * 60  # 10 minutes
"""Maximum waiting time between retries in seconds (10 minutes)."""

TLlmInterface = TypeVar("TLlmInterface")

logger = get_logger(__name__)


class LlmInterface(ABC, Generic[TLlmInterface]):
    """A generic LLM interface.

    Provides a way to call an LLM using StreetRace🚗💨 internal types for ease of use.

    StreetRace🚗💨 uses:
        streetrace.history.History for conversation history;
        list[dict] for tools;
        litellm.types.utils.ModelResponse for response.

    Ideally we should provide internal types for all of the above, but there is no
    value in it currently.

    """

    @property
    def llm(self) -> TLlmInterface:
        """The internal LLM interface instance."""
        raise NotImplementedError

    @abstractmethod
    async def generate_async(
        self,
        history: History,
        tools: list[dict],
    ) -> ModelResponse:
        """Call LLM interface's async generate method based on conversation history."""

    def estimate_token_count(
        self,
        prompt: str,
    ) -> int:
        """Estimate the number of tokens in the provided input.

        Override to provide a proper count estimation.
        """
        return len(prompt.split())


def get_llm_interface(model: str, ui_bus: UiBus) -> LlmInterface:
    """Create an LLM interface factory."""
    return AdkLiteLlmInterface(model, ui_bus)


class RetryingLiteLlm(LiteLlm):
    """LiteLlm with built-in retry capabilities for generate_content_async.

    This implementation adds tenacity-based retries to the original LiteLlm
    implementation to handle transient errors like rate limits and server errors.
    """

    def __init__(self, model: str, ui_bus: UiBus, **kwargs) -> None:
        """Initialize the RetryingLiteLlm with a model and UI for feedback.

        Args:
            model: The name of the LiteLlm model
            ui_bus: UI event bus to exchange messages with the UI.
            **kwargs: Additional arguments passed to the LiteLlm constructor

        """
        super().__init__(model=model, **kwargs)
        self._ui_bus = ui_bus
        logger.debug("Initialized RetryingLiteLlm with model: %s", model)

    @override
    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ) -> AsyncGenerator[LlmResponse, None]:
        """Generate content with retry support for handling transient errors.

        This method wraps the original generate_content_async with retry logic
        that handles rate limiting and server errors gracefully.

        Args:
            llm_request: The request to send to the LiteLlm model
            stream: Whether to stream the response

        Yields:
            LlmResponse objects from the model

        """
        logger.debug("Generating content with model %s (stream=%s)", self.model, stream)

        # Define a retrying context that handles specific exceptions
        retrying = AsyncRetrying(
            stop=stop_after_attempt(_MAX_RETRIES),
            wait=wait_incrementing(
                start=_RETRY_WAIT_START,
                increment=_RETRY_WAIT_INCREMENT,
                max=_RETRY_WAIT_MAX,
            ),
            reraise=True,  # Re-raise the last exception when retries are exhausted
        )

        # If streaming is requested, we delegate to the original implementation
        # since it's more complex to handle retry logic with streaming
        if stream:
            logger.debug("Using streaming mode, delegating to original implementation")
            async for response in super().generate_content_async(
                llm_request,
                stream=True,
            ):
                yield response
            return

        # For non-streaming, we use the retry logic
        attempt = 0
        async for attempt_context in retrying:
            with attempt_context:
                attempt += 1
                if attempt > 1:
                    self._ui_bus.dispatch_ui_update(
                        ui_events.Info(
                            f"Retrying (attempt {attempt}/{_MAX_RETRIES})...",
                        ),
                    )

                try:
                    # Call the original method for a single response
                    # (non-streaming implementation returns only one response)
                    async for response in super().generate_content_async(
                        llm_request,
                        stream=False,
                    ):
                        yield response
                        # Break after first response in non-streaming mode
                        break

                except RateLimitError as rate_limit_err:
                    # Log and display the rate limit error
                    logger.exception()
                    self._ui_bus.dispatch_ui_update(
                        ui_events.Warning(
                            f"LLM rate limit reached: {rate_limit_err}",
                        ),
                    )
                    # Signal tenacity to retry
                    raise TryAgain from rate_limit_err

                except InternalServerError as server_error:
                    # Log and display the server error
                    logger.exception("Server error encountered.")
                    self._ui_bus.dispatch_ui_update(
                        ui_events.Error(f"LLM server error: {server_error}"),
                    )
                    # Signal tenacity to retry
                    raise TryAgain from server_error

                except Exception as e:
                    # Log unexpected errors but don't retry
                    logger.exception("LLM call failed with non-retried exception")
                    self._ui_bus.dispatch_ui_update(ui_events.Error(f"LLM error: {e}"))
                    # Re-raise the exception
                    raise


class AdkLiteLlmInterface(LlmInterface[RetryingLiteLlm]):
    """LiteLLM interface for ADK using RetryingLiteLlm.

    This implementation uses the RetryingLiteLlm class which has built-in retry
    functionality for handling transient errors like rate limits and server errors.
    """

    def __init__(self, model: str, ui_bus: UiBus) -> None:
        """Initialize new AdkLiteLlmInterface for the given model.

        Args:
            model (str): Model names in format provider/model, or just model. See https://docs.litellm.ai/docs/set_keys.
            ui_bus: UI event bus to exchange messages with the UI.

        """
        self.model = model
        self.llm_instance = RetryingLiteLlm(model=model, ui_bus=ui_bus)
        self.ui_bus = ui_bus
        ui_bus.on_typing_prompt(self.estimate_token_count)

    @override
    @property
    def llm(self) -> RetryingLiteLlm:
        """Get the internal LLM interface reference."""
        return self.llm_instance

    def estimate_token_count(
        self,
        prompt: str,
    ) -> int:
        """Estimate the number of tokens in the provided input.

        Override to provide a proper count estimation.
        """
        messages = [{"user": "role", "content": prompt}]
        estimated_token_count = token_counter(model=self.model, messages=messages)
        self.ui_bus.dispatch_prompt_token_count_estimate(estimated_token_count)

    # RetryingLiteLlm already handles the retry logic internally, so we don't need
    # the tenacity decorator here anymore
    @override
    async def generate_async(
        self,
        history: History,
        tools: list[dict],
    ) -> ModelResponse:
        """Generate content using the provided history and the initialized LiteLlm instance.

        Args:
            history: Conversation history in LiteLlm format.
            tools: tools in OpenAI format.

        """
        logger.debug("Calling LLM API...")
        # Since we're still using the same LiteLlm client under the hood,
        # we can use the same approach to call the LLM API but with RetryingLiteLlm
        # which will handle retries internally
        try:
            # Use the llm_client from RetryingLiteLlm to make the API call
            return await self.llm_instance.llm_client.acompletion(
                model=self.llm_instance.model,
                messages=[m.to_dict() for m in history.get_all_messages()],
                stream=False,
                tools=tools,
                num_retries=0,  # Let RetryingLiteLlm handle retries
            )
        except Exception as e:
            # RetryingLiteLlm should handle retryable exceptions, so this should only happen
            # for non-retryable errors after all retry attempts have been exhausted
            logger.exception("LLM call failed after retry attempts")
            self.ui_bus.dispatch_ui_update(ui_events.Error(f"LLM error: {e}"))
            raise
