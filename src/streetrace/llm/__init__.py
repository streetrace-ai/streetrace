"""Language Model (LLM) integration package.

This package provides interfaces and implementations for integrating
with various LLM providers like OpenAI, Anthropic, Gemini, and Ollama.
"""

from ollama import Message

from streetrace.llm.history_converter import HistoryConverter
from streetrace.llm.llmapi import LLMAPI, RetriableError
from streetrace.llm.llmapi_factory import get_ai_provider
from streetrace.llm.wrapper import (
    ContentPart,
    ContentPartFinishReason,
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    ContentPartUsage,
    ContentType,
    History,
    Role,
    ToolCallResult,
    ToolOutput,
)

__all__ = [
    "LLMAPI",
    "ContentPart",
    "ContentPartFinishReason",
    "ContentPartText",
    "ContentPartToolCall",
    "ContentPartToolResult",
    "ContentPartUsage",
    "ContentType",
    "History",
    "HistoryConverter",
    "Message",
    "RetriableError",
    "Role",
    "ToolCallResult",
    "ToolOutput",
    "get_ai_provider",
]
