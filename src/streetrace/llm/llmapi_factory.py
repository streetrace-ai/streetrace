"""AI Provider Factory Module.

This module provides a factory function to create instances of the appropriate LLMAPI
implementations based on available API keys or explicit provider selection.
"""

import logging
import os

from streetrace.llm.anthropic.impl import Anthropic
from streetrace.llm.gemini.impl import Gemini
from streetrace.llm.llmapi import LLMAPI
from streetrace.llm.ollama.impl import Ollama
from streetrace.llm.openai.impl import OpenAI

logger = logging.getLogger(__name__)


def get_ai_provider(provider_name: str | None = None) -> LLMAPI:  # noqa: C901, PLR0911
    """Create the appropriate AI provider instance.

    Args:
        provider_name: Optional explicitly specified provider name
                     ('anthropic', 'gemini', 'openai', 'ollama')

    Returns:
        LLMAPI: An instance of the appropriate LLMAPI implementation

    Raises:
        ValueError: If the specified provider is not available or if no API keys are found

    """
    # If provider is explicitly specified, use that
    if provider_name:
        provider_name = provider_name.lower()
        match provider_name:
            case "anthropic":
                if not os.environ.get("ANTHROPIC_API_KEY"):
                    msg = "Requested Anthropic provider but ANTHROPIC_API_KEY not found"
                    raise ValueError(
                        msg,
                    )
                return Anthropic()
            case "gemini":
                if not os.environ.get("GEMINI_API_KEY"):
                    msg = "Requested Gemini provider but GEMINI_API_KEY not found"
                    raise ValueError(
                        msg,
                    )
                return Gemini()
            case "openai":
                if not os.environ.get("OPENAI_API_KEY"):
                    msg = "Requested OpenAI provider but OPENAI_API_KEY not found"
                    raise ValueError(
                        msg,
                    )
                return OpenAI()
            case "ollama":
                # Ollama can use local models, so no API key check
                return Ollama()

        msg = f"Unknown provider name: {provider_name}"
        raise ValueError(msg)

    # Auto-detect provider based on available API keys
    if os.environ.get("ANTHROPIC_API_KEY"):
        logger.info("Using Anthropic provider (ANTHROPIC_API_KEY found)")
        return Anthropic()
    if os.environ.get("GEMINI_API_KEY"):
        logger.info("Using Gemini provider (GEMINI_API_KEY found)")
        return Gemini()
    if os.environ.get("OPENAI_API_KEY"):
        logger.info("Using OpenAI provider (OPENAI_API_KEY found)")
        return OpenAI()

    msg = f"Provider '{provider_name or 'default'}' could not be loaded."
    raise ValueError(msg)
