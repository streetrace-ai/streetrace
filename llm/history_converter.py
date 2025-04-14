"""
Abstract Type Converter Module

This module defines the abstract base class TypeConverter that serves as a template
for specific LLM provider converters. It defines the interface for converting between
the common message format and provider-specific formats.
"""

import abc
from typing import Generic, List, Optional, TypeVar

from llm.wrapper import (ContentPartToolCall, ContentPartToolResult, History, Message)

# Define generic type variables for provider-specific types
T_MessageParam = TypeVar('T_MessageParam')
T_Chunk = TypeVar('T_Chunk')

class ChunkWrapper(Generic[T_Chunk], abc.ABC):
    raw: T_Chunk

    def __init__(self, chunk: T_Chunk):
        self.raw = chunk

    @abc.abstractmethod
    def get_text(self) -> str:
        pass

    @abc.abstractmethod
    def get_tool_calls(self) -> List[ContentPartToolCall]:
        pass

class HistoryConverter(Generic[T_MessageParam, T_Chunk], abc.ABC):
    """
    Abstract base class for converting between common message format and provider-specific formats.

    This class serves as a template for provider-specific converters, ensuring consistent
    interface across different LLM implementations.

    Type Parameters:
        T_MessageParam: The provider-specific history item type
        T_Chunk: The provider-specific streaming content chunk type
    """

    @abc.abstractmethod
    def from_history(self, history: History) -> List[T_MessageParam]:
        """
        Convert common History format to provider-specific message format.

        Args:
            history: The common format history

        Returns:
            List of provider-specific messages
        """
        pass

    @abc.abstractmethod
    def to_history(
        self,
        provider_history: List[T_MessageParam]
    ) -> List[Message]:
        """
        Convert provider-specific history to common format messages.

        Args:
            provider_history: The provider-specific history

        Returns:
            List of common format messages
        """
        pass

    @abc.abstractmethod
    def to_history_item(
        self,
        messages: List[ChunkWrapper] | List[ContentPartToolResult],
    ) -> Optional[T_MessageParam]:
        """
        Convert chunks or tool results to a provider-specific message.

        Args:
            messages: The chunks or tool results to convert

        Returns:
            A provider-specific message, or None if no valid message can be created
        """
        pass

    @abc.abstractmethod
    def create_chunk_wrapper(
        self,
        chunk: T_Chunk,
    ) -> ChunkWrapper[T_Chunk]:
        """
        Create a wrapper for provider-specific streaming content chunks.

        Args:
            chunk: The chunk to wrap

        Returns:
            A ChunkWrapper[T] implementation to access chunk data
        """
        pass