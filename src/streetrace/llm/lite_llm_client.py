"""A class to swap ADK's LiteLLMClient to allow counting tokens and costs."""

# LiteLLMClient is not type checked, so we need to disable some rules:
# mypy: disable-error-code=misc,no-untyped-def,no-any-return

from collections.abc import Iterable

from google.adk.models.lite_llm import LiteLLMClient
from litellm.cost_calculator import completion_cost
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ModelResponse, Usage

from streetrace.costs import UsageAndCost
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


def _try_extract_usage(response: ModelResponse) -> Usage | None:
    usage = response.get("usage", None)  # type: ignore[no-untyped-call]
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


class LiteLLMClientWithUsage(LiteLLMClient):  # type: ignore[misc,no-untyped-def,no-any-return]
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
