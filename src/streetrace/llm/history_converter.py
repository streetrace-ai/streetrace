"""Abstract Type Converter Module.

This module defines the abstract base class TypeConverter that serves as a template
for specific LLM provider converters. It defines the interface for converting between
the common message format and provider-specific formats.
"""

import abc
from collections.abc import Iterator
from typing import Generic, TypeVar

from streetrace.llm.wrapper import (
    ContentPart,
    ContentPartText,
    History,
    Message,
    Role,
)

# Define generic type variables for provider-specific types
T_AiRequestMessage = TypeVar("T_AiRequestMessage")
T_AiResponseMessage = TypeVar("T_AiResponseMessage")


class HistoryConverter(Generic[T_AiRequestMessage, T_AiResponseMessage], abc.ABC):
    """Abstract base class for converting between common message format and provider-specific formats.

    This class serves as a template for provider-specific converters, ensuring consistent
    interface across different LLM implementations.

    Type Parameters:
        T_AiRequestMessage: The provider-specific history item type
        T_AiResponseMessage: The provider-specific response type
    """

    def create_provider_history(self, history: History) -> list[T_AiRequestMessage]:
        """Convert common History format to provider-specific message format.

        Args:
            history: The common format history

        Returns:
            List of provider-specific messages

        """
        provider_history: list[T_AiRequestMessage] = []

        if history.system_message:
            for msg in self.create_history_messages(
                Role.SYSTEM,
                [ContentPartText(text=history.system_message)],
            ):
                provider_history.append(msg)

        if history.context:
            for msg in self.create_history_messages(
                Role.CONTEXT,
                [ContentPartText(text=history.context)],
            ):
                provider_history.append(msg)

        provider_history.extend(self.to_provider_history_items(history.conversation))

        return provider_history

    def to_provider_history_items(
        self,
        turn: list[Message],
    ) -> Iterator[T_AiRequestMessage]:
        if turn:
            for message in turn:
                yield from self.create_history_messages(message.role, message.content)

    @abc.abstractmethod
    def create_history_messages(
        self,
        role: Role,
        items: list[ContentPart],
    ) -> Iterator[T_AiRequestMessage]:
        pass

    @abc.abstractmethod
    def get_response_parts(
        self,
        model_response: T_AiResponseMessage,
    ) -> Iterator[ContentPart]:
        pass
