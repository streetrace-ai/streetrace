"""
AI Provider Factory Module

This module provides a factory function to create instances of the appropriate LLMAPI
implementations based on available API keys or explicit provider selection.
"""

import os
import logging
from typing import Optional

from llm.llmapi import LLMAPI
from llm.claude import Claude
from llm.gemini import Gemini
from llm.openai import OpenAI
from llm.ollama import Ollama


def get_ai_provider(provider_name: Optional[str] = None) -> LLMAPI:
    """
    Factory function to get the appropriate AI provider instance.
    
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
        if provider_name == 'claude':
            if not os.environ.get('ANTHROPIC_API_KEY'):
                raise ValueError("Requested Claude provider but ANTHROPIC_API_KEY not found")
            return Claude()
        elif provider_name == 'gemini':
            if not os.environ.get('GEMINI_API_KEY'):
                raise ValueError("Requested Gemini provider but GEMINI_API_KEY not found")
            return Gemini()
        elif provider_name == 'openai':
            if not os.environ.get('OPENAI_API_KEY'):
                raise ValueError("Requested OpenAI provider but OPENAI_API_KEY not found")
            return OpenAI()
        elif provider_name == 'ollama':
            # Ollama can use local models, so no API key check
            return Ollama()
        else:
            raise ValueError(f"Unknown provider name: {provider_name}")
    
    # Auto-detect provider based on available API keys
    if os.environ.get('ANTHROPIC_API_KEY'):
        logging.info("Using Claude provider (ANTHROPIC_API_KEY found)")
        return Claude()
    elif os.environ.get('GEMINI_API_KEY'):
        logging.info("Using Gemini provider (GEMINI_API_KEY found)")
        return Gemini()
    elif os.environ.get('OPENAI_API_KEY'):
        logging.info("Using OpenAI provider (OPENAI_API_KEY found)")
        return OpenAI()
    else:
        # Default to Ollama if no API keys are found
        logging.info("Using Ollama provider (no API keys found)")
        return Ollama()
