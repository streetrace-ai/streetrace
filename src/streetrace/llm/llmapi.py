"""AI Provider Interface Module.

This module defines the abstract base class LLMAPI that serves as a common interface
for different AI model providers (Anthropic, Gemini, OpenAI, Ollama). It standardizes
initialization, API calls, and tool management across all providers.
"""

import abc
from collections.abc import Iterator
from typing import Any

from streetrace.llm.wrapper import ContentPart, History, Message

ProviderHistory = list[dict[str, Any]]
ProviderTools = list[dict[str, Any]]


class LLMAPI(abc.ABC):
    """Abstract base class for AI model providers.

    This class defines a common interface that all AI providers must implement,
    standardizing how we initialize clients, transform tools, manage conversations,
    and generate content with tools.
    """

    @abc.abstractmethod
    def initialize_client(self) -> Any:
        """Initialize and return the AI provider client.

        Returns:
            Any: The initialized client object

        Raises:
            ValueError: If required API keys or configuration is missing

        """

    @abc.abstractmethod
    def transform_history(self, history: History) -> ProviderHistory:
        """Transform conversation history from common format into provider-specific format.

        Args:
            history (History): Conversation history to transform

        Returns:
            ProviderHistory: Conversation history in provider-specific format

        """

    @abc.abstractmethod
    def append_history(
        self,
        provider_history: ProviderHistory,
        turn: list[Message],
    ):
        """Add turn items into provider's conversation history.

        Args:
            provider_history: List of provider-specific message objects
            turn: List of items in this turn

        """

    @abc.abstractmethod
    def transform_tools(self, tools: list[dict[str, Any]]) -> ProviderTools:
        """Transform tools from common format to provider-specific format.

        Args:
            tools: List of tool definitions in common format

        Returns:
            ProviderTools: List of tool definitions in provider-specific format

        """

    @abc.abstractmethod
    def pretty_print(self, messages: ProviderHistory) -> str:
        """Format message list for readable logging.

        Args:
            messages: List of message objects to format

        Returns:
            str: Formatted string representation

        """

    @abc.abstractmethod
    def manage_conversation_history(
        self,
        messages: ProviderHistory,
        max_tokens: int | None = None,
    ) -> bool:
        """Ensure conversation history is within token limits by intelligently pruning when needed.

        Args:
            messages: List of message objects to manage
            max_tokens: Maximum token limit

        Returns:
            bool: True if successful, False if pruning failed

        """

    @abc.abstractmethod
    def generate(
        self,
        client: Any,
        model_name: str | None,
        system_message: str,
        messages: ProviderHistory,
        tools: ProviderTools,
    ) -> Iterator[ContentPart]:
        """Get API response from the provider.

        When streaming, returns a stream, otherwise returns an iterator over content items.

        Args:
            client: The provider client
            model_name: The model name to use (None for default model)
            system_message: The system message to use in the request
            messages: The messages to send in the request
            tools: The tools to use

        Returns:
            Iterator[Any]: Provider response stream
            or Any: The final response object

        """


class RetriableError(Exception):
    """A custom exception class for retriable errors.

    This class is used to raise and handle errors that can be retried,
    such as rate limit errors from API providers.

    Attributes:
        max_retries (int): The maximum number of retry attempts allowed.
        message (str): The error message.

    """

    def __init__(
        self,
        message: str,
        max_retries: int = 3,
        wait_seconds: int = 30,
    ) -> None:
        """Initialize the RetriableError.

        Args:
            message (str): The error message.
            max_retries (int): The maximum number of retry attempts allowed. Defaults to 3.

        """
        self.max_retries = max_retries
        self.message = message
        self.wait_seconds = wait_seconds
        super().__init__(self.message)

    def wait_time(self, retry_count: int) -> int:
        """Calculate the wait time before the next retry attempt.

        Args:
            retry_count (int): The current retry attempt count.

        Returns:
            int: The time to wait in seconds before the next retry attempt.

        """
        return self.wait_seconds
