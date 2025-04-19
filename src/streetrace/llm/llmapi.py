"""
AI Provider Interface Module

This module defines the abstract base class LLMAPI that serves as a common interface
for different AI model providers (Claude, Gemini, OpenAI, Ollama). It standardizes
initialization, API calls, and tool management across all providers.
"""

import abc
from typing import Any, Dict, Iterable, List, Optional

from streetrace.llm.history_converter import ChunkWrapper
from streetrace.llm.wrapper import ContentPartToolResult, History

ProviderHistory = List[Dict[str, Any]]
ProviderTools = List[Dict[str, Any]]


class LLMAPI(abc.ABC):
    """
    Abstract base class for AI model providers.

    This class defines a common interface that all AI providers must implement,
    standardizing how we initialize clients, transform tools, manage conversations,
    and generate content with tools.
    """

    @abc.abstractmethod
    def initialize_client(self) -> Any:
        """
        Initialize and return the AI provider client.

        Returns:
            Any: The initialized client object

        Raises:
            ValueError: If required API keys or configuration is missing
        """
        pass

    @abc.abstractmethod
    def transform_history(self, history: History) -> ProviderHistory:
        """
        Transform conversation history from common format into provider-specific format.

        Args:
            history (History): Conversation history to transform

        Returns:
            ProviderHistory: Conversation history in provider-specific format
        """
        pass

    @abc.abstractmethod
    def transform_tools(self, tools: List[Dict[str, Any]]) -> ProviderTools:
        """
        Transform tools from common format to provider-specific format.

        Args:
            tools: List of tool definitions in common format

        Returns:
            ProviderTools: List of tool definitions in provider-specific format
        """
        pass

    @abc.abstractmethod
    def pretty_print(self, messages: ProviderHistory) -> str:
        """
        Format message list for readable logging.

        Args:
            messages: List of message objects to format

        Returns:
            str: Formatted string representation
        """
        pass

    @abc.abstractmethod
    def manage_conversation_history(
        self, messages: ProviderHistory, max_tokens: int = None
    ) -> bool:
        """
        Ensure conversation history is within token limits by intelligently pruning when needed.

        Args:
            messages: List of message objects to manage
            max_tokens: Maximum token limit

        Returns:
            bool: True if successful, False if pruning failed
        """
        pass

    @abc.abstractmethod
    def generate(
        self,
        client: Any,
        model_name: Optional[str],
        system_message: str,
        messages: ProviderHistory,
        tools: ProviderTools,
    ) -> Iterable[ChunkWrapper]:
        """
        Get API response from the provider.

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
        pass

    @abc.abstractmethod
    def append_to_provider_history(
        self,
        provider_history: ProviderHistory,
        turn: List[ChunkWrapper | ContentPartToolResult],
    ):
        """
        Add turn items into provider's conversation history.

        Args:
            provider_history: List of provider-specific message objects
            turn: List of items in this turn
        """
        pass

    @abc.abstractmethod
    def append_to_common_history(
        self,
        history: History,
        turn: List[ChunkWrapper | ContentPartToolResult],) -> None:
        """
        Updates the conversation history in common format based on the provided turn items.

        Args:
            messages (ProviderHistory): Provider-specific conversation history
            history (History): Conversation history in common format
        """
        pass


class RetriableError(Exception):
    """
    A custom exception class for retriable errors.

    This class is used to raise and handle errors that can be retried,
    such as rate limit errors from API providers.

    Attributes:
        max_retries (int): The maximum number of retry attempts allowed.
        message (str): The error message.
    """

    def __init__(self, message: str, max_retries: int = 3):
        """
        Initialize the RetriableError.

        Args:
            message (str): The error message.
            max_retries (int): The maximum number of retry attempts allowed. Defaults to 3.
        """
        self.max_retries = max_retries
        self.message = message
        super().__init__(self.message)

    def wait_time(self, retry_count: int) -> int:
        """
        Calculate the wait time before the next retry attempt.

        Args:
            retry_count (int): The current retry attempt count.

        Returns:
            int: The time to wait in seconds before the next retry attempt.
        """
        return 30