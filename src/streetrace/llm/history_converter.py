"""Abstract Type Converter Module.

This module defines the abstract base class TypeConverter that serves as a template
for specific LLM provider converters. It defines the interface for converting between
the common message format and provider-specific formats.

Testing scenarios for implementers:

1. Basic conversion: Test conversion of simple text messages for all role types.
   Ensure that user, system, model, and context roles are properly converted.

2. Empty history: Test conversion of an empty History object to verify correct handling
   of empty inputs (should return empty provider history).

3. System message only: Test conversion of a History with only a system message
   to ensure proper formatting of system instructions.

4. Complex content types: Test conversion of messages containing multiple content types
   (text, tool calls, tool results) to verify all parts are properly translated.

5. Round-trip conversion: Test that converting to provider format and back results in
   semantically equivalent content (accounting for provider-specific limitations).

6. Edge cases: Test handling of extremely long messages, special characters, and
   unicode to ensure proper encoding/decoding.

7. Error handling: Test how the converter handles malformed inputs and verify
   appropriate error messages or fallbacks.

8. Multi-turn conversation: Test conversion of a full conversation with
   multiple back-and-forth exchanges.

9. Streaming responses: If applicable, test parsing of streamed/chunked responses
   from the provider into coherent ContentPart objects.

10. Role mapping consistency: Verify consistent role mapping across all conversion
    functions for each provider's specific role system.
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
            provider_history.extend(
                list(
                    self.create_history_messages(
                        Role.SYSTEM,
                        [ContentPartText(text=history.system_message)],
                    ),
                ),
            )

        if history.context:
            provider_history.extend(
                list(
                    self.create_history_messages(
                        Role.CONTEXT,
                        [ContentPartText(text=history.context)],
                    ),
                ),
            )

        provider_history.extend(self.to_provider_history_items(history.conversation))

        return provider_history

    def to_provider_history_items(
        self,
        turn: list[Message],
    ) -> Iterator[T_AiRequestMessage]:
        """Convert a list of messages into provider-specific history items.

        Args:
            turn: A list of Message objects representing a conversation turn.

        Returns:
            An iterator over provider-specific request messages.

        """
        if turn:
            for message in turn:
                yield from self.create_history_messages(message.role, message.content)

    @abc.abstractmethod
    def create_history_messages(
        self,
        role: Role,
        items: list[ContentPart],
    ) -> Iterator[T_AiRequestMessage]:
        """Create provider-specific request messages for the given role and content parts.

        Args:
            role: The role of the message (e.g., system, user, context).
            items: A list of content parts to include in the message.

        Returns:
            An iterator over provider-specific request messages.

        """

    @abc.abstractmethod
    def get_response_parts(
        self,
        model_response: T_AiResponseMessage,
    ) -> Iterator[ContentPart]:
        """Extract content parts from the provider-specific model response.

        Args:
            model_response: The provider-specific response object.

        Returns:
            An iterator over ContentPart objects representing the response content.

        """
