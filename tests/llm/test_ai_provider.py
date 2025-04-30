"""Unit tests for AI provider interface and factory."""

import os
import unittest
from unittest.mock import patch

import pytest

from streetrace.llm.claude.impl import Claude
from streetrace.llm.gemini.impl import Gemini
from streetrace.llm.llmapi import LLMAPI
from streetrace.llm.llmapi_factory import get_ai_provider
from streetrace.llm.ollama.impl import Ollama
from streetrace.llm.openai.impl import OpenAI


class TestAIProvider(unittest.TestCase):
    """Test cases for AI provider interface and factory."""

    def test_provider_implementations(self) -> None:
        """Verify that all provider implementations inherit from LLMAPI."""
        assert issubclass(Claude, LLMAPI)
        assert issubclass(Gemini, LLMAPI)
        assert issubclass(OpenAI, LLMAPI)
        assert issubclass(Ollama, LLMAPI)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}, clear=True)
    def test_get_provider_claude(self) -> None:
        """Test getting Claude provider when ANTHROPIC_API_KEY is set."""
        provider = get_ai_provider()
        assert isinstance(provider, Claude)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}, clear=True)
    def test_get_provider_gemini(self) -> None:
        """Test getting Gemini provider when GEMINI_API_KEY is set."""
        provider = get_ai_provider()
        assert isinstance(provider, Gemini)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}, clear=True)
    def test_get_provider_openai(self) -> None:
        """Test getting OpenAI provider when OPENAI_API_KEY is set."""
        provider = get_ai_provider()
        assert isinstance(provider, OpenAI)

    def test_get_provider_explicit(self) -> None:
        """Test explicitly requesting a specific provider."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}, clear=True):
            provider = get_ai_provider("claude")
            assert isinstance(provider, Claude)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}, clear=True):
            provider = get_ai_provider("gemini")
            assert isinstance(provider, Gemini)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}, clear=True):
            provider = get_ai_provider("openai")
            assert isinstance(provider, OpenAI)

        provider = get_ai_provider("ollama")
        assert isinstance(provider, Ollama)

    def test_get_provider_invalid(self) -> None:
        """Test requesting an invalid provider."""
        with pytest.raises(ValueError):
            get_ai_provider("invalid_provider")

    def test_get_provider_missing_key(self) -> None:
        """Test requesting a provider without required API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                get_ai_provider("claude")

            with pytest.raises(ValueError):
                get_ai_provider("gemini")

            with pytest.raises(ValueError):
                get_ai_provider("openai")


if __name__ == "__main__":
    unittest.main()
