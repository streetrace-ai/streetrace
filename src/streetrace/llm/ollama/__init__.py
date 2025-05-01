"""Ollama-specific implementation for locally hosted open source models."""

from streetrace.llm.ollama.converter import OllamaHistoryConverter
from streetrace.llm.ollama.impl import Ollama

__all__ = ["Ollama", "OllamaHistoryConverter"]
