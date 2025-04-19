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
    ContentPartToolResult,
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
    # history converter:
    # 1. update provider history based on turn results:
    #    - convert assistant message chunks to provider history
    #    - convert tool results to provider history
    # 2. update common history based on turn results:
    #    - convert assistant message chunks to common history messages
    #    - add tool results to common history
    # 3. create provider history based on common history

    """
    Abstract base class for converting between common message format and provider-specific formats.

    This class serves as a template for provider-specific converters, ensuring consistent
    interface across different LLM implementations.

    Type Parameters:
        T_AiRequestMessage: The provider-specific history item type
        T_AiResponsePart: The provider-specific streaming content chunk type
    """

    @abc.abstractmethod
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
        pass

    @abc.abstractmethod
    def create_provider_history(self, history: History) -> List[T_AiRequestMessage]:
        """
        Convert common History format to provider-specific message format.

        Args:
            history: The common format history

        Returns:
            List of provider-specific messages
        """
        provider_history: List[T_AiRequestMessage] = []

        if history.context:
            provider_history.append(
                self._provider_message(Role.USER, [
                    self._common_to_request(ContentPartText(text=history.context)),
                    ])
            )

        for message in history.conversation:
            content = [self._common_to_request(part) for part in message.content]

            if content:
                provider_history.append(
                    self._provider_message(message.role, content)
                )
        return provider_history

    @abc.abstractmethod
    def to_provider_history_items(
        self,
        turn: List[ChunkWrapper | ContentPartToolResult],
    ) -> Iterable[T_AiRequestMessage]:
        if not turn:
            return None
        assistant_messages: List[T_AiRequestPart] = []
        tool_results: List[T_AiRequestPart] = []
        for item in turn:
            if isinstance(item, ChunkWrapper):
                part = self._response_to_request(item.raw)
                if part is not None:
                    assistant_messages.append(part)
            elif isinstance(item, ContentPartToolResult):
                tool_results.append(self._common_to_request(item))
            else:
                raise TypeError(f"Unsupported turn type in list: {type(item)}")

        if assistant_messages:
            yield self._provider_message(Role.MODEL, assistant_messages)
        if tool_results:
            yield self._provider_message(Role.TOOL, tool_results)

    @abc.abstractmethod
    def to_common_history_items(
        self,
        turn: List[ChunkWrapper | ContentPartToolResult],
    ) -> Iterable[Message]:
        if not turn:
            return None
        assistant_response: List[ContentPart] = []
        tool_results: List[ContentPart] = []
        for item in turn:
            if isinstance(item, ChunkWrapper):
                parts = self._response_to_common(item.raw)
                assistant_response.extend(parts)
            elif isinstance(item, ContentPartToolResult):
                tool_results.append(item)
            else:
                raise TypeError(f"Unsupported turn type in list: {type(item)}")

        if assistant_response:
            yield Message(
                role=Role.MODEL, content=assistant_response
            )
        if tool_results:
            yield Message(
                role=Role.TOOL, content=tool_results
            )

    @abc.abstractmethod
    def _provider_message(self, role: Role, items: List[T_AiRequestPart]) -> T_AiRequestMessage:
        """
        Convert provider-specific response content part to common history item part.

        For use in to_common_history_items.
        """
        pass

    @abc.abstractmethod
    def _common_to_request(self, item: ContentPart) -> T_AiRequestPart:
        """
        Convert common history item part to provider-specific request content part.

        For use in create_provider_history, to_provider_history_items.
        """
        pass

    @abc.abstractmethod
    def _response_to_request(self, item: T_AiResponsePart) -> Optional[T_AiRequestPart]:
        """
        Convert provider-specific response content part to request content part.

        For use in to_provider_history_items.
        """
        pass

    @abc.abstractmethod
    def _response_to_common(self, item: T_AiResponsePart) -> Iterable[ContentPart]:
        """
        Convert provider-specific response content part to common history item part.

        For use in to_common_history_items.
        """
        pass
