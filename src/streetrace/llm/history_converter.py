"""
Abstract Type Converter Module

This module defines the abstract base class TypeConverter that serves as a template
for specific LLM provider converters. It defines the interface for converting between
the common message format and provider-specific formats.
"""

import abc
from typing import Generic, Iterable, List, Optional, TypeVar, override

from streetrace.llm.wrapper import (
    ContentPart,
    ContentPartText,
    ContentPartToolCall,
    History,
    Message,
    Role,
)

# Define generic type variables for provider-specific types
T_AiRequestMessage = TypeVar("T_AiRequestMessage")
T_AiRequestPart = TypeVar("T_AiRequestPart")
T_AiResponsePart = TypeVar("T_AiResponsePart")
T_ChunkWrapper = TypeVar("T_ChunkWrapper")


class ChunkWrapper(Generic[T_AiResponsePart], abc.ABC):
    raw: T_AiResponsePart

    def __init__(self, chunk: T_AiResponsePart):
        self.raw = chunk

    @abc.abstractmethod
    def get_text(self) -> str:
        pass

    @abc.abstractmethod
    def get_tool_calls(self) -> List[ContentPartToolCall]:
        pass

    @abc.abstractmethod
    def get_finish_message(self) -> Optional[str]:
        pass


class FinishWrapper(ChunkWrapper[str]):
    """
    Wrapper for Gemini's Part that implements the ChunkWrapper interface.

    This allows for a consistent way to access content from Gemini's responses.
    """

    def __init__(self, finish_reason: str, finish_message: str):
        super().__init__(finish_reason)
        self.finish_message = finish_message

    @override
    def get_text(self) -> str:
        """Get text content from the chunk if it has text."""
        return None

    @override
    def get_tool_calls(self) -> List[ContentPartToolCall]:
        """Get tool calls from the chunk if it has function calls."""
        return None

    @override
    def get_finish_message(self) -> str:
        """Get text content from the chunk if it has text."""
        return f"{self.raw}: {self.finish_message}" if self.raw is not None else None


class HistoryConverter(Generic[T_AiRequestMessage, T_AiRequestPart, T_AiResponsePart, T_ChunkWrapper], abc.ABC):
    """
    Abstract base class for converting between common message format and provider-specific formats.

    This class serves as a template for provider-specific converters, ensuring consistent
    interface across different LLM implementations.

    Type Parameters:
        T_AiRequestMessage: The provider-specific history item type
        T_AiResponsePart: The provider-specific streaming content chunk type
    """

    def create_chunk_wrapper(
        self,
        chunk: T_AiResponsePart,
    ) -> T_ChunkWrapper:
        """
        Create a wrapper for provider-specific streaming content chunks.

        Args:
            chunk: The chunk to wrap

        Returns:
            A ChunkWrapper[T] implementation to access chunk data
        """
        return T_ChunkWrapper(chunk)

    def create_provider_history(self, history: History) -> List[T_AiRequestMessage]:
        """
        Convert common History format to provider-specific message format.

        Args:
            history: The common format history

        Returns:
            List of provider-specific messages
        """
        provider_history: List[T_AiRequestMessage] = []

        if history.system_message:
            msg = self._provider_message(Role.SYSTEM, [
                self._common_to_request(ContentPartText(text=history.system_message)),
            ])
            if msg:
                provider_history.append(msg)

        if history.context:
            msg = self._provider_message(Role.CONTEXT, [
                self._common_to_request(ContentPartText(text=history.context)),
            ])
            if msg:
                provider_history.append(msg)


        content = self.to_provider_history_items(history.conversation)
        if content:
            provider_history.extend(content)

        return provider_history

    def to_provider_history_items(
        self,
        turn: List[Message],
    ) -> Iterable[T_AiRequestMessage]:
        if turn:
            for message in turn:
                yield self._provider_message(message.role, [
                    self._common_to_request(part) for part in message.content
                ])

    @abc.abstractmethod
    def _provider_message(self, role: Role, items: List[T_AiRequestPart]) -> T_AiRequestMessage:
        """
        Convert provider-specific response content part to common history item part.
        """
        pass

    @abc.abstractmethod
    def _common_to_request(self, item: ContentPart) -> T_AiRequestPart:
        """
        Convert common history item part to provider-specific request content part.

        For use in create_provider_history, to_provider_history_items.
        """
        pass
