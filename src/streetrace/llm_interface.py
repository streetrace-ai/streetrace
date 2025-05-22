"""A single point of creating an interface to any LLM used by StreetRace🚗💨."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Iterable
from typing import Any, cast, override

from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm, LiteLLMClient
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from litellm import (
    CustomStreamWrapper,
    completion_cost,  # type: ignore[not-exported]: documented use
    token_counter,  # type: ignore[not-exported]: documented use
)
from litellm.exceptions import InternalServerError, RateLimitError
from litellm.types.utils import ModelResponse, Usage
from tenacity import (
    AsyncRetrying,
    TryAgain,
    stop_after_attempt,
    wait_incrementing,
)

from streetrace.costs import UsageAndCost
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
    def get_adk_llm(self) -> BaseLlm:
        """Get the ADK LLM interface instance."""
        raise NotImplementedError

    @abstractmethod
    async def generate_async(
        self,
        messages: list,
        tools: list[dict],
    ) -> dict[str, Any]:
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


def _try_extract_usage(response: ModelResponse) -> Usage | None:
    usage = response.get("usage", None)
    if not usage:
        logger.warning("Usage not found in ModelResponse: %s", response)
        return None
    if not isinstance(usage, Usage):
        logger.warning("Unexpected usage type: %s:\n%s", type(usage), usage)
        return None
    logger.info("Usage found: %s", usage)
    return usage


def _try_extract_cost(
    model: str,
    messages: object,
    completion_response: ModelResponse,
) -> float | None:
    """Use litellm.completion_cost to calculate costs based on known costs.

    See https://docs.litellm.ai/docs/completion/token_usage.

    Raises:
        Exception, if the calculation was unsuccessful (perhaps, model costs are not
            known).

    """
    if not isinstance(messages, list):
        logger.warning(
            "Unexpected messages type for cost calculation: %s:\n%s",
            type(messages),
            messages,
        )
        messages = list(messages) if isinstance(messages, Iterable) else [messages]
    return completion_cost(
        model=model,
        messages=messages,
        completion_response=completion_response,
    )


class LiteLLMClientWithUsage(LiteLLMClient):
    """Provides acompletion method (for better testability)."""

    def __init__(self, ui_bus: UiBus) -> None:
        """Initialize a new instance."""
        super().__init__()
        self.ui_bus = ui_bus

    def _process_usage_and_cost(
        self,
        model: str,
        messages: object,
        completion_response: object,
    ) -> None:
        if not isinstance(completion_response, ModelResponse):
            if isinstance(completion_response, CustomStreamWrapper):
                logger.warning(
                    "NotImplemented (and not plans for now): CustomStreamWrapper "
                    "streaming generator cannot provide usage info itself.",
                )
            else:
                logger.warning(
                    "Cannot extract usage from LiteLLM response type %s",
                    type(completion_response),
                )
            return

        usage = _try_extract_usage(completion_response)

        try:
            cost = _try_extract_cost(model, messages, completion_response)
        except Exception:
            msg = (
                "Cost could not be calculated. See "
                "https://docs.litellm.ai/docs/completion/token_usage#6-completion_cost."
            )
            logger.exception(msg)
            self.ui_bus.dispatch_ui_update(ui_events.Warn(msg))
        else:
            usage_and_costs = UsageAndCost(
                completion_tokens=usage.completion_tokens if usage else None,
                prompt_tokens=usage.prompt_tokens if usage else None,
                cost=cost,
            )
            self.ui_bus.dispatch_usage_data(usage_and_costs)

    async def acompletion(
        self,
        model,  # noqa: ANN001
        messages,  # noqa: ANN001
        tools,  # noqa: ANN001
        **kwargs,
    ) -> ModelResponse | CustomStreamWrapper:
        """Asynchronously calls acompletion.

        Args:
          model: The model name.
          messages: The messages to send to the model.
          tools: The tools to use for the model.
          **kwargs: Additional arguments to pass to acompletion.

        Returns:
          The model response as a message.

        """
        response = await super().acompletion(model, messages, tools, **kwargs)
        self._process_usage_and_cost(model, messages, response)
        return response

    def completion(
        self,
        model,  # noqa: ANN001
        messages,  # noqa: ANN001
        tools,  # noqa: ANN001
        stream=False,  # noqa: ANN001, FBT002
        **kwargs,
    ) -> ModelResponse | CustomStreamWrapper:
        """Call LiteLLM completion, use in streaming mode.

        Args:
          model: The model to use.
          messages: The messages to send.
          tools: The tools to use for the model.
          stream: Whether to stream the response.
          **kwargs: Additional arguments to pass to completion.

        Returns:
          The response from the model.

        """
        response = super().completion(model, messages, tools, stream, **kwargs)
        if not stream:
            self._process_usage_and_cost(model, messages, response)
        return response


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
        self.llm_client = LiteLLMClientWithUsage(ui_bus)
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
                    logger.exception("Rate limit error")
                    self._ui_bus.dispatch_ui_update(
                        ui_events.Warn(
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
                    # we should re-throw this, but due to Gemini responding with
                    # 500 randomly, we will re-try. Perhaps limit this to Gemini models.
                    raise TryAgain from server_error

                except Exception as e:
                    # Log unexpected errors but don't retry
                    logger.exception("LLM call failed with non-retried exception")
                    self._ui_bus.dispatch_ui_update(ui_events.Error(f"LLM error: {e}"))
                    # Re-raise the exception
                    raise


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
        self.model = model
        self.llm_instance = RetryingLiteLlm(model=model, ui_bus=ui_bus)
        self.ui_bus = ui_bus
        ui_bus.on_typing_prompt(self.estimate_token_count)

    @override
    def get_adk_llm(self) -> RetryingLiteLlm:
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
        return estimated_token_count

    # RetryingLiteLlm already handles the retry logic internally, so we don't need
    # the tenacity decorator here anymore
    @override
    async def generate_async(
        self,
        messages: list,
        tools: list[dict],
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
