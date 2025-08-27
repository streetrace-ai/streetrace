"""Factory for creating and managing LLM models."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.adk.models.base_llm import BaseLlm

    from streetrace.args import Args

from streetrace.llm.llm_interface import (
    AdkLiteLlmInterface,
    LlmInterface,
)
from streetrace.log import get_logger
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class ModelFactory:
    """Factory class to create and manage models for the StreetRace application.

    This class is responsible for:
    1. Managing model configurations
    2. Creating and caching LlmInterface instances
    3. Providing access to underlying BaseLlm instances for agents
    """

    current_model_name: str | None = None

    def __init__(
        self,
        default_model_name: str | None,
        ui_bus: UiBus,
        args: "Args",
    ) -> None:
        """Initialize the ModelFactory with model configuration and UI bus.

        Args:
            default_model_name: Name of the model to use
            ui_bus: UI event bus for displaying messages to the user
            args: Application arguments

        """
        self.ui_bus = ui_bus
        self.current_model_name = default_model_name

        # Setup Redis caching if enabled
        if args.cache:
            self._setup_caching()

    def _setup_caching(self) -> None:
        """Set up Redis caching for LiteLLM."""
        try:
            from streetrace.llm.lite_llm_client import setup_redis_caching

            setup_redis_caching()
        except ImportError:
            # If redis package is not available, log and continue
            msg = "Redis package not available. Install with: pip install redis"
            logger.warning(msg)
        except (ConnectionError, RuntimeError) as e:
            # Log caching setup failures but don't crash the application
            logger.warning("Failed to setup Redis caching: %s", e)

    def get_llm_interface(self, model_name: str) -> LlmInterface:
        """Return the default model based on the configuration.

        Returns:
            LlmInterface instance.

        """
        return AdkLiteLlmInterface(model_name, self.ui_bus)

    def get_current_model(self) -> "BaseLlm":
        """Return the default model based on the configuration.

        Returns:
            Either a string model name or a BaseLlm instance.

        """
        if not self.current_model_name:
            msg = "The current model is not set"
            raise ValueError(msg)
        return self.get_llm_interface(self.current_model_name).get_adk_llm()
