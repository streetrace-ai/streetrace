"""AI Provider Factory Module.

This module provides a factory function to create instances of the appropriate LLMAPI
implementations based on available API keys or explicit provider selection.
"""

import logging
import os

from streetrace.llm.claude.impl import Claude
from streetrace.llm.gemini.impl import Gemini
from streetrace.llm.llmapi import LLMAPI
from streetrace.llm.ollama.impl import Ollama
from streetrace.llm.openai.impl import OpenAI


def get_ai_provider(provider_name: str | None = None) -> LLMAPI:
    """Factory function to get the appropriate AI provider instance.

    Args:
        provider_name: Optional explicitly specified provider name
                     ('claude', 'gemini', 'openai', 'ollama')

    Returns:
        LLMAPI: An instance of the appropriate LLMAPI implementation

    Raises:
        ValueError: If the specified provider is not available or if no API keys are found

    """
    # If provider is explicitly specified, use that
    if provider_name:
        provider_name = provider_name.lower()
        if provider_name == "claude":
            if not os.environ.get("ANTHROPIC_API_KEY"):
                msg = "Requested Claude provider but ANTHROPIC_API_KEY not found"
                raise ValueError(
                    msg,
                )
            return Claude()
        if provider_name == "gemini":
            if not os.environ.get("GEMINI_API_KEY"):
                msg = "Requested Gemini provider but GEMINI_API_KEY not found"
                raise ValueError(
                    msg,
                )
            return Gemini()
        if provider_name == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                msg = "Requested OpenAI provider but OPENAI_API_KEY not found"
                raise ValueError(
                    msg,
                )
            return OpenAI()
        if provider_name == "ollama":
            # Ollama can use local models, so no API key check
            return Ollama()
        msg = f"Unknown provider name: {provider_name}"
        raise ValueError(msg)

    # Auto-detect provider based on available API keys
    if os.environ.get("ANTHROPIC_API_KEY"):
        logging.info("Using Claude provider (ANTHROPIC_API_KEY found)")
        return Claude()
    if os.environ.get("GEMINI_API_KEY"):
        logging.info("Using Gemini provider (GEMINI_API_KEY found)")
        return Gemini()
    if os.environ.get("OPENAI_API_KEY"):
        logging.info("Using OpenAI provider (OPENAI_API_KEY found)")
        return OpenAI()
    # Default to Ollama if no API keys are found
    logging.info("Using Ollama provider (no API keys found)")
    return Ollama()
