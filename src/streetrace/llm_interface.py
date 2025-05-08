"""A single poitn of creating an interface to any LLM used by StreetRace🚗💨."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, override

from google.adk.models.lite_llm import LiteLlm
from litellm.exceptions import InternalServerError, RateLimitError
from litellm.types.utils import ModelResponse
from tenacity import TryAgain, retry, stop_after_attempt, wait_incrementing

from streetrace.history import History
from streetrace.logging import get_logger
from streetrace.ui.console_ui import ConsoleUI

_MAX_RETRIES = 7

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

    @abstractmethod
    @property
    def llm() -> TLlmInterface:
        """The internal LLM interface instance."""

    @abstractmethod
    async def generate_async(
        self, history: History, tools: list[dict],
    ) -> ModelResponse:
        """Call LLM interface's async generate method based on conversation history."""


def get_llm_interface(model: str, ui: ConsoleUI) -> LlmInterface:
    """Create an LLM interface factory."""
    return AdkLiteLlmInterface(model, ui)


class AdkLiteLlmInterface(LlmInterface[LiteLlm]):
    """LiteLLM interface for ADK."""

    def __init__(self, model: str, ui: ConsoleUI) -> None:
        """Initialize new AdkLiteLlmInterface for the given model.

        Args:
            model (str): Model names in format provider/model, or just model. See https://docs.litellm.ai/docs/set_keys.
            ui: UI component to write messages for the user.

        """
        self.llm_instance = LiteLlm(model)
        self.ui = ui

    @override
    @property
    def llm(self) -> LiteLlm:
        """Get the internal LLM interface reference."""
        return self.llm_instance

    # Only retry on specific LiteLLM exceptions that indicate a potentially
    # transient issue (like rate limiting). Do not retry on general errors.
    @retry(
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_incrementing(start=30, increment=30, max=10 * 60),
        reraise=True,
    )
    @override
    async def generate_async(
        self, history: History, tools: list[dict],
    ) -> ModelResponse:
        """Generate content using the provided history and the initialized LiteLlm instance.

        Args:
            history: Conversation history in LiteLlm format.
            tools: tools in OpenAI format.

        """
        logger.debug("Calling LLM API...")
        try:
            completion = await self.llm_instance.llm_client.acompletion(
                model=self.llm_instance.model,
                messages=[m.to_dict() for m in history.get_all_messages()],
                stream=False,
                tools=tools.tools,
                num_retries=0,  # Let tenacity handle retries
            )
        except RateLimitError as rate_limit_err:
            # Log and increment count for the specific retry handler
            logger.exception()
            self.ui.display_warning(str(rate_limit_err))
            # Reraise TryAgain explicitly to signal tenacity to retry
            raise TryAgain from rate_limit_err
        except InternalServerError as server_error:
            # Log and increment count for the specific retry handler
            self.ui.display_error(str(server_error))
            logger.exception()
            # Reraise TryAgain explicitly to signal tenacity to retry
            raise TryAgain from server_error
        except Exception:
            # For any other exception, log it and let tenacity's reraise=True handle it
            # (i.e., it will stop retrying and raise the original exception)
            logger.exception("LLM call failed with non-retried exception.")
            raise  # Reraises the original exception 'e'
        else:
            return completion
